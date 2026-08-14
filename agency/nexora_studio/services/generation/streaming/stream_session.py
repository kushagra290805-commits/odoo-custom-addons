import time
from typing import Any, Dict, Optional

class StreamSession:
    """
    Manages an individual client connection for streaming.
    Isolates streaming lifecycle from the generation lifecycle.
    """
    def __init__(self, session_id: str, generation_id: str, correlation_id: str, client_id: str, transport: Any):
        self.session_id = session_id
        self.generation_id = generation_id
        self.correlation_id = correlation_id
        self.client_id = client_id
        self.transport = transport
        self.status = "connected"
        self.connected_at = time.time()
        self.last_heartbeat = self.connected_at
        self.last_event_id: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        
    def update_heartbeat(self):
        self.last_heartbeat = time.time()

    def disconnect(self):
        self.status = "disconnected"
        if hasattr(self.transport, "close"):
            self.transport.close()
