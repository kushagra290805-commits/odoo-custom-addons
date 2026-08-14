import logging
from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent
from odoo.addons.nexora_studio.services.generation.events.subscribers.base_subscriber import PipelineEventSubscriber
from odoo.addons.nexora_studio.services.generation.events.event_recorder import EventRecorder

_logger = logging.getLogger(__name__)

class LoggingSubscriber(PipelineEventSubscriber):
    def __init__(self, recorder: EventRecorder = None):
        self.recorder = recorder or EventRecorder()
        
    def handle(self, event: PipelineEvent) -> None:
        self.recorder.record(event)
