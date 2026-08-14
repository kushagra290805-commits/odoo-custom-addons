import time
import logging
from typing import Optional
from .plan_models import ExecutionPlan, ExecutionState, PlanExecutionTrace, ExecutionContext
from .dependency_resolver import DependencyResolver
from odoo.addons.nexora_studio.services.capabilities.selection_engine import CapabilitySelectionEngine

_logger = logging.getLogger(__name__)

class PlanOrchestrator:
    """
    Executes an ExecutionPlan.
    Responsible for state management, retries, checkpointing, and trace construction.
    """
    
    def __init__(self, selection_engine: CapabilitySelectionEngine):
        self.selection_engine = selection_engine
        self.resolver = DependencyResolver()
        
    def execute_plan(self, plan: ExecutionPlan) -> PlanExecutionTrace:
        trace = PlanExecutionTrace(plan_id=plan.plan_id)
        start_time = time.time()
        
        try:
            # 1. Resolve execution order
            execution_order = self.resolver.resolve_execution_order(plan)
        except Exception as e:
            trace.validation_results.append(f"Failed to resolve execution order: {e}")
            return trace
            
        # 2. Execute steps in order
        for step_id in execution_order:
            step = plan.graph.steps[step_id]
            
            if step.state in [ExecutionState.SUCCESS, ExecutionState.SKIPPED, ExecutionState.CANCELLED]:
                continue
                
            step.state = ExecutionState.RUNNING
            step.start_time = time.time()
            _logger.info(f"Orchestrator: Running step {step_id} - capability {step.capability}")
            
            # Context preparation
            payload = step.payload_template.copy()
            # In a full implementation, we'd inject context variables into payload here.
            
            success = False
            attempts = 0
            max_attempts = step.retry_policy.max_retries + 1
            
            while attempts < max_attempts and not success:
                attempts += 1
                step.retries_attempted = attempts - 1
                if step.retries_attempted > 0:
                    step.state = ExecutionState.RETRYING
                    _logger.info(f"Orchestrator: Retrying step {step_id} (Attempt {attempts}/{max_attempts})")
                    
                try:
                    # Execute via CSE
                    # We pass the shared context. It should contain intent, artifacts, etc.
                    # The CSE and underlying router could mutate the context.
                    context_dict = {
                        "intent": plan.context.intent,
                        "artifacts": plan.context.artifacts,
                        "shared_variables": plan.context.shared_variables
                    }
                    
                    result = self.selection_engine.execute_capability(step.capability, payload, context_dict)
                    
                    if getattr(result, 'success', False):
                        success = True
                        step.result = getattr(result, 'result', None)
                        step.logs.extend(getattr(result, 'logs', []))
                        
                        # Store intermediate outputs in context
                        if step.result:
                            plan.context.intermediate_outputs[step_id] = step.result
                            
                        # Extract provider namespace if available from logs
                        provider_namespace = "unknown"
                        for log in getattr(result, 'logs', []):
                            if isinstance(log, str) and "Attempting " in log:
                                parts = log.split("Attempting ")
                                if len(parts) > 1:
                                    provider_namespace = parts[1].split(" ")[0]
                                    break
                                    
                        # Update trace
                        trace.capability_trace.append({
                            "step_id": step_id,
                            "capability": step.capability,
                            "status": "success",
                            "provider": provider_namespace,
                            "duration_sec": time.time() - step.start_time,
                            "logs": getattr(result, 'logs', [])
                        })
                    else:
                        step.logs.extend(getattr(result, 'logs', []))
                        # Backoff before retry
                        if attempts < max_attempts:
                            time.sleep(step.retry_policy.delay_ms / 1000.0 * (step.retry_policy.backoff_multiplier ** (attempts - 1)))
                            
                except Exception as e:
                    step.logs.append(f"Unhandled exception: {e}")
                    if attempts < max_attempts:
                        time.sleep(step.retry_policy.delay_ms / 1000.0 * (step.retry_policy.backoff_multiplier ** (attempts - 1)))
                        
            step.end_time = time.time()
            trace.retry_history[step_id] = step.retries_attempted
            
            if success:
                step.state = ExecutionState.SUCCESS
                trace.steps_completed.append(step_id)
                self._save_checkpoint(plan, step_id)
            else:
                step.state = ExecutionState.FAILED
                trace.steps_failed.append(step_id)
                self._save_checkpoint(plan, step_id)
                
                # Default behavior: Stop execution on first failure for strict DAGs
                _logger.error(f"Orchestrator: Step {step_id} failed. Halting execution.")
                break
                
        trace.execution_time = time.time() - start_time
        return trace
        
    def _save_checkpoint(self, plan: ExecutionPlan, step_id: str):
        """
        Saves the execution state and context to allow resumability.
        In this phase, we just log it. Future implementations will persist to DB/Disk.
        """
        _logger.info(f"Checkpoint saved after step {step_id}.")
        pass
