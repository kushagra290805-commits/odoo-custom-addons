import time
import threading
import uuid
import logging
from typing import Dict, List, Any, Optional
from collections import deque
from odoo.addons.nexora_studio.services.generation.streaming.stream_session import StreamSession
from odoo.addons.nexora_studio.services.generation.streaming.progress_calculator import ProgressCalculator

_logger = logging.getLogger(__name__)

class StreamingService:
    """
    Central hub for managing streaming sessions, replay buffers, QoS, and heartbeats.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(StreamingService, cls).__new__(cls)
                    cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        # generation_id -> List[StreamSession]
        self.active_sessions: Dict[str, List[StreamSession]] = {}
        
        # generation_id -> deque of recent events (Replay Buffer)
        self.replay_buffers: Dict[str, deque] = {}
        
        # Operational limits
        self.MAX_BUFFER_SIZE = 100
        self.HEARTBEAT_INTERVAL_SEC = 15
        
        # Metrics
        self.metrics = {
            "active_streams": 0,
            "completed_streams": 0,
            "cancelled_streams": 0,
            "reconnect_count": 0,
            "replay_events_served": 0,
            "heartbeat_failures": 0
        }
        
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def register_client(self, generation_id: str, correlation_id: str, client_id: str, transport: Any, last_event_id: Optional[str] = None) -> StreamSession:
        """Register a new client session for a generation stream."""
        with self._lock:
            session = StreamSession(
                session_id=str(uuid.uuid4()),
                generation_id=generation_id,
                correlation_id=correlation_id,
                client_id=client_id,
                transport=transport
            )
            
            if generation_id not in self.active_sessions:
                self.active_sessions[generation_id] = []
            if generation_id not in self.replay_buffers:
                self.replay_buffers[generation_id] = deque(maxlen=self.MAX_BUFFER_SIZE)
                
            self.active_sessions[generation_id].append(session)
            self.metrics["active_streams"] += 1
            
            # Reconnect & Replay logic
            if last_event_id:
                self.metrics["reconnect_count"] += 1
                self._replay_missing_events(session, generation_id, last_event_id)
                
            return session

    def unregister_client(self, session: StreamSession):
        """Remove a client session."""
        with self._lock:
            if session.generation_id in self.active_sessions:
                if session in self.active_sessions[session.generation_id]:
                    self.active_sessions[session.generation_id].remove(session)
                    session.disconnect()
                    self.metrics["active_streams"] = max(0, self.metrics["active_streams"] - 1)

    def dispatch(self, generation_id: str, payload: Dict[str, Any]):
        """Dispatch a standard streaming payload to all active clients for a generation."""
        with self._lock:
            # 1. Add to Replay Buffer
            if generation_id not in self.replay_buffers:
                self.replay_buffers[generation_id] = deque(maxlen=self.MAX_BUFFER_SIZE)
            
            # Inject a unique event ID for replay tracking if not present
            if "event_id" not in payload:
                payload["event_id"] = str(uuid.uuid4())
                
            self.replay_buffers[generation_id].append(payload)
            
            # 2. Send to Active Sessions
            sessions = self.active_sessions.get(generation_id, [])
            for session in sessions:
                try:
                    session.transport.send(payload)
                    session.last_event_id = payload["event_id"]
                except Exception as e:
                    _logger.warning(f"Failed to send to client {session.client_id}: {e}")
                    # In a robust system, we might mark for cleanup.

            # Cleanup logic on terminal events
            event_type = payload.get("event")
            if event_type in ["generation-completed", "generation-failed", "generation-cancelled"]:
                self._cleanup_generation(generation_id, event_type)

    def _replay_missing_events(self, session: StreamSession, generation_id: str, last_event_id: str):
        """Replay events from the buffer after the last_event_id."""
        buffer = self.replay_buffers.get(generation_id, [])
        replay_list = []
        found = False
        
        for payload in buffer:
            if found:
                replay_list.append(payload)
            elif payload.get("event_id") == last_event_id:
                found = True
                
        # If not found, replay the entire buffer as a fallback, or handle QoS
        if not found and buffer:
            replay_list = list(buffer)
            
        for payload in replay_list:
            try:
                session.transport.send(payload)
                session.last_event_id = payload.get("event_id")
                self.metrics["replay_events_served"] += 1
            except Exception:
                pass

    def _cleanup_generation(self, generation_id: str, terminal_event: str):
        """Clean up resources when generation finishes."""
        if terminal_event == "generation-completed":
            self.metrics["completed_streams"] += 1
        elif terminal_event == "generation-cancelled":
            self.metrics["cancelled_streams"] += 1
            
        sessions = self.active_sessions.get(generation_id, [])
        for session in sessions:
            session.disconnect()
            self.metrics["active_streams"] = max(0, self.metrics["active_streams"] - 1)
            
        if generation_id in self.active_sessions:
            del self.active_sessions[generation_id]
        if generation_id in self.replay_buffers:
            del self.replay_buffers[generation_id]

    def _heartbeat_loop(self):
        """Background thread to emit heartbeats every HEARTBEAT_INTERVAL_SEC."""
        while self.running:
            time.sleep(self.HEARTBEAT_INTERVAL_SEC)
            with self._lock:
                for gen_id, sessions in self.active_sessions.items():
                    if not sessions:
                        continue
                    
                    # Construct enriched heartbeat
                    # We look at the replay buffer to find the latest state
                    current_state = "UNKNOWN"
                    buffer = self.replay_buffers.get(gen_id, [])
                    if buffer:
                        current_state = buffer[-1].get("state", current_state)
                        
                    progress = ProgressCalculator.calculate(current_state)
                    
                    # Assume correlation_id from the first session
                    corr_id = sessions[0].correlation_id
                    
                    hb_payload = {
                        "event": "heartbeat",
                        "state": current_state,
                        "progress": progress,
                        "timestamp": time.time(),
                        "generation_id": gen_id,
                        "correlation_id": corr_id,
                        "metadata": {}
                    }
                    
                    for session in sessions:
                        try:
                            session.transport.send(hb_payload)
                            session.update_heartbeat()
                        except Exception:
                            self.metrics["heartbeat_failures"] += 1
