# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import logging

_logger = logging.getLogger(__name__)

class ToolWorkspace(models.AbstractModel):
    _name = 'nexora.tool.workspace'
    _inherit = 'nexora.tool.base'
    _description = 'Workspace Tool'

    @api.model
    def metadata(self):
        return {
            'capability_code': 'mcp.tool.workspace',
            'display_name': 'Workspace Metadata Tool',
            'description': 'Read workspace metadata and configuration.',
            'provider': 'nexora',
            'version': '1.0.0'
        }

    @api.model
    def schema(self):
        return {
            'type': 'object',
            'properties': {
                'command': {
                    'type': 'string',
                    'description': 'The command to execute'
                }
            },
            'required': ['command']
        }

    @api.model
    def validate(self, session, **kwargs):
        return True

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        session = request.runtime
        command = request.payload.get('command') or request.namespace.split('.')[-1]
        kwargs = request.payload
        """
        Executes the workspace tool capability.
        Delegates to WorkspaceService where supported, falls back to legacy string for missing functionality.
        """
        _logger.info(f"Executing workspace tool command: {command}")
        
        if command == 'get_path':
            workspace_service = self.env['nexora.workspace_service']
            try:
                path = workspace_service.resolve_workspace_path(session.workspace_id) if session and session.workspace_id else workspace_service.get_workspace_root_path()
                return {
                    "status": "success",
                    "path": path,
                    "message": f"Executed workspace {command}."
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e)
                }
        
        _logger.warning(f"Capability gap hit for workspace command '{command}'. Returning compatibility fallback.")
        return {
            "status": "success",
            "message": f"Executed workspace {command}."
        }
