from .session import McpSessionManager

class ProtocolLayer:
    def __init__(self, session_manager: McpSessionManager):
        self.session_manager = session_manager
        
    def serialize(self, payload: dict) -> str:
        return str(payload)
        
    def deserialize(self, data: str) -> dict:
        return {"data": data}