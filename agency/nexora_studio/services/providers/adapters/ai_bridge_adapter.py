import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
from typing import Dict, Any, List

from ..base_provider import (
    BaseProvider,
    ProviderMetadata,
    ProviderCategory,
    ProviderConfiguration,
    ProviderAuthentication,
    ProviderHealth,
    ProviderCapability,
    ProviderSearchResult,
    ProviderExecutionResult,
    ProviderExecutionContext
)

_logger = logging.getLogger(__name__)

class UnifiedAIProviderProxy(BaseProvider):
    """
    Bridge adapter wrapping legacy AI providers (e.g., openai_adapter, nvidia_adapter)
    into the Unified Provider Platform (ADR-0031).
    """

    def __init__(self, metadata: ProviderMetadata):
        super().__init__(metadata)
        self._legacy_manager = None
        self._provider_name = metadata.provider_id.replace("legacy_ai_", "")

    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="legacy_ai_bridge",
            name="Legacy AI Bridge Adapter",
            category=ProviderCategory.AI,
            provider_version="1.0.0",
            manifest_version="2.0",
            api_version="v1",
            vendor_url="internal",
            author="Nexora Studio"
        )

    def initialize(self, config: ProviderConfiguration) -> None:
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                # Eagerly load the AI provider manager from Odoo env
                self._legacy_manager = http.request.env['agency.ai_provider_manager']
        except ImportError:
            pass

    def authenticate(self, auth: ProviderAuthentication) -> bool:
        # Legacy auth is typically handled by reading Odoo config directly in the manager
        return True

    def check_health(self) -> ProviderHealth:
        if not self._legacy_manager:
            return ProviderHealth(status="degraded", latency_ms=0.0, error_rate_24h=0.0, last_checked=None, details="No legacy manager")
            
        try:
            # Assuming the legacy manager has a ping or we just return healthy
            return ProviderHealth(status="healthy", latency_ms=10.0, error_rate_24h=0.0, last_checked=None)
        except Exception as e:
            return ProviderHealth(status="degraded", latency_ms=0.0, error_rate_24h=0.0, last_checked=None, details=str(e))

    def discover_capabilities(self) -> List[ProviderCapability]:
        # Expose legacy operations as Unified Capabilities
        return [
            ProviderCapability(
                capability_id=f"{self.metadata.provider_id}_chat",
                operation_type="chat_completion",
                capability_version="1.0",
                supported_revisions=["1.0"],
                deprecated_revisions=[],
                parameter_schema={},
                output_schema={},
                rate_limits={"rpm": 60},
                supports_streaming=True,
                min_context_window_tokens=4096,
                max_output_tokens=2048
            )
        ]

    def search(self, query: str, filters: Dict[str, Any]) -> List[ProviderSearchResult]:
        return []

    def fetch(self, resource_id: str, context: ProviderExecutionContext) -> ProviderExecutionResult:
        return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=NotImplementedError("fetch not supported by AI Bridge"))

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        operation = request.payload.get('operation') or request.namespace.split('.')[-1]
        payload = request.payload
        context = request.context
        import time
        start = time.time()
        
        if not self._legacy_manager:
            return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=None)
            
        # Route to legacy manager based on operation
        if operation == "chat_completion":
            prompt = payload.get("prompt", "")
            system = payload.get("system", "")
            # Legacy signature: get_ai_response(provider, prompt, system, ...)
            try:
                res = self._legacy_manager.get_ai_response(self._provider_name, prompt, system_message=system)
                duration = (time.time() - start) * 1000
                return ProviderExecutionResult(success=True, data=res, metadata={"legacy": True}, execution_ms=duration)
            except Exception as e:
                duration = (time.time() - start) * 1000
                return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=duration, error=Exception(str(e)))
        
        return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=None)
    def cleanup(self) -> None:
        self._legacy_manager = None

