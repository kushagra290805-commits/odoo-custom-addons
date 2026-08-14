# -*- coding: utf-8 -*-
"""
nexora.mcp_discovered_tool — Discovered MCP Tool Schema
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Stores tool/resource/prompt metadata discovered from a live MCP server.
Results are snapshots: each discovery run replaces the previous results.
Does NOT hardcode tool names as Python identifiers.
"""
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class NexoraMcpDiscoveredTool(models.Model):
    _name = 'nexora.mcp_discovered_tool'
    _description = 'Discovered MCP Tool'
    _order = 'connector_id, discovery_source, tool_name'

    connector_id = fields.Many2one(
        'nexora.connector', string='Connector',
        required=True, ondelete='cascade', index=True
    )
    tool_name = fields.Char(
        string='Tool Name', required=True, index=True,
        help='MCP tool/resource/prompt name as returned by the server.'
    )
    description = fields.Text(
        string='Description',
        help='Human-readable description from the MCP server.'
    )
    input_schema_json = fields.Text(
        string='Input Schema (JSON)', default='{}',
        help='Full JSON schema of the tool\'s input parameters.'
    )
    discovery_source = fields.Selection([
        ('tools', 'Tool (tools/list)'),
        ('resources', 'Resource (resources/list)'),
        ('prompts', 'Prompt (prompts/list)'),
    ], string='Discovery Source', required=True, default='tools')
    discovered_at = fields.Datetime(
        string='Discovered At', default=fields.Datetime.now
    )
    raw_schema_json = fields.Text(
        string='Raw Schema (JSON)', default='{}',
        help='Complete raw model_dump() from the MCP SDK for this item.'
    )

    _sql_constraints = [
        ('unique_connector_tool', 'unique(connector_id, discovery_source, tool_name)',
         'Each connector can only have one record per tool name and discovery source.'),
    ]
