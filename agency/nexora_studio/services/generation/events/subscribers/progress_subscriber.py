from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent
from odoo.addons.nexora_studio.services.generation.events.subscribers.base_subscriber import PipelineEventSubscriber

class ProgressSubscriber(PipelineEventSubscriber):
    def handle(self, event: PipelineEvent) -> None:
        pass  # Stub for future implementation
