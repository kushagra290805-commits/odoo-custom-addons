# -*- coding: utf-8 -*-
"""
nexora.mcp_credential — Encrypted MCP Connector Credentials
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Stores Fernet-encrypted secrets (API keys, tokens, env var secrets) for MCP connectors.
The encryption master key MUST be provided via the NEXORA_CONNECTOR_SECRET_KEY
environment variable. It is NEVER stored in the database.

Security guarantees:
- encrypted_value is never returned in any API response or log
- ORM reads expose only: is_set (bool), display_hint (masked string)
- Decryption only through OdooSecretsProvider.get_secret()
"""
import logging
import os
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)


class NexoraMcpCredential(models.Model):
    _name = 'nexora.mcp_credential'
    _description = 'MCP Connector Credential'
    _order = 'connector_id, credential_key'

    # ------------------------------------------------------------------
    # Parent Connector Link
    # ------------------------------------------------------------------
    connector_id = fields.Many2one(
        'nexora.connector', string='Connector',
        required=True, ondelete='cascade', index=True
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    credential_key = fields.Char(
        string='Credential Key', required=True, index=True,
        help='Environment variable name or config key this secret maps to. '
             'Example: GITHUB_TOKEN, OPENAI_API_KEY'
    )
    credential_type = fields.Selection([
        ('api_key', 'API Key'),
        ('bearer_token', 'Bearer Token'),
        ('env_var', 'Environment Variable Secret'),
        ('oauth2_token', 'OAuth2 Token'),
        ('custom', 'Custom'),
    ], string='Credential Type', required=True, default='api_key')
    description = fields.Char(
        string='Description',
        help='Human-readable description of what this credential is for.'
    )

    # ------------------------------------------------------------------
    # Encrypted Storage (WRITE-ONLY from API perspective)
    # ------------------------------------------------------------------
    encrypted_value = fields.Text(
        string='Encrypted Value',
        groups='nexora_studio.group_nexora_super_admin',
        help='Fernet-encrypted credential value. '
             'NEVER read this field directly — use OdooSecretsProvider.get_secret().'
    )

    # ------------------------------------------------------------------
    # Safe Read-Only Fields
    # ------------------------------------------------------------------
    is_set = fields.Boolean(
        string='Is Set', compute='_compute_is_set', store=True,
        help='True if a credential value has been stored.'
    )
    display_hint = fields.Char(
        string='Value Hint', compute='_compute_display_hint', store=False,
        help='Masked hint showing only the last 4 characters. Never the full value.'
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    last_rotated_at = fields.Datetime(string='Last Rotated At')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)

    _sql_constraints = [
        ('unique_connector_key', 'unique(connector_id, credential_key)',
         'Each connector can only have one credential per key.'),
    ]

    @api.depends('encrypted_value')
    def _compute_is_set(self):
        for rec in self:
            rec.is_set = bool(rec.encrypted_value and rec.encrypted_value.strip())

    def _compute_display_hint(self):
        """
        Returns only the last 4 chars of the DECRYPTED value as a hint.
        This requires a decryption step — only performed if the key is available.
        If key unavailable or value not set, returns '****'.
        """
        for rec in self:
            if not rec.is_set:
                rec.display_hint = '(not set)'
                continue
            try:
                from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import (
                    OdooSecretsProvider
                )
                provider = OdooSecretsProvider()
                raw_key = f"{rec.connector_id.connector_id}:{rec.credential_key}"
                # We intentionally only decrypt to get the hint — never store/log the value
                secret = provider.get_secret_from_blob(rec.encrypted_value)
                hint = f"****{secret[-4:]}" if len(secret) >= 4 else "****"
                rec.display_hint = hint
            except Exception:
                # Key not available or decryption failed — show generic mask
                rec.display_hint = '****'

    @api.constrains('credential_key')
    def _check_credential_key(self):
        for rec in self:
            if not rec.credential_key or not rec.credential_key.strip():
                raise ValidationError('Credential key cannot be empty.')
            # Keys should be valid env var names (uppercase alphanum + underscore)
            import re
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', rec.credential_key):
                raise ValidationError(
                    f'Credential key "{rec.credential_key}" must be a valid '
                    f'identifier (letters, digits, underscores only).'
                )

    @api.model_create_multi
    def create(self, vals_list):
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
        # Determine if we can instantiate safely without an explicit env (it picks up self.env anyway)
        provider = OdooSecretsProvider(env=self.env)
        for vals in vals_list:
            if 'encrypted_value' in vals and vals['encrypted_value']:
                # Encrypt if it doesn't look like Fernet ciphertext (which starts with gAAAAA)
                if not vals['encrypted_value'].startswith('gAAAAA'):
                    vals['encrypted_value'] = provider._encrypt(vals['encrypted_value'])
        
        records = super().create(vals_list)
        for rec in records:
            _logger.info(
                "nexora.mcp_credential: credential '%s' CREATED for connector '%s'. Audit: user=%s",
                rec.credential_key, rec.connector_id.connector_id, self.env.user.name
            )
            self._sync_credential_change(rec)
        return records

    def write(self, vals):
        """Encrypt plain text values and log credential rotation without logging the value."""
        if 'encrypted_value' in vals and vals['encrypted_value']:
            from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
            provider = OdooSecretsProvider(env=self.env)
            if not vals['encrypted_value'].startswith('gAAAAA'):
                vals['encrypted_value'] = provider._encrypt(vals['encrypted_value'])

            for rec in self:
                _logger.info(
                    "nexora.mcp_credential: credential '%s' updated for connector '%s'. "
                    "Audit: user=%s, timestamp=%s",
                    rec.credential_key,
                    rec.connector_id.connector_id,
                    self.env.user.name,
                    datetime.utcnow().isoformat()
                )
            vals['last_rotated_at'] = fields.Datetime.now()
        
        res = super().write(vals)
        if 'encrypted_value' in vals:
            for rec in self:
                self._sync_credential_change(rec)
        return res

    def _sync_credential_change(self, rec):
        """Phase 29.6 — Credential changes must trigger runtime synchronization"""
        try:
            connector_type = rec.connector_id.connector_type_id.type_code if rec.connector_id.connector_type_id else ''
            if connector_type == 'mcp':
                from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
                runtime = get_connector_runtime()
                if runtime:
                    from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                    from odoo.addons.nexora_studio.services.connector.onboarding.runtime_synchronizer import ConnectorRuntimeSynchronizer
                    onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, self.env)
                    synchronizer = ConnectorRuntimeSynchronizer(onboarding)
                    synchronizer.sync_credential_rotation(rec.connector_id)
        except Exception as e:
            _logger.warning("Failed to sync credential change for %s: %s", rec.connector_id.connector_id, e)

    def unlink(self):
        """Log credential deletion without logging the value, and sync runtime."""
        for rec in self:
            _logger.info(
                "nexora.mcp_credential: credential '%s' DELETED for connector '%s'. "
                "User=%s",
                rec.credential_key,
                rec.connector_id.connector_id,
                self.env.user.name
            )
            # Phase 29.6 — Credential deletion must trigger runtime eviction
            try:
                connector_type = rec.connector_id.connector_type_id.type_code if rec.connector_id.connector_type_id else ''
                if connector_type == 'mcp':
                    from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
                    runtime = get_connector_runtime()
                    if runtime:
                        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                        from odoo.addons.nexora_studio.services.connector.onboarding.runtime_synchronizer import ConnectorRuntimeSynchronizer
                        onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, self.env)
                        synchronizer = ConnectorRuntimeSynchronizer(onboarding)
                        synchronizer.sync_credential_rotation(rec.connector_id)
            except Exception as e:
                _logger.warning("Failed to sync credential deletion for %s: %s", rec.connector_id.connector_id, e)
                
        return super().unlink()
