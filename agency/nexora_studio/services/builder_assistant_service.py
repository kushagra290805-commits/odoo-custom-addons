# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class BuilderAssistantService(models.AbstractModel):
    _name = 'nexora.builder_assistant_service'
    _description = 'Builder Assistant Coordinator'

    @api.model
    def execute(self, session_id, intent, prompt, context=None):
        session = self.env['nexora.builder_session'].browse(int(session_id))
        if not session.exists():
            return {'status': 'error', 'error': 'Session not found'}

        # 1. Intent Detection
        self._emit(session_id, 'ai.intent.detected', f"Detected intent: {intent}")
        
        # 2. Context Collection
        self._emit(session_id, 'ai.context.collected', "Collecting workspace and memory context")
        active_file = context.get('active_file') if context else None
        
        ctx_builder = self.env['nexora.context_builder']
        ai_context = ctx_builder.build_assistant_context(session, active_file)
        
        # Build strict prompt for the adapter
        sys_context = ctx_builder.to_prompt_text(ai_context)
        final_prompt = f"{sys_context}\n\nUSER PROMPT: {prompt}"

        if intent in ['patch', 'modify']:
            final_prompt += "\n\nYou must return a unified diff patch or a full file replacement."

        # 3. Execution Started
        self._emit(session_id, 'ai.execution.started', "Executing AI request via Provider Manager")
        
        provider_manager = self.env['nexora.ai_provider_manager']
        response = provider_manager.route_request(
            task_type='builder_assistant',
            prompt=final_prompt,
            parameters={'temperature': 0.4}
        )

        if response.get('error'):
            self._emit(session_id, 'ai.execution.failed', f"Execution failed: {response['error']}")
            return {'status': 'error', 'error': response['error']}

        # Save to memory
        self.env['nexora.builder_conversation'].add_message(session_id, 'user', prompt)
        self.env['nexora.builder_conversation'].add_message(session_id, 'assistant', response['response'])

        # 4. Patch Generation (if applicable)
        # Note: The frontend will parse the response. If it contains a code block, the UI asks for approval.
        if '```' in response['response']:
            self._emit(session_id, 'ai.patch.generated', "Patch generated, awaiting approval.")
        else:
            self._emit(session_id, 'ai.execution.completed', "Execution completed.")

        return {
            'status': 'success',
            'response': response['response']
        }

    @api.model
    def approve_patch(self, session_id, file_path, content):
        """Applies an approved patch safely via WorkspaceFileService."""
        session = self.env['nexora.builder_session'].browse(int(session_id))
        
        # Pre-Checkpoint
        self.env['nexora.git_service'].commit_session(session_id, f"Auto-checkpoint before AI edit to {file_path}")
        
        # Save via WorkspaceFileService
        res = self.env['nexora.workspace_file_service'].save_file(session_id, file_path, content)
        if res.get('status') == 'error':
            self._emit(session_id, 'ai.execution.failed', f"Failed to apply patch: {res.get('error')}")
            return res
            
        # Post-Checkpoint
        self.env['nexora.git_service'].commit_session(session_id, f"AI Edit applied to {file_path}")
        
        self._emit(session_id, 'ai.execution.completed', f"Patch successfully applied to {file_path}.")
        return {'status': 'success'}

    def _emit(self, session_id, event_type, message):
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session_id,
            'runtime_type': 'ai',
            'event_type': event_type,
            'message': message,
        })
