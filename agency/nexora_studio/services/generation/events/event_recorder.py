import logging
import json
from dataclasses import asdict
from typing import Any
from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent

_logger = logging.getLogger(__name__)

class EventRecorder:
    """
    Persists structured event logs for auditing, future event replay,
    and debugging history. Subscribers remain independent of this recorder.
    """
    def __init__(self, env: Any = None):
        self.env = env
        
    def record(self, event: PipelineEvent) -> None:
        """Record the event in a structured format."""
        try:
            event_dict = asdict(event)
            # Remove complex artifact references for basic logging
            if 'artifact_ref' in event_dict:
                event_dict.pop('artifact_ref', None)
                
            payload = json.dumps(event_dict, default=str)
            
            # Simple logging forwarder for now, ready for Odoo DB persistence
            _logger.info(f"[EventRecorder] {event.event_category} | {event.event_type} | {event.correlation_id}: {payload}")
            
            if self.env and 'nexora.runtime_event' in self.env:
                # Example of future DB persistence
                pass
                
        except Exception as e:
            _logger.error(f"Failed to record event {getattr(event, 'event_type', 'Unknown')}: {e}")
