# -*- coding: utf-8 -*-
"""
nexora.mcp_server_config — MCP Server Configuration
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Stores operator-defined MCP server connection parameters.
One record per nexora.connector. Secrets are NOT stored here —
they live in nexora.mcp_credential.
"""
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class NexoraMcpServerConfig(models.Model):
    _name = 'nexora.mcp_server_config'
    _description = 'MCP Server Configuration'
    _order = 'connector_id'

    # ------------------------------------------------------------------
    # Parent Connector Link
    # ------------------------------------------------------------------
    connector_id = fields.Many2one(
        'nexora.connector', string='Connector',
        required=True, ondelete='cascade', index=True,
        help='The nexora.connector record this MCP server configuration belongs to.'
    )

    # ------------------------------------------------------------------
    # MCP Process Configuration
    # ------------------------------------------------------------------
    command = fields.Char(
        string='Command', required=True,
        help='Executable to launch (e.g. "npx", "/usr/bin/python"). '
             'Must be an absolute path or resolvable binary name. Never shell-expanded.'
    )
    args_json = fields.Text(
        string='Arguments (JSON)', default='[]',
        help='JSON array of string arguments to pass to the command. '
             'Example: ["@modelcontextprotocol/server-memory"]'
    )
    working_directory = fields.Char(
        string='Working Directory',
        help='Optional working directory for the MCP server process.'
    )
    env_vars_json = fields.Text(
        string='Non-Secret Environment Variables (JSON)', default='{}',
        help='JSON dict of non-secret environment variables to inject into the MCP process. '
             'NEVER store secrets here — use nexora.mcp_credential instead.'
    )

    # ------------------------------------------------------------------
    # Timeout & Startup Policy
    # ------------------------------------------------------------------
    timeout_seconds = fields.Integer(
        string='Request Timeout (s)', default=60,
        help='Maximum seconds to wait for a single MCP request before timeout.'
    )
    startup_policy = fields.Selection([
        ('lazy', 'Lazy (connect on first request)'),
        ('eager', 'Eager (connect at enable)'),
    ], string='Startup Policy', default='lazy', required=True)

    # ------------------------------------------------------------------
    # Computed / Status
    # ------------------------------------------------------------------
    discovered_capabilities_count = fields.Integer(
        string='Discovered Capabilities',
        compute='_compute_discovered_capabilities_count', store=False
    )
    credential_count = fields.Integer(
        string='Credentials Configured',
        compute='_compute_credential_count', store=False
    )

    # ------------------------------------------------------------------
    # Last Test Result (sanitized — never contains secrets)
    # ------------------------------------------------------------------
    last_test_result_json = fields.Text(
        string='Last Test Result (JSON)', default='{}',
        help='Sanitized result from the last "Test Connection" run. Never contains secrets.'
    )
    last_tested_at = fields.Datetime(string='Last Tested At')
    last_test_success = fields.Boolean(
        string='Last Test Succeeded', compute='_compute_last_test_success', store=False
    )

    _sql_constraints = [
        ('unique_connector', 'unique(connector_id)',
         'An MCP connector can only have one server configuration record.'),
    ]

    @api.depends()
    def _compute_discovered_capabilities_count(self):
        for rec in self:
            rec.discovered_capabilities_count = self.env['nexora.mcp_discovered_tool'].search_count(
                [('connector_id', '=', rec.connector_id.id)]
            )

    @api.depends()
    def _compute_credential_count(self):
        for rec in self:
            rec.credential_count = self.env['nexora.mcp_credential'].search_count(
                [('connector_id', '=', rec.connector_id.id)]
            )

    @api.depends('last_test_result_json')
    def _compute_last_test_success(self):
        for rec in self:
            try:
                result = json.loads(rec.last_test_result_json or '{}')
                rec.last_test_success = bool(result.get('success', False))
            except (json.JSONDecodeError, TypeError):
                rec.last_test_success = False

    @api.constrains('args_json')
    def _check_args_json(self):
        for rec in self:
            if rec.args_json:
                try:
                    args = json.loads(rec.args_json)
                    if not isinstance(args, list):
                        raise ValidationError('Arguments must be a JSON array (list of strings).')
                    for arg in args:
                        if not isinstance(arg, str):
                            raise ValidationError(
                                f'All arguments must be strings. Got: {type(arg).__name__}'
                            )
                except json.JSONDecodeError as e:
                    raise ValidationError(f'Arguments JSON is invalid: {e}')

    @api.constrains('env_vars_json')
    def _check_env_vars_json(self):
        for rec in self:
            if rec.env_vars_json:
                try:
                    env = json.loads(rec.env_vars_json)
                    if not isinstance(env, dict):
                        raise ValidationError('Environment variables must be a JSON object (dict).')
                    for k, v in env.items():
                        if not isinstance(k, str) or not isinstance(v, str):
                            raise ValidationError(
                                'All environment variable keys and values must be strings.'
                            )
                except json.JSONDecodeError as e:
                    raise ValidationError(f'Environment Variables JSON is invalid: {e}')

    @api.constrains('command')
    def _check_command(self):
        for rec in self:
            if rec.command and '..' in rec.command:
                raise ValidationError(
                    'Path traversal detected in command. Use absolute paths or binary names only.'
                )

    @api.constrains('timeout_seconds')
    def _check_timeout(self):
        for rec in self:
            if rec.timeout_seconds is not None and rec.timeout_seconds < 1:
                raise ValidationError('Timeout must be at least 1 second.')

    def get_args_list(self):
        """Returns the parsed args as a Python list. Never raises — returns [] on error."""
        self.ensure_one()
        try:
            return json.loads(self.args_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def get_env_vars_dict(self):
        """Returns parsed env vars as a Python dict. Never raises — returns {} on error."""
        self.ensure_one()
        try:
            return json.loads(self.env_vars_json or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}
