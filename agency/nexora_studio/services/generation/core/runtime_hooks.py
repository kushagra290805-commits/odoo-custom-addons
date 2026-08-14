class RuntimeHooks:
    """Internal lifecycle hooks for GenerationRuntime."""
    
    def before_execute(self, engine_name: str, context: 'GenerationContext') -> None:
        pass
        
    def after_execute(self, engine_name: str, result: 'EngineExecutionResult') -> None:
        pass
        
    def before_ai_call(self, operation: str, payload: dict) -> None:
        pass
        
    def after_ai_call(self, operation: str, response: dict) -> None:
        pass
        
    def before_workspace_write(self, path: str, content: str) -> None:
        pass
        
    def after_workspace_write(self, path: str) -> None:
        pass
        
    def before_state_transition(self, current_state: str, next_state: str) -> None:
        pass
        
    def after_state_transition(self, current_state: str, next_state: str) -> None:
        pass
