class McpClient:
    def connect(self):
        pass

class McpSessionManager:
    def __init__(self):
        self.clients = {}
        
    def get_session(self, session_id: str):
        return self.clients.get(session_id)