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
    # MCP Process/Endpoint Configuration
    # ------------------------------------------------------------------
    transport_type = fields.Selection([
        ('stdio', 'Standard I/O (Local Process)'),
        ('sse', 'HTTP/SSE (Remote API)'),
    ], string='Transport Type', default='stdio', required=True)

    command = fields.Char(
        string='Command / Endpoint', required=True,
        help='Executable to launch (e.g. "npx") for stdio, or Endpoint URL (e.g. "http://localhost/mcp") for SSE. '
             'For stdio, must be absolute path or resolvable binary. Never shell-expanded.'
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
        help='JSON dict of non-secret environment variables to inject into the MCP process (stdio). '
             'NEVER store secrets here — use nexora.mcp_credential instead.'
    )

    # ------------------------------------------------------------------
    # Generic Authentication Configuration (primarily for SSE)
    # ------------------------------------------------------------------
    # ADR-0071 (C-15): authentication_location is the single declared axis of
    # credential delivery. 'env' = stdio only — the credential is delivered as
    # an environment variable of the child MCP server process, declared in
    # env_vars_json via the reserved placeholder
    # __INJECT_VIA_NEXORA_MCP_CREDENTIAL__.
    authentication_location = fields.Selection([
        ('none', 'None'),
        ('header', 'HTTP Header'),
        ('query', 'Query Parameter'),
        ('env', 'Process Environment (stdio)'),
    ], string='Authentication Location', default='none')

    authentication_name = fields.Char(
        string='Authentication Name',
        help='Name of the header or query parameter (e.g., "Authorization", "userToken", "X-API-Key").'
    )

    authentication_scheme = fields.Selection([
        ('none', 'None'),
        ('bearer', 'Bearer'),
        ('token', 'Token'),
    ], string='Authentication Scheme', default='none',
       help='Prefix used for headers (e.g., "Bearer <secret>").'
    )

    credential_key = fields.Char(
        string='Credential Key Mapping',
        help='Key of the nexora.mcp_credential used for this authentication (e.g., "PENPOT_API_KEY").'
    )
    
    allowed_request_context_fields_json = fields.Text(
        string='Allowed Request Context Fields (JSON)',
        default='[]',
        help='JSON array of strings defining the allowlist of request_context keys '
             'that are permitted to be sent to the MCP server. (e.g. ["userToken"])'
    )

    # ------------------------------------------------------------------
    # Session Binding Configuration
    # ------------------------------------------------------------------
    session_binding = fields.Selection([
        ('none', 'None'),
        ('request_context', 'Request Context'),
    ], string='Session Binding Policy', default='none')

    session_binding_field = fields.Char(
        string='Session Binding Field',
        help='The request context field providing session identity (e.g., "userToken").'
    )

    session_binding_location = fields.Selection([
        ('query', 'Query Parameter'),
        ('header', 'HTTP Header'),
    ], string='Session Binding Location', default='query')

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

    @api.constrains('allowed_request_context_fields_json')
    def _check_allowed_request_context_fields_json(self):
        for rec in self:
            if rec.allowed_request_context_fields_json:
                try:
                    fields_list = json.loads(rec.allowed_request_context_fields_json)
                    if not isinstance(fields_list, list):
                        raise ValidationError('Allowed request context fields must be a JSON array (list of strings).')
                    for field in fields_list:
                        if not isinstance(field, str):
                            raise ValidationError(
                                f'All allowed request context fields must be strings. Got: {type(field).__name__}'
                            )
                except json.JSONDecodeError as e:
                    raise ValidationError(f'Allowed Request Context Fields JSON is invalid: {e}')

    @api.constrains('session_binding', 'session_binding_field', 'allowed_request_context_fields_json')
    def _check_session_binding(self):
        for rec in self:
            if rec.session_binding == 'request_context':
                if not rec.session_binding_field:
                    raise ValidationError('Session Binding Field is required when Session Binding Policy is "Request Context".')
                allowed_fields = rec.get_allowed_request_context_fields_list()
                if rec.session_binding_field not in allowed_fields:
                    raise ValidationError(
                        f"Session Binding Field '{rec.session_binding_field}' must be explicitly listed in Allowed Request Context Fields."
                    )

    @api.constrains('command')
    def _check_command(self):
        for rec in self:
            if rec.command and '..' in rec.command:
                raise ValidationError(
                    'Path traversal detected in command. Use absolute paths or binary names only.'
                )

    @api.constrains('authentication_location', 'transport_type')
    def _check_auth_transport_coherence(self):
        """ADR-0071 (C-15): delivery modes are transport-bound.

        'env' is meaningful only for stdio (credential becomes an environment
        variable of the child process); 'header'/'query' are meaningful only
        for sse (HTTP surfaces). Nonsensical combinations are rejected at write
        time rather than at connect time.
        """
        for rec in self:
            if rec.authentication_location == 'env' and rec.transport_type != 'stdio':
                raise ValidationError(
                    "Authentication location 'env' is only valid for stdio transports."
                )
            if rec.authentication_location in ('header', 'query') and rec.transport_type != 'sse':
                raise ValidationError(
                    "Authentication locations 'header'/'query' are only valid for sse transports."
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

    def get_allowed_request_context_fields_list(self):
        """Returns parsed allowed request context fields as a Python list. Never raises — returns [] on error."""
        self.ensure_one()
        try:
            return json.loads(self.allowed_request_context_fields_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
