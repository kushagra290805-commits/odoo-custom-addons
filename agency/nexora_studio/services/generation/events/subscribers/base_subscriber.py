from abc import ABC, abstractmethod
from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent

class PipelineEventSubscriber(ABC):
    """Abstract interface for all pipeline event subscribers."""
    
    @abstractmethod
    def handle(self, event: PipelineEvent) -> None:
        """Handle an incoming pipeline event."""
        pass
