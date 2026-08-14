from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent
from odoo.addons.nexora_studio.services.generation.events.subscribers.base_subscriber import PipelineEventSubscriber
from odoo.addons.nexora_studio.services.generation.streaming.streaming_service import StreamingService
from odoo.addons.nexora_studio.services.generation.streaming.progress_calculator import ProgressCalculator

class StreamingSubscriber(PipelineEventSubscriber):
    """
    Subscribes to pipeline events, translates them to standardized streaming payloads,
    and dispatches them via the StreamingService.
    Does NOT modify the original event.
    """
    def __init__(self):
        self.streaming_service = StreamingService()
        
    def _map_event_name(self, original_type: str) -> str:
        """Standardize streaming event names."""
        mapping = {
            "GenerationStarted": "generation-started",
            "GenerationCompleted": "generation-completed",
            "GenerationFailed": "generation-failed",
            "StateTransitionStarted": "state-transition",
            "StateTransitionCompleted": "state-transition",
            "EngineStarted": "engine-started",
            "EngineCompleted": "engine-completed",
            "EngineFailed": "engine-failed"
        }
        return mapping.get(original_type, "progress")

    def handle(self, event: PipelineEvent) -> None:
        """Handle incoming pipeline events and forward them."""
        # Calculate progress
        state_for_progress = event.next_state if event.next_state else event.current_state
        progress = ProgressCalculator.calculate(state_for_progress)
        
        # Build standard payload
        payload = {
            "event": self._map_event_name(event.event_type),
            "state": state_for_progress,
            "progress": progress,
            "timestamp": event.timestamp,
            "generation_id": event.generation_id,
            "correlation_id": event.correlation_id,
            "event_version": event.event_version,
            "metadata": dict(event.metadata)
        }
        
        # Dispatch through Streaming Service
        self.streaming_service.dispatch(event.generation_id, payload)
