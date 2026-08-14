from typing import Any, Callable, Dict, List, Optional
from odoo.addons.nexora_studio.services.generation.core.workspace_adapter import WorkspaceAdapter
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import GenerationStateManager

class AIRuntimeAdapter:
    def __init__(self, provider_manager: Any, hooks: Any = None):
        self._pm = provider_manager
        self._hooks = hooks
        
    def generate(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route a request to the AI Provider Manager using the canonical contract."""
        import json
        
        if self._hooks:
            self._hooks.before_ai_call(operation, payload)
            
        # Extract prompt / task
        prompt = payload.get('prompt') or payload.get('task')
        
        # If there are remaining keys that look like context, stringify them into the prompt
        context_keys = [k for k in payload.keys() if k not in ('prompt', 'task', 'response_format', 'system_prompt', 'temperature', 'max_tokens', 'timeout', 'retries')]
        if context_keys:
            context_data = {k: payload[k] for k in context_keys}
            context_str = json.dumps(context_data, default=str)
            if prompt:
                prompt = f"{prompt}\n\nContext:\n{context_str}"
            else:
                prompt = context_str
                
        # Determine JSON mode
        json_mode = False
        if "response_format" in payload and payload.get("response_format", {}).get("type") == "json_schema":
            json_mode = True
            
        parameters = {
            "builder_session_id": getattr(self._hooks, 'session_id', 0) if self._hooks else 0,
            "json_mode": json_mode,
        }
        
        # Extract metadata overrides if present
        for key in ['system_prompt', 'temperature', 'max_tokens', 'timeout', 'retries']:
            if key in payload:
                parameters[key] = payload[key]
                
        # The AIProviderManager returns a generic response dict
        try:
            result = self._pm.route_request(
                task_type=operation,
                prompt=prompt,
                parameters=parameters
            )
        except Exception as e:
            raise Exception(f"AI Provider execution failed: {str(e)}")
            
        # Note: route_request returns a dict directly, often containing 'response' or 'patch_diff'
        # Some engines expect the raw dict, others expect certain keys. We pass the whole dict back.
        if self._hooks:
            self._hooks.after_ai_call(operation, result)
            
        return result
        
    def select_model(self, capability: str) -> str:
        provider = self._pm._resolve_provider(capability)
        return provider.provider_code if provider else "unknown"
        
    def estimate_cost(self, prompt: str, model: str) -> float:
        # Placeholder for AI Provider Manager cost estimation
        return 0.0

class EventsRuntimeAdapter:
    def __init__(self, event_bus: PipelineEventBus):
        self._bus = event_bus
        
    def publish(self, event: Any) -> None:
        """Publish a generic PipelineEvent."""
        self._bus.publish(event)
        
    def publish_progress(self, percentage: float, message: str) -> None:
        """Publish an ad-hoc progress event (to be implemented if needed by agents)."""
        pass
        
    def publish_agent(self, agent_name: str, status: str) -> None:
        """Publish an agent status event."""
        pass

class StateRuntimeAdapter:
    def __init__(self, state_manager: GenerationStateManager, context_id: str):
        self._sm = state_manager
        self._context_id = context_id
        
    def checkpoint(self, context: Any) -> None:
        self._sm.save_checkpoint(context)
        
    def restore(self) -> Optional[Any]:
        return self._sm.load_checkpoint(self._context_id)
        
    def progress(self, context: Any, state: Any, percentage: float, message: str) -> Any:
        return self._sm.update_progress(context, state, percentage, message)
        
    def current(self) -> Optional[Any]:
        return self._sm.load_checkpoint(self._context_id)

class CancellationRuntimeAdapter:
    def __init__(self, state_manager: GenerationStateManager, context_id: str):
        self._sm = state_manager
        self._context_id = context_id
        
    def is_cancelled(self) -> bool:
        return self._sm.check_interruption(self._context_id)

class AgentRuntimeAdapter:
    """Phase 18.5 Autonomous Agent capability."""
    
    def __init__(self, agent_runtime: Any):
        self._runtime = agent_runtime
        
    def execute(self, agent_class: Any, generation_runtime: Any, generation_id: str, **kwargs) -> Any:
        return self._runtime.invoke(agent_class, generation_runtime, generation_id, **kwargs)

    def request_human_approval(self, *args, **kwargs):
        # Reserved for Phase 18.x
        pass

    def spawn_subtask(self, *args, **kwargs):
        # Reserved for Phase 18.9
        pass

    def report_progress(self, *args, **kwargs):
        # Delegate to events
        pass

    def complete(self, *args, **kwargs):
        pass

class ToolRuntimeAdapter:
    """Phase 21D Universal Capability Execution Layer (UCEL) capability."""
    def __init__(self, ucel_router: Any):
        self._router = ucel_router
        
    def execute(self, namespace: str, payload: Dict[str, Any], scoped_runtime: Any, budget: int = 100) -> Any:
        # Wrap the tool execution in the new UCEL structure
        result = self._router.execute(namespace, payload, context={"scoped_runtime": scoped_runtime, "budget": budget})
        if not result.success:
            raise Exception(f"Capability Execution Failed: {' | '.join(result.logs)}")
        return result.result

class KnowledgeRuntimeAdapter:
    """Phase 18.7 Design Intelligence & Knowledge Framework capability."""
    def __init__(self, knowledge_service: Any):
        self._service = knowledge_service
        
    def search(self, query: Any) -> List[Any]:
        return self._service.query(query)

class RuntimeMetadata:
    def __init__(self, session_id: str, generation_id: str, correlation_id: str, started_at: float, initiated_by: str, runtime_version: str, environment: str, scope_name: str):
        self.session_id = session_id
        self.generation_id = generation_id
        self.correlation_id = correlation_id
        self.started_at = started_at
        self.initiated_by = initiated_by
        self.runtime_version = runtime_version
        self.environment = environment
        self.scope_name = scope_name

class OrchestratorRuntimeAdapter:
    def __init__(self, capability_resolver, ucel_router):
        self._resolver = capability_resolver
        self._router = ucel_router

    def execute_plan(self, objective: str, target_outputs: Optional[List[str]] = None, context_overrides: Optional[Dict[str, Any]] = None) -> Any:
        from odoo.addons.nexora_studio.services.capabilities.selection_engine import CapabilitySelectionEngine
        from odoo.addons.nexora_studio.services.planning.planner import IntelligentCapabilityPlanner
        from odoo.addons.nexora_studio.services.planning.plan_optimizer import PlanOptimizer
        from odoo.addons.nexora_studio.services.planning.orchestrator import PlanOrchestrator

        cse = CapabilitySelectionEngine(self._resolver, self._router)
        planner = IntelligentCapabilityPlanner()
        optimizer = PlanOptimizer()
        orchestrator = PlanOrchestrator(cse)
        
        plan = planner.plan(objective, target_outputs=target_outputs)
        plan = optimizer.optimize(plan)
        
        if context_overrides:
            for k, v in context_overrides.get("shared_variables", {}).items():
                plan.context.shared_variables[k] = v
            for k, v in context_overrides.get("artifacts", {}).items():
                plan.context.artifacts[k] = v

        trace = orchestrator.execute_plan(plan)
        return trace
