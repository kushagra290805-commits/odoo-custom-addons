from odoo import fields

from odoo.addons.nexora_studio.services.generation.events.events import PipelineEvent
from odoo.addons.nexora_studio.services.generation.events.subscribers.base_subscriber import PipelineEventSubscriber


class ProgressSubscriber(PipelineEventSubscriber):
    """Persist successful pipeline progress on the existing builder session."""

    def __init__(self, env=None):
        self.env = env

    def _session(self, event):
        if not self.env:
            return None
        try:
            session_id = int(event.session_id)
        except (TypeError, ValueError):
            return None
        return self.env['nexora.builder_session'].sudo().browse(session_id).exists()

    def handle(self, event: PipelineEvent) -> None:
        session = self._session(event)
        if not session:
            return

        if event.event_type == 'StateTransitionCompleted':
            completed = event.metadata.get('completed_steps')
            total = event.metadata.get('total_steps')
            if not isinstance(completed, int) or not isinstance(total, int):
                return
            if total <= 0 or completed < 0 or completed > total:
                return
            if completed < session.completed_stages:
                return

            session.current_stage = event.current_state
            session.completed_stages = completed
            session.total_stages = total
            session.progress_percent = completed / total * 100
            session.last_activity = fields.Datetime.now()
            return

        if event.event_type == 'EngineFailed':
            engine_name = getattr(event, 'engine_name', '') or event.current_state
            session.current_stage = f'Failed: {engine_name}'
            session.last_activity = fields.Datetime.now()
        elif event.event_type == 'GenerationInterrupted':
            session.current_stage = 'Interrupted'
            session.last_activity = fields.Datetime.now()
        elif event.event_type == 'GenerationFailed':
            session.current_stage = 'Failed'
            session.last_activity = fields.Datetime.now()
