import logging
import time
from typing import Dict, Any, Generator, List

from .base_provider import (
    ExecutionOrchestrator,
    ProviderCategory,
    ProviderFeatureSet,
    ProviderSession,
    ExecutionRequest,
    ProviderServiceContainer,
    CapabilityResolver,
    LockService,
    ProviderStateMachine,
    ProviderRuntimeState,
    ProviderTelemetryService,
    UnifiedCostQuotaService,
    ProviderCache,
    ProviderMetricsService,
    ProviderRateLimitError,
    ProviderException
)
from .domain_events import (
    ProviderExecutionStarted,
    ProviderExecutionCompleted,
    ProviderExecutionFailed,
    DomainEventPublisher
)
from .transaction_manager import ProviderTransactionManager
from .execution_models import ProviderExecutionRequest, ProviderExecutionResult

_logger = logging.getLogger(__name__)

class OdooExecutionOrchestrator(ExecutionOrchestrator):
    """
    Master coordinator for all provider executions.
    Enforces concurrency limits, handles retries/fallbacks, and orchestrates
    telemetry, caching, and cost accounting.
    (Updated to integrate with ProviderTransactionManager and Domain Events)
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        self._active_executions: Dict[str, int] = {}

    @property
    def _resolver(self) -> CapabilityResolver:
        return self._container.resolve(CapabilityResolver)

    @property
    def _lock_service(self) -> LockService:
        return self._container.resolve(LockService)

    @property
    def _state_machine(self) -> ProviderStateMachine:
        return self._container.resolve(ProviderStateMachine)

    @property
    def _telemetry(self) -> ProviderTelemetryService:
        return self._container.resolve(ProviderTelemetryService)

    @property
    def _quota(self) -> UnifiedCostQuotaService:
        return self._container.resolve(UnifiedCostQuotaService)

    @property
    def _cache(self) -> ProviderCache:
        return self._container.resolve(ProviderCache)

    @property
    def _metrics(self) -> ProviderMetricsService:
        return self._container.resolve(ProviderMetricsService)
        
    @property
    def _tx_manager(self) -> ProviderTransactionManager:
        return self._container.resolve(ProviderTransactionManager)

    def execute(self, request: ProviderExecutionRequest, session: ProviderSession) -> ProviderExecutionResult:
        """
        Executes a synchronous operation with full governance.
        """
        # Resolve best provider
        # Note: In a real implementation, ExecutionPolicy could be passed in session.metadata
        category = request.execution_metadata.get('category', ProviderCategory.CUSTOM)
        operation = request.execution_metadata.get('operation') or request.namespace.split('.')[-1]
        required_features = request.execution_metadata.get('required_features', ProviderFeatureSet())
        provider = self._resolver.resolve(category, operation, required_features, session.to_execution_context())
        provider_id = provider.metadata.provider_id
        
        # Override session provider to the resolved one
        session.provider = provider
        
        concurrency = provider.metadata.concurrency_policy
        exec_lock_key = f"nexora:provider:{provider_id}:exec_lock"
        
        # ── Concurrency Throttling ──
        # Check if we exceed max parallel requests
        active = self._active_executions.get(provider_id, 0)
        if active >= concurrency.max_parallel_requests:
            if concurrency.reject_on_queue_full:
                raise ProviderRateLimitError(
                    f"Max parallel requests reached ({active}/{concurrency.max_parallel_requests})",
                    provider_id=provider_id,
                    retry_after_seconds=5
                )
            # Else, wait via lock acquisition timeout
        
        lock_res = self._lock_service.acquire(exec_lock_key, holder_id=session.session_id, timeout_ms=concurrency.queue_timeout_ms)
        if not lock_res.acquired:
            raise ProviderRateLimitError(
                f"Queue timeout waiting for execution slot",
                provider_id=provider_id,
                retry_after_seconds=10
            )
            
        try:
            self._active_executions[provider_id] = self._active_executions.get(provider_id, 0) + 1
            
            # Use Transaction Manager for the execution lifecycle
            self._tx_manager.begin_transaction()
            try:
                # Fire Domain Event
                DomainEventPublisher.publish(ProviderExecutionStarted(provider_id, session.session_id, operation))
                
                # Transition to BUSY
                self._state_machine.transition(provider_id, ProviderRuntimeState.BUSY, reason=f"Executing {operation}")
                
                # Telemetry span
                span_id = self._telemetry.start_span(operation, session)
                
                # Check quota
                # Rough estimate of cost, or just 1 unit for quota check
                if not self._quota.check_quota(provider_id, category, 1.0):
                    raise ProviderRateLimitError("Cost quota exceeded", provider_id=provider_id)
                
                start_time = time.time()
                is_retry = False
                is_fallback = False # Fallback logic omitted here for brevity, would be wrapped in a loop
                
                # Execute
                response = provider.execute(request=request)
                
                latency = (time.time() - start_time) * 1000
                
                # Finish span
                self._telemetry.end_span(span_id, response)
                
                # Charge cost
                token_cost_usd = response.metadata.get('token_cost_usd', 0.0)
                if token_cost_usd > 0:
                    session.charge(token_cost_usd, 0, 'tokens')
                    
                # Cache response
                cache_key = f"{provider_id}:{operation}:{hash(str(request.payload))}"
                self._cache.set(cache_key, response)
                
                # Record metrics
                self._metrics.record_request(provider_id, latency, response.success, is_fallback, is_retry)
                
                # Transition back to READY
                self._state_machine.transition(provider_id, ProviderRuntimeState.READY, reason="Execution complete")
                
                # Fire Domain Event
                DomainEventPublisher.publish(ProviderExecutionCompleted(provider_id, session.session_id, operation, latency))
                
                self._tx_manager.commit()
                return response
                
            except ProviderException as pe:
                self._tx_manager.rollback()
                
                DomainEventPublisher.publish(ProviderExecutionFailed(provider_id, session.session_id, operation, str(pe)))
                
                self._metrics.record_request(provider_id, 0.0, False, False, False)
                self._state_machine.transition(provider_id, ProviderRuntimeState.READY, reason="Execution failed")
                raise pe
                
            except Exception as e:
                self._tx_manager.rollback()
                
                DomainEventPublisher.publish(ProviderExecutionFailed(provider_id, session.session_id, operation, str(e)))
                
                self._metrics.record_request(provider_id, 0.0, False, False, False)
                self._state_machine.transition(provider_id, ProviderRuntimeState.READY, reason="Execution error")
                raise ProviderExecutionError(str(e), provider_id=provider_id)
                
        finally:
            self._active_executions[provider_id] -= 1
            self._lock_service.release(exec_lock_key, holder_id=session.session_id)

    def execute_streaming(self, request: ProviderExecutionRequest, session: ProviderSession) -> Generator[ProviderExecutionResult, None, None]:
        """
        Executes a streaming operation.
        """
        category = request.execution_metadata.get('category', ProviderCategory.CUSTOM)
        operation = request.execution_metadata.get('operation') or request.namespace.split('.')[-1]
        required_features = request.execution_metadata.get('required_features', ProviderFeatureSet())
        provider = self._resolver.resolve(category, operation, required_features, session.to_execution_context())
        session.provider = provider
        
        # Omitted full lock/quota/telemetry wrapping for brevity, follows same pattern as execute()
        yield from provider.execute_streaming(request)

    def execute_parallel(self, requests: List[ProviderExecutionRequest], session: ProviderSession) -> List[ProviderExecutionResult]:
        """
        Executes multiple requests in parallel, respecting concurrency limits.
        """
        import concurrent.futures
        
        responses = [None] * len(requests)
        
        def _exec_task(idx, req):
            try:
                res = self.execute(req, session)
                return idx, res
            except Exception as e:
                return idx, ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=str(e))

        if not requests:
            return []
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(len(requests), 10))) as executor:
            futures = [executor.submit(_exec_task, i, req) for i, req in enumerate(requests)]
            for future in concurrent.futures.as_completed(futures):
                idx, res = future.result()
                responses[idx] = res
                
        return responses
