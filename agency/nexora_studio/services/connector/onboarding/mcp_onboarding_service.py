"""
McpOnboardingService — Translates Odoo Records → Connector Platform Domain Objects
====================================================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Orchestrates the full onboarding path:
  nexora.mcp_server_config (Odoo ORM)
      → McpConfigurationBuilder    (config + secret injection)
      → ManifestBuilder            (ConnectorManifest)
      → ConnectorRegistrationPipeline (existing, frozen)
      → ConnectorRuntime           (existing, frozen)

Never bypasses the registration pipeline.
Never stores decrypted secrets.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.connectors.mcp.manifest import build_mcp_manifest
from odoo.addons.nexora_studio.services.connector.credentials.odoo_credential_resolver import OdooCredentialResolver
from odoo.addons.nexora_studio.services.connector.domain.models import (
    Connector,
    ConnectorConfiguration,
    ConnectorLifecycleState,
    ConnectorManifest,
)
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from odoo.addons.nexora_studio.services.connector.sdk.version import SDK_VERSION

_logger = get_logger(__name__)

# Default capability namespaces exposed by any MCP connector
_DEFAULT_MCP_CAPABILITIES = ['tools.list', 'tools.call', 'resources.list', 'resources.read',
                              'prompts.list', 'prompts.get']


class McpOnboardingService:
    """
    Central service for onboarding MCP servers through the Universal Connector Platform.

    One McpConnector implementation + N nexora.mcp_server_config records
    = N independently managed MCP servers.
    """

    def __init__(self, runtime, registration_pipeline, odoo_env):
        """
        Args:
            runtime: ConnectorRuntime singleton
            registration_pipeline: ConnectorRegistrationPipeline instance
            odoo_env: Odoo environment (self.env)
        """
        self._runtime = runtime
        self._pipeline = registration_pipeline
        self._env = odoo_env
        self._resolver = OdooCredentialResolver(odoo_env)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_connector(self, connector_record) -> None:
        """
        Register an MCP server connector through the full pipeline.

        Args:
            connector_record: nexora.connector Odoo record with associated
                              nexora.mcp_server_config.
        Raises:
            ConnectorConfigurationError if validation fails.
        """
        connector_id = connector_record.connector_id
        _logger.info(
            "McpOnboardingService: registering connector '%s'.",
            connector_id,
            extra={'connector_id': connector_id}
        )

        mcp_config_record = self._get_mcp_config(connector_record)
        mcp_config = self._build_mcp_configuration(connector_record, mcp_config_record)
        manifest = self._build_manifest(connector_record)
        connector_domain = self._build_connector_domain(manifest, connector_record, mcp_config)

        self._pipeline.execute(connector_domain)
        # Phase 35.4 — Canonical transport initialization and handshake
        try:
            if hasattr(self._runtime, 'dispatcher'):
                from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
                context = ExecutionContext(connector_id=connector_id, request_id='register_init', capability_namespace='init')

                result = self._runtime.dispatcher.initialize_and_verify(connector_domain, context)
                from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionStatus
                if result.status == ConnectorExecutionStatus.FAILURE:
                    raise Exception(result.error)

                # Post-handshake: Capability Discovery
                from odoo.addons.nexora_studio.services.connector.onboarding.capability_discovery import McpCapabilityDiscoveryService
                discovery = McpCapabilityDiscoveryService(self._runtime, self._env)
                discovery.discover(connector_record)

                # Reconcile capabilities in memory
                self._runtime.rebuild_capability_index()

        except Exception as e:
            import traceback
            _logger.error(f"DIAGNOSTIC: register_connector inner exception:\n{traceback.format_exc()}")
            # If handshake or discovery fails, unregister and propagate the error
            self.deregister_connector(connector_id)
            raise ConnectorConfigurationError(
                error_code='HANDSHAKE_FAILED',
                user_safe_message=f"Connector '{connector_record.name}' failed to initialize or handshake.",
                technical_message=str(e)
            )

        _logger.info(
            "McpOnboardingService: connector '%s' registered and verified successfully.",
            connector_id,
            extra={'connector_id': connector_id}
        )

    def deregister_connector(self, connector_id: str) -> None:
        """Deregister a connector from the runtime. Evicts any cached session."""
        try:
            self._runtime.unregister_connector(connector_id)
            _logger.info(
                "McpOnboardingService: connector '%s' deregistered.",
                connector_id,
                extra={'connector_id': connector_id}
            )
        except (KeyError, Exception) as e:
            _logger.warning(
                "McpOnboardingService: deregister called for unknown connector '%s'. "
                "May already be removed: %s",
                connector_id, type(e).__name__,
                extra={'connector_id': connector_id}
            )

    def set_credential(self, connector_id: str, credential_key: str, value: str) -> None:
        """
        Store an encrypted credential for a connector.
        Never logs the value.
        """
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
        provider = OdooSecretsProvider(env=self._env)
        composite_key = f"{connector_id}:{credential_key}"
        provider.set_secret(composite_key, value)
        _logger.info(
            "McpOnboardingService: credential '%s' set for connector '%s'.",
            credential_key, connector_id,
            extra={'connector_id': connector_id}
        )

    def rotate_credential(self, connector_id: str, credential_key: str, new_value: str) -> None:
        """
        Rotate a credential — re-encrypt with new value and evict the cached session
        so the next request picks up the new credential.
        """
        self.set_credential(connector_id, credential_key, new_value)
        # Evict session so new credential is picked up
        self._evict_session(connector_id)
        _logger.info(
            "McpOnboardingService: credential '%s' rotated for connector '%s'. "
            "Session evicted for fresh connection.",
            credential_key, connector_id,
            extra={'connector_id': connector_id}
        )

    def delete_credential(self, connector_id: str, credential_key: str) -> None:
        """Delete a credential and evict the cached session."""
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
        provider = OdooSecretsProvider(env=self._env)
        composite_key = f"{connector_id}:{credential_key}"
        provider.delete_secret(composite_key)
        self._evict_session(connector_id)
        _logger.info(
            "McpOnboardingService: credential '%s' deleted for connector '%s'.",
            credential_key, connector_id,
            extra={'connector_id': connector_id}
        )

    # ------------------------------------------------------------------
    # Internal Builders
    # ------------------------------------------------------------------

    def _get_mcp_config(self, connector_record):
        """Fetch the nexora.mcp_server_config record for the connector. Raises if missing."""
        mcp_config = self._env['nexora.mcp_server_config'].search(
            [('connector_id', '=', connector_record.id)], limit=1
        )
        if not mcp_config:
            raise ConnectorConfigurationError(
                error_code='MCP_CONFIG_MISSING',
                user_safe_message=f"Connector '{connector_record.name}' has no MCP server configuration.",
                technical_message=f"No nexora.mcp_server_config found for connector_id={connector_record.connector_id}"
            )
        return mcp_config

    def _build_mcp_configuration(self, connector_record, mcp_config_record) -> McpConfiguration:
        """
        Build McpConfiguration from Odoo records.
        Injects decrypted secrets into env dict — never persists them.
        """
        connector_id = connector_record.connector_id

        # Non-secret env vars from config record
        env_vars = mcp_config_record.get_env_vars_dict()

        # Resolve encrypted credentials and merge into env
        resolved_secrets = self._resolver.resolve_all_for_connector(connector_id)
        env_vars.update(resolved_secrets)
        # resolved_secrets dict goes out of scope here after merge — not retained

        return McpConfiguration(
            command=mcp_config_record.command,
            args=mcp_config_record.get_args_list(),
            env=env_vars if env_vars else None,
        )

    def _build_manifest(self, connector_record) -> ConnectorManifest:
        """Build a ConnectorManifest from the nexora.connector Odoo record."""
        return build_mcp_manifest(
            connector_id=connector_record.connector_id,
            display_name=connector_record.name,
            capabilities=_DEFAULT_MCP_CAPABILITIES,
            version=connector_record.version or '1.0.0',
        )

    def _build_connector_domain(
        self,
        manifest: ConnectorManifest,
        connector_record,
        mcp_config: McpConfiguration,
    ) -> Connector:
        """
        Build a Connector domain aggregate from manifest and configuration.

        The McpConfiguration (command, args, env) is stored in
        ConnectorConfiguration.current_values so the ConnectorFactory/Dispatcher
        can retrieve it when creating the concrete McpConnector instance at
        dispatch time.

        NOTE: Decrypted env vars are injected into current_values['env'] here.
        They exist only in-process for the duration of this call.
        The Connector aggregate returned does NOT persist secrets — it only
        holds config values sufficient for the factory to construct McpConnector.
        """
        from dataclasses import field as dc_field

        # Store mcp_config in connector configuration so the factory can build
        # the live McpConnector instance during dispatch.
        # env dict may contain resolved secrets — kept in-process only.
        config = ConnectorConfiguration(
            connector_id=manifest.connector_id,
            user_overrides={
                'command': mcp_config.command,
                'args': mcp_config.args,
                'env': mcp_config.env or {},
            }
        )

        return Connector(
            manifest=manifest,
            lifecycle_state=ConnectorLifecycleState.RUNNING,
            configuration=config,
        )


    def _evict_session(self, connector_id: str) -> None:
        """Evict the cached connector session from the dispatcher."""
        try:
            if hasattr(self._runtime, 'dispatcher'):
                self._runtime.dispatcher.shutdown_connector(connector_id)
                _logger.info(
                    "McpOnboardingService: session evicted for connector '%s'.", connector_id,
                    extra={'connector_id': connector_id}
                )
        except Exception as e:
            _logger.warning(
                "McpOnboardingService: session eviction failed for '%s': %s",
                connector_id, type(e).__name__,
                extra={'connector_id': connector_id}
            )
