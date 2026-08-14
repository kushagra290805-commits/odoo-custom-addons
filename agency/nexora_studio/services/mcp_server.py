# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import logging
import uuid
import json

_logger = logging.getLogger(__name__)

class MCPServer(models.AbstractModel):
    _name = 'nexora.mcp_server'
    _description = 'MCP Server Manager'

    @api.model
    def start_server(self, session):
        """
        Simulates the startup of an MCP server process for a Builder Session.
        In a real deployment, this might spawn a Node.js/Python MCP stdio/SSE server.
        """
        workspace = session.workspace_id
        if not workspace:
            raise ValidationError(_("Cannot start MCP Server without a linked workspace."))

        ide_meta = self._get_ide_metadata(session)
        tools = self.env['nexora.tool_registry'].get_registered_tools()
        
        server_state = {
            'server_uuid': str(uuid.uuid4()),
            'session_uuid': session.session_uuid,
            'workspace_uuid': workspace.workspace_uuid,
            'heartbeat': fields.Datetime.now().isoformat(),
            'connected_client': None,
            'connected_ide': ide_meta.get('ide_name'),
            'registered_tools': json.dumps(self.env['nexora.mcp_protocol_adapter'].serialize_registered_tools(tools)),
            'server_version': '1.0.0',
            'server_state': 'online',
            'last_activity': fields.Datetime.now().isoformat()
        }
        
        _logger.info(f"Started MCP Server {server_state['server_uuid']} for session {session.name}")
        return server_state

    @api.model
    def stop_server(self, session):
        """
        Stops the MCP server associated with the Builder Session.
        """
        _logger.info(f"Stopping MCP Server for session {session.name}")
        return True

    @api.model
    def get_server_status(self, session):
        """
        Returns the current status of the MCP server.
        """
        runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'mcp')
        ], limit=1)
        
        if not runtime or not runtime.metadata_json:
            return {'server_state': 'offline'}
            
        try:
            state = json.loads(runtime.metadata_json)
            # Update heartbeat
            state['heartbeat'] = fields.Datetime.now().isoformat()
            
            # Sync IDE state dynamically
            ide_meta = self._get_ide_metadata(session)
            state['connected_ide'] = ide_meta.get('ide_name')
            
            return state
        except Exception:
            return {'server_state': 'offline'}

    @api.model
    def _get_ide_metadata(self, session):
        ide_runtime = self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', 'ide')
        ], limit=1)
        
        if ide_runtime and ide_runtime.metadata_json:
            try:
                return json.loads(ide_runtime.metadata_json)
            except Exception:
                return {}
        return {}
