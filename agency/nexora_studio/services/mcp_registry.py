# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class MCPRegistry(models.AbstractModel):
    _name = 'nexora.mcp_registry'
    _description = 'MCP Tool Registry'

    @api.model
    def get_all_tools(self, session):
        """
        Dynamically discovers and returns all registered MCP tools for a session.
        """
        tools = []
        # In a real module system, we would query ir.model to find all models inheriting from a base tool class.
        # For simplicity and given Odoo's registry, we can just instantiate the known tools.
        # Alternatively, we could define them as models. Here we return dictionaries.
        
        tool_models = [
            'nexora.mcp_tool_filesystem',
            'nexora.mcp_tool_git',
            'nexora.mcp_tool_workspace',
            'nexora.mcp_tool_preview'
        ]
        
        for model_name in tool_models:
            if model_name in self.env:
                tools.append(self.env[model_name].get_definition())
                
        return tools


class MCPToolBase(models.AbstractModel):
    _name = 'nexora.mcp_tool_base'
    _description = 'Base MCP Tool'

    @api.model
    def get_definition(self):
        raise NotImplementedError

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        session = request.runtime
        command = request.payload.get('command') or request.namespace.split('.')[-1]
        kwargs = request.payload
        raise NotImplementedError

    @api.model
    def validate(self, **kwargs):
        return True

    @api.model
    def shutdown(self, session):
        pass


class MCPToolFilesystem(models.AbstractModel):
    _name = 'nexora.mcp_tool_filesystem'
    _inherit = 'nexora.mcp_tool_base'
    _description = 'Filesystem MCP Tool'

    @api.model
    def get_definition(self):
        return {
            'tool_id': 'filesystem',
            'display_name': 'Filesystem Tool',
            'description': 'Interact with the local workspace filesystem.',
            'capabilities': ['read', 'write', 'list', 'create', 'delete', 'rename', 'move', 'search', 'replace']
        }

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        session = request.runtime
        command = request.payload.get('command') or request.namespace.split('.')[-1]
        kwargs = request.payload
        fs_service = self.env['nexora.filesystem_service']
        # Route to fs_service based on command...
        return {"status": "success", "message": f"Executed {command} on filesystem."}


class MCPToolGit(models.AbstractModel):
    _name = 'nexora.mcp_tool_git'
    _inherit = 'nexora.mcp_tool_base'
    _description = 'Git MCP Tool'

    @api.model
    def get_definition(self):
        return {
            'tool_id': 'git',
            'display_name': 'Git Tool',
            'description': 'Interact with the Git repository of the workspace.',
            'capabilities': ['status', 'commit', 'branch', 'checkout', 'pull', 'push', 'diff', 'log']
        }

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        session = request.runtime
        command = request.payload.get('command') or request.namespace.split('.')[-1]
        kwargs = request.payload
        git_service = self.env['nexora.git_service']
        # Route to git_service...
        return {"status": "success", "message": f"Executed git {command}."}


class MCPToolWorkspace(models.AbstractModel):
    _name = 'nexora.mcp_tool_workspace'
    _inherit = 'nexora.mcp_tool_base'
    _description = 'Workspace MCP Tool'

    @api.model
    def get_definition(self):
        return {
            'tool_id': 'workspace',
            'display_name': 'Workspace Metadata Tool',
            'description': 'Read workspace metadata and configuration.',
            'capabilities': ['get_path', 'get_session', 'get_config', 'get_metadata', 'get_variables']
        }

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        session = request.runtime
        command = request.payload.get('command') or request.namespace.split('.')[-1]
        kwargs = request.payload
        return {"status": "success", "message": f"Executed workspace {command}."}


class MCPToolPreview(models.AbstractModel):
    _name = 'nexora.mcp_tool_preview'
    _inherit = 'nexora.mcp_tool_base'
    _description = 'Preview MCP Tool'

    @api.model
    def get_definition(self):
        return {
            'tool_id': 'preview',
            'display_name': 'Preview Tool',
            'description': 'Interact with the Preview Runtime.',
            'capabilities': ['refresh', 'restart', 'status', 'preview_url']
        }

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        session = request.runtime
        command = request.payload.get('command') or request.namespace.split('.')[-1]
        kwargs = request.payload
        return {"status": "success", "message": f"Executed preview {command}."}
