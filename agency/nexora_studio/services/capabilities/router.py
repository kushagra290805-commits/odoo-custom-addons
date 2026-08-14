from typing import Dict
from .models import CapabilityResult, ExecutionTargetType
from .resolver import CapabilityResolver
from .policy import CapabilityPolicyEngine
from .security import SecurityLayer
from .middleware import MiddlewarePipeline
from .scheduler import ExecutionScheduler
from .executors.base import ExecutionTarget

class UniversalCapabilityRouter:
    def __init__(self, 
                 resolver: CapabilityResolver, 
                 policy_engine: CapabilityPolicyEngine,
                 security_layer: SecurityLayer,
                 middleware: MiddlewarePipeline,
                 scheduler: ExecutionScheduler,
                 executors: Dict[ExecutionTargetType, ExecutionTarget]):
        self.resolver = resolver
        self.policy_engine = policy_engine
        self.security = security_layer
        self.middleware = middleware
        self.scheduler = scheduler
        self.executors = executors
        
    def execute(self, namespace: str, payload: dict, context: dict = None) -> CapabilityResult:
        context = context or {}
        
        # Security
        if not self.security.authorize(namespace, context):
            return CapabilityResult(success=False, result=None, logs=["Unauthorized"])
            
        # Middleware PRE
        self.middleware.execute_pre(namespace, context)
        
        # Resolution
        candidates = self.resolver.resolve_candidates(namespace)
        descriptor = self.policy_engine.evaluate(candidates, context)
        
        if not descriptor:
            result = CapabilityResult(success=False, result=None, logs=[f"Capability not found: {namespace}"])
            self.middleware.execute_post(result, context)
            return result
            
        # Credential Injection
        context = self.security.inject_credentials(descriptor, context)
        
        # Canonical placeholder handler
        if namespace.endswith('_reviewer') and descriptor.manifest.metadata.get('provider') == 'nexora':
            result = CapabilityResult(success=True, result=[{"severity": "info", "message": "Capability Not Installed"}], logs=["Placeholder capability returned gracefully"])
            self.middleware.execute_post(result, context)
            return result
        
        # Execution
        target = self.executors.get(descriptor.manifest.target_type)
        if not target:
            result = CapabilityResult(success=False, result=None, logs=[f"Executor not found for {descriptor.manifest.target_type}"])
        else:
            if "tool_id" not in payload:
                payload["tool_id"] = namespace
            result = self.scheduler.schedule_and_execute(target, payload)
            
        # Middleware POST
        self.middleware.execute_post(result, context)
        return result