"""
OdooSecretsProvider — Fernet-Encrypted Secrets for Odoo-backed MCP Connectors
===============================================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Implements the SecretsProvider ABC (ADR-0050, Phase 26) using:
- nexora.mcp_credential Odoo model for encrypted storage
- Fernet symmetric encryption keyed from NEXORA_CONNECTOR_SECRET_KEY env var

Security guarantees:
- The master key is NEVER stored in the database
- Decrypted values are NEVER logged
- Decrypted values are NEVER returned from ORM reads
- The only authorized decryption path is get_secret()

Environment variable: NEXORA_CONNECTOR_SECRET_KEY
Format: URL-safe base64-encoded 32-byte key (Fernet key format)
Generation: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import base64
import logging
import os
from typing import List

from odoo.addons.nexora_studio.services.connector.credentials.interfaces import SecretsProvider
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError

_logger = logging.getLogger(__name__)

_ENV_VAR_NAME = 'NEXORA_CONNECTOR_SECRET_KEY'


def _get_fernet():
    """
    Load and return a Fernet instance using the master key from the environment.
    Raises ConfigurationError if the key is missing or invalid.
    The key is NEVER cached at module level — loaded fresh per call to prevent
    stale key references after rotation.
    """
    try:
        from cryptography.fernet import Fernet, InvalidToken  # noqa: F401
    except ImportError:
        raise ConnectorConfigurationError(
            error_code='CRYPTO_NOT_INSTALLED',
            user_safe_message='The cryptography package is not installed.',
            technical_message=(
                'Install the cryptography package: pip install cryptography'
            )
        )

    from odoo.tools import config
    
    # Phase 28/29: Canonical resolution order: Odoo config -> Environment
    raw_key = config.get('nexora_connector_secret_key')
    if not raw_key:
        raw_key = os.environ.get(_ENV_VAR_NAME)
        
    if not raw_key:
        raise ConnectorConfigurationError(
            error_code='SECRET_KEY_MISSING',
            user_safe_message=(
                'The MCP connector secret key is not configured. '
                'Contact your system administrator.'
            ),
            technical_message=(
                f'Secret key missing. Ensure nexora_connector_secret_key is set in '
                f'odoo.conf or environment variable {_ENV_VAR_NAME} is set. '
                f'Generate a key with: python -c "from cryptography.fernet import Fernet; '
                f'print(Fernet.generate_key().decode())"'
            )
        )

    try:
        return Fernet(raw_key.encode())
    except Exception as e:
        raise ConnectorConfigurationError(
            error_code='SECRET_KEY_INVALID',
            user_safe_message='The MCP connector secret key is invalid.',
            technical_message=f'Fernet key validation failed: {type(e).__name__}'
        )


class OdooSecretsProvider(SecretsProvider):
    """
    SecretsProvider implementation backed by nexora.mcp_credential Odoo model.

    Key scheme: "<connector_id>:<credential_key>"
    Example: "com.nexora.github:GITHUB_TOKEN"

    All values are Fernet-encrypted before persistence.
    The master encryption key is sourced from NEXORA_CONNECTOR_SECRET_KEY env var.
    """

    def __init__(self, env=None):
        """
        Args:
            env: Odoo environment (self.env in a model). If None, relies on caller
                 to pass the Odoo env via get_secret_with_env() etc.
        """
        self._env = env

    def _get_env(self):
        if self._env is None:
            raise RuntimeError(
                'OdooSecretsProvider requires an Odoo environment. '
                'Instantiate with env=self.env.'
            )
        return self._env

    # ------------------------------------------------------------------
    # SecretsProvider ABC Implementation
    # ------------------------------------------------------------------

    def get_secret(self, key: str) -> str:
        """
        Retrieve and decrypt a secret by its full key ("<connector_id>:<credential_key>").
        Raises KeyError if not found. Never logs the decrypted value.
        """
        connector_id, credential_key = self._parse_key(key)
        record = self._find_credential(connector_id, credential_key)
        if not record or not record.encrypted_value:
            raise KeyError(f'Secret not found: connector={connector_id}, key={credential_key}')
        return self.get_secret_from_blob(record.encrypted_value)

    def set_secret(self, key: str, value: str) -> None:
        """
        Encrypt and store a secret. Creates or updates the nexora.mcp_credential record.
        Never logs the value.
        """
        if not value:
            raise ValueError('Secret value cannot be empty.')
        connector_id, credential_key = self._parse_key(key)
        encrypted = self._encrypt(value)

        env = self._get_env()
        connector = env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
        if not connector:
            raise KeyError(f'Connector not found: {connector_id}')

        existing = self._find_credential(connector_id, credential_key)
        if existing:
            existing.with_context(skip_sync=True).write({'encrypted_value': encrypted})
        else:
            env['nexora.mcp_credential'].create({
                'connector_id': connector.id,
                'credential_key': credential_key,
                'encrypted_value': encrypted,
            })
        _logger.info(
            "OdooSecretsProvider: secret set for connector='%s', key='%s'.",
            connector_id, credential_key
        )

    def delete_secret(self, key: str) -> None:
        """Delete a secret. No-op if not found. Never logs the value."""
        connector_id, credential_key = self._parse_key(key)
        record = self._find_credential(connector_id, credential_key)
        if record:
            record.unlink()
            _logger.info(
                "OdooSecretsProvider: secret deleted for connector='%s', key='%s'.",
                connector_id, credential_key
            )

    def list_keys(self, prefix: str = '') -> List[str]:
        """
        List all secret keys, optionally filtered by prefix.
        Returns full composite keys: "<connector_id>:<credential_key>".
        Never returns values.
        """
        env = self._get_env()
        domain = []
        if prefix:
            # prefix is expected to be "<connector_id>" or "<connector_id>:<key_prefix>"
            if ':' in prefix:
                connector_id, key_prefix = prefix.split(':', 1)
                domain = [
                    ('connector_id.connector_id', '=', connector_id),
                    ('credential_key', 'like', key_prefix + '%'),
                ]
            else:
                domain = [('connector_id.connector_id', '=', prefix)]

        records = env['nexora.mcp_credential'].search(domain)
        return [f"{r.connector_id.connector_id}:{r.credential_key}" for r in records]

    def has_secret(self, key: str) -> bool:
        """Returns True if the key exists and has a non-empty encrypted value."""
        connector_id, credential_key = self._parse_key(key)
        record = self._find_credential(connector_id, credential_key)
        return bool(record and record.is_set)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_secret_from_blob(self, encrypted_blob: str) -> str:
        """
        Decrypt a raw encrypted blob. Used for display_hint computation.
        Never logs the result.
        """
        return self._decrypt(encrypted_blob)

    def _encrypt(self, value: str) -> str:
        """Fernet-encrypt a value. Returns URL-safe base64 string."""
        f = _get_fernet()
        return f.encrypt(value.encode()).decode()

    def _decrypt(self, blob: str) -> str:
        """Fernet-decrypt an encrypted blob. Raises on invalid token."""
        from cryptography.fernet import InvalidToken
        f = _get_fernet()
        try:
            return f.decrypt(blob.encode()).decode()
        except InvalidToken:
            raise RuntimeError(
                'Failed to decrypt credential. The master key may have changed. '
                'Re-enter the credential or rotate with the new key.'
            )

    def _parse_key(self, key: str):
        """Parse "<connector_id>:<credential_key>" into (connector_id, credential_key)."""
        if ':' not in key:
            raise ValueError(
                f'Invalid secret key format: "{key}". '
                f'Expected "<connector_id>:<credential_key>".'
            )
        parts = key.split(':', 1)
        return parts[0], parts[1]

    def _find_credential(self, connector_id: str, credential_key: str):
        """Find a nexora.mcp_credential record by connector_id + key. Returns None if not found."""
        env = self._get_env()
        return env['nexora.mcp_credential'].search([
            ('connector_id.connector_id', '=', connector_id),
            ('credential_key', '=', credential_key),
        ], limit=1) or None
