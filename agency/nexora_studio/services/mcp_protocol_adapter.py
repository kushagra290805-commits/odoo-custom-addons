# -*- coding: utf-8 -*-
from odoo import models, api, _

class MCPProtocolAdapter(models.AbstractModel):
    _name = 'nexora.mcp_protocol_adapter'
    _description = 'MCP Protocol Translation Adapter'

    # Mapping of canonical internal tool capability codes to legacy external IDs.
    # Note: Only map explicitly required legacy names to ensure tight boundaries.
    _EXTERNAL_TO_INTERNAL = {
        'workspace': 'mcp.tool.workspace',
        'filesystem': 'mcp.tool.fs',
        'git': 'mcp.tool.git',
        'preview': 'mcp.tool.preview',
        'terminal': 'mcp.tool.terminal',
        'browser': 'mcp.tool.browser'
    }

    _INTERNAL_TO_EXTERNAL = {v: k for k, v in _EXTERNAL_TO_INTERNAL.items()}

    @api.model
    def serialize_tool_id(self, internal_capability_code):
        """
        Translates an internal capability code (e.g., 'mcp.tool.workspace') 
        to an external legacy ID (e.g., 'workspace').
        Returns the original code if no translation exists.
        """
        return self._INTERNAL_TO_EXTERNAL.get(internal_capability_code, internal_capability_code)

    @api.model
    def deserialize_tool_id(self, external_id):
        """
        Translates an external legacy ID (e.g., 'workspace') 
        back to an internal capability code (e.g., 'mcp.tool.workspace').
        Returns the original ID if no translation exists.
        """
        return self._EXTERNAL_TO_INTERNAL.get(external_id, external_id)

    @api.model
    def serialize_registered_tools(self, tool_registry_tools):
        """
        Takes a list of tools from ToolRegistry and serializes them 
        into the list of external IDs expected by MCPServer and IDE clients.
        
        :param tool_registry_tools: List of dicts returned by ToolRegistry.get_registered_tools()
        :return: List of string tool IDs for external consumption
        """
        external_tools = []
        for tool in tool_registry_tools:
            # Capability codes might be stored as 'tool_type' or 'tool_id' in ToolRegistry.
            # In ToolRegistry.get_registered_tools(), it uses tool_type = cap.capability_code
            internal_code = tool.get('tool_type') or tool.get('tool_id')
            if internal_code:
                external_tools.append(self.serialize_tool_id(internal_code))
        return external_tools
