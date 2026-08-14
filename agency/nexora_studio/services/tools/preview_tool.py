# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult


class PreviewTool(models.AbstractModel):
    _name = 'nexora.tool.preview'
    _inherit = 'nexora.tool.base'
    _description = 'Preview Tool'

    def metadata(self):
        return {
            'capability_code': 'mcp.tool.preview',
            'display_name': 'Preview Tool',
            'category': 'tool',
            'version': '1.0.0',
            'author': 'Nexora Studio',
            'provider': 'nexora',
            'implementation_model': self._name,
            'supported_platforms': ['windows', 'linux', 'macos'],
            'supports_local': True,
            'supports_remote': True,
            'supports_async': True,
            'permissions': [],
            'dependencies': [],
            'optional_dependencies': [],
            'minimum_runtime_version': '1.0.0',
            'metadata_version': '1.0'
        }

    def health(self):
        return True

    def validate(self, context, **kwargs):
        """Validate that the preview context has a valid workspace."""
        if not context:
            return False
        return True

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        context = request.context
        kwargs = request.payload
        """
        Execute a preview action by delegating to the preview service.
        """
        
        action = kwargs.get('action', 'status')
        session = context.get('session') if isinstance(context, dict) else context

        try:
            preview_service = self.env['nexora.preview_service']
            if action == 'start':
                result = preview_service.start_preview(session)
                return ProviderExecutionResult(success=True, data=f'Preview started: {result}')
            elif action == 'stop':
                result = preview_service.stop_preview(session)
                return ProviderExecutionResult(success=True, data=f'Preview stopped: {result}')
            elif action == 'status':
                runtimes = self.env['nexora.runtime'].search([
                    ('builder_session_id', '=', session.id),
                    ('runtime_type', '=', 'preview')
                ])
                if runtimes:
                    rt = runtimes[0]
                    return ProviderExecutionResult(
                        success=True,
                        data=f'Preview status: {rt.status}, URL: {rt.endpoint}'
                    )
                return ProviderExecutionResult(success=True, data='No preview runtime found.')
            else:
                return ProviderExecutionResult(success=False, stderr=f'Unknown action: {action}')
        except Exception as e:
            return ProviderExecutionResult(success=False, stderr=str(e))
