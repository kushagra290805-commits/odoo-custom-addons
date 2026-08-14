"""
OdooCredentialResolver — Resolves MCP Connector Credentials for Runtime Injection
==================================================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Implements the CredentialResolver ABC (ADR-0050, Phase 26).

Resolves ConnectorCredentialReferences into dict of env vars for McpConfiguration.env.
Decrypted values are returned only within the scope of a single dispatch — never cached,
never logged, never persisted.
"""
from __future__ import annotations

import logging
from typing import Dict

from odoo.addons.nexora_studio.services.connector.credentials.interfaces import (
    CredentialResolver,
    CredentialValidationResult,
)
from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
from odoo.addons.nexora_studio.services.connector.domain.models import (
    ConnectorCredentialReference,
    ConnectorRuntimeContext,
)

_logger = logging.getLogger(__name__)


class OdooCredentialResolver(CredentialResolver):
    """
    Resolves ConnectorCredentialReferences to env var dicts for McpConfiguration.env injection.

    Key format used with OdooSecretsProvider: "<connector_id>:<credential_key>"

    Security:
    - Decrypted values returned in-process only within dict — never logged
    - Never persisted to any model field
    - If a credential is missing and is_required=True, raises RuntimeError
    """

    def __init__(self, env):
        self._secrets = OdooSecretsProvider(env=env)

    def resolve(
        self,
        reference: ConnectorCredentialReference,
        context: ConnectorRuntimeContext,
    ) -> Dict[str, str]:
        """
        Resolve a credential reference to a dict suitable for injection into McpConfiguration.env.

        Returns:
            Dict[str, str] — {credential_key: decrypted_value}
        """
        connector_id = context.connector_id
        composite_key = f"{connector_id}:{reference.credential_key}"

        if not self._secrets.has_secret(composite_key):
            if reference.is_required:
                raise RuntimeError(
                    f"Required credential '{reference.credential_key}' is not set "
                    f"for connector '{connector_id}'."
                )
            _logger.warning(
                "OdooCredentialResolver: optional credential '%s' not set for connector '%s'.",
                reference.credential_key, connector_id
            )
            return {}

        # Decrypted value obtained — never logged beyond this point
        decrypted = self._secrets.get_secret(composite_key)
        _logger.debug(
            "OdooCredentialResolver: resolved credential key='%s' for connector='%s'.",
            reference.credential_key, connector_id
        )
        return {reference.credential_key: decrypted}

    def validate(
        self,
        reference: ConnectorCredentialReference,
    ) -> CredentialValidationResult:
        """
        Validate that a credential reference can be resolved without decrypting.
        Returns CredentialValidationResult — does NOT make external calls.
        """
        # We need the connector_id to form the composite key — but this interface
        # doesn't take a context. We use a prefix search to check existence.
        suffix = f":{reference.credential_key}"
        all_keys = self._secrets.list_keys()
        found = any(k.endswith(suffix) for k in all_keys)

        if found:
            return CredentialValidationResult(
                valid=True,
                credential_key=reference.credential_key
            )
        if reference.is_required:
            return CredentialValidationResult(
                valid=False,
                credential_key=reference.credential_key,
                error=f"Required credential '{reference.credential_key}' is not set."
            )
        return CredentialValidationResult(
            valid=True,
            credential_key=reference.credential_key,
            metadata={'optional': True, 'is_set': False}
        )

    def resolve_all_for_connector(self, connector_id: str) -> Dict[str, str]:
        """
        Resolve ALL credentials for a connector into a single env var dict.
        Used by McpOnboardingService to populate McpConfiguration.env.
        Never logs values.
        """
        prefix = connector_id
        keys = self._secrets.list_keys(prefix=prefix)
        result = {}
        for composite_key in keys:
            _, credential_key = composite_key.split(':', 1)
            try:
                value = self._secrets.get_secret(composite_key)
                result[credential_key] = value
            except Exception as e:
                _logger.warning(
                    "OdooCredentialResolver: failed to resolve key='%s' for connector='%s': %s",
                    credential_key, connector_id, type(e).__name__
                )
        return result
