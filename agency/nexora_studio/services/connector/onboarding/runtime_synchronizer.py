"""
ConnectorRuntimeSynchronizer — ORM Hook-driven Runtime Sync
============================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Called from nexora.connector ORM write/unlink hooks to keep the
ConnectorRuntime synchronized with Odoo state changes.

Guarantees:
- State change → running: connector is registered and available
- State change → disabled/removed: connector is deregistered, session evicted
- Config update: connector is deregistered then re-registered
- Credential rotation: session evicted, connector re-registered with fresh credentials
- unlink: unconditional cleanup

Uses McpOnboardingService internally — does NOT bypass the pipeline.
"""
from __future__ import annotations

import logging
from typing import Optional

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger

_logger = get_logger(__name__)

# States that mean the connector should be active in the runtime
_RUNNING_STATES = {'running', 'healthy', 'paused'}

# States that mean the connector must be removed from the runtime
_TERMINAL_STATES = {'disabled', 'removed', 'failed'}


class ConnectorRuntimeSynchronizer:
    """
    Bridges Odoo nexora.connector state changes to ConnectorRuntime operations.

    Called from ORM write/unlink hooks — NOT from controllers or business logic.
    Handles only the runtime state; Odoo ORM state is managed by the connector model.
    """

    def __init__(self, onboarding_service):
        """
        Args:
            onboarding_service: McpOnboardingService instance
        """
        self._onboarding = onboarding_service

    def sync_on_write(self, connector_record, previous_state: Optional[str] = None) -> None:
        """
        Called after nexora.connector.write() when state changes.

        Args:
            connector_record: The nexora.connector record after the write
            previous_state: The state before the write (optional)
        """
        current_state = connector_record.state
        connector_id = connector_record.connector_id
        connector_type = connector_record.connector_type_id.type_code if connector_record.connector_type_id else ''

        if connector_type != 'mcp':
            # Only MCP connectors are managed by this synchronizer
            return

        _logger.info(
            "ConnectorRuntimeSynchronizer: state change for '%s': %s → %s",
            connector_id, previous_state, current_state,
            extra={'connector_id': connector_id}
        )

        if current_state in _RUNNING_STATES:
            self._sync_enable(connector_record)
        elif current_state in _TERMINAL_STATES:
            self._sync_disable(connector_id)

    def sync_on_unlink(self, connector_record) -> None:
        """
        Called before nexora.connector.unlink(). Unconditional cleanup.
        """
        connector_id = connector_record.connector_id
        connector_type = connector_record.connector_type_id.type_code if connector_record.connector_type_id else ''
        if connector_type != 'mcp':
            return

        _logger.info(
            "ConnectorRuntimeSynchronizer: connector '%s' deleted — cleaning up runtime.",
            connector_id,
            extra={'connector_id': connector_id}
        )
        self._sync_disable(connector_id)

    def sync_config_update(self, connector_record) -> None:
        """
        Called when the MCP server configuration is updated.
        Deregisters then re-registers the connector to pick up the new config.
        """
        connector_id = connector_record.connector_id
        if connector_record.connector_type_id.type_code != 'mcp':
            return

        _logger.info(
            "ConnectorRuntimeSynchronizer: config updated for '%s' — resyncing runtime.",
            connector_id,
            extra={'connector_id': connector_id}
        )
        self._sync_disable(connector_id)
        if connector_record.state in _RUNNING_STATES:
            self._sync_enable(connector_record)

    def sync_credential_rotation(self, connector_record) -> None:
        """
        Called after credential rotation. Forces session eviction and re-registration
        so the next request uses the new credential.
        """
        connector_id = connector_record.connector_id
        if connector_record.connector_type_id.type_code != 'mcp':
            return

        _logger.info(
            "ConnectorRuntimeSynchronizer: credential rotated for '%s' — evicting session.",
            connector_id,
            extra={'connector_id': connector_id}
        )
        self._sync_disable(connector_id)
        if connector_record.state in _RUNNING_STATES:
            self._sync_enable(connector_record)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sync_enable(self, connector_record) -> None:
        """Register the connector in the runtime."""
        connector_id = connector_record.connector_id
        try:
            # Avoid redundant registration if already fully running
            runtime = self._onboarding._runtime
            if runtime.registry.is_registered(connector_id):
                conn = runtime.registry.get(connector_id)
                if conn and conn.is_running:
                    _logger.debug("ConnectorRuntimeSynchronizer: connector '%s' is already running in runtime, skipping sync.", connector_id)
                    return

            # Ensure no stale registration
            self._sync_disable(connector_id)
            self._onboarding.register_connector(connector_record)
            _logger.info(
                "ConnectorRuntimeSynchronizer: connector '%s' enabled in runtime.",
                connector_id,
                extra={'connector_id': connector_id}
            )
        except Exception as e:
            _logger.error(
                "ConnectorRuntimeSynchronizer: failed to enable connector '%s': %s — %s",
                connector_id, type(e).__name__, str(e),
                extra={'connector_id': connector_id}
            )
            # Update the connector record to failed state
            try:
                connector_record.write({'state': 'failed', 'error_message': str(e)})
            except Exception:
                pass  # Don't cascade failures

    def _sync_disable(self, connector_id: str) -> None:
        """Deregister the connector from the runtime."""
        try:
            self._onboarding.deregister_connector(connector_id)
        except Exception as e:
            _logger.warning(
                "ConnectorRuntimeSynchronizer: deregister failed for '%s': %s",
                connector_id, type(e).__name__,
                extra={'connector_id': connector_id}
            )
