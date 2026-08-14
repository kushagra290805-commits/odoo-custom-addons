import json
from abc import ABC, abstractmethod
from typing import Dict, Any

class StreamingTransport(ABC):
    """Abstract base class for streaming transports."""
    @abstractmethod
    def send(self, payload: Dict[str, Any]) -> None:
        """Send a payload to the client."""
        pass
        
    @abstractmethod
    def close(self) -> None:
        """Close the transport connection."""
        pass

class SSETransport(StreamingTransport):
    """Server-Sent Events (SSE) Transport."""
    def __init__(self, queue: Any):
        # queue could be a thread-safe Queue or gevent Queue
        self.queue = queue
        
    def send(self, payload: Dict[str, Any]) -> None:
        """Format the payload as SSE data and put it in the queue."""
        data_str = json.dumps(payload, default=str)
        # SSE format: data: {...}\n\n
        sse_message = f"data: {data_str}\n\n"
        self.queue.put(sse_message)
        
    def close(self) -> None:
        """Signal the end of the stream."""
        # Typically we send a sentinel value or close the queue.
        # Sending a close event or None
        self.queue.put(None)
