"""
Connector Onboarding API Controller
=====================================
Phase 28 — MCP Connector Onboarding Platform (ADR-0051).

Exposes HTTP endpoints for the UI to:
- Test an MCP server connection (ephemeral, no permanent registration)
- Enable an MCP connector (register in runtime)
- Disable an MCP connector (deregister + session eviction)
- Get connector runtime status

Architecture rules:
- NEVER bypasses ConnectorRuntime, ConnectorRegistry, or ConnectorDispatcher.
- All operations route through McpOnboardingService or McpConnectionTester.
- Credential values are NEVER returned in any response.
- All error responses use user-safe messages only.
"""
from __future__ import annotations

import json
import logging

try:
    from odoo import http
    from odoo.http import request
    _ODOO_AVAILABLE = True
except ImportError:
    # Running outside Odoo (unit test environment)
    http = None
    request = None
    _ODOO_AVAILABLE = False

_logger = logging.getLogger(__name__)


def _json_response(data: dict, status: int = 200):
    """Return a JSON response with the given data and HTTP status code."""
    return request.make_response(
        json.dumps(data),
        headers=[('Content-Type', 'application/json')],
        status=status,
    )


def _error_response(message: str, code: str, status: int = 400):
    """Return a standardized error JSON response. Never includes secrets."""
    return _json_response({
        'success': False,
        'error': {'code': code, 'message': message},
    }, status=status)


if _ODOO_AVAILABLE:

    class ConnectorOnboardingController(http.Controller):
        """
        HTTP API for MCP Connector Onboarding operations.

        All endpoints require user authentication (auth='user').
        Administrative actions require 'nexora_studio.group_nexora_admin'.
        Credential actions require 'nexora_studio.group_nexora_super_admin'.
        Credential values are never returned in any response.
        """

        def _require_admin(self):
            """Raise Forbidden if user is not in group_nexora_admin."""
            from odoo.exceptions import AccessError
            if not request.env.user.has_group('nexora_studio.group_nexora_admin'):
                raise AccessError("Administrator privileges required for this action.")

        def _require_super_admin(self):
            """Raise Forbidden if user is not in group_nexora_super_admin."""
            from odoo.exceptions import AccessError
            if not request.env.user.has_group('nexora_studio.group_nexora_super_admin'):
                raise AccessError("Super Administrator privileges required for this action.")

        # ------------------------------------------------------------------
        # Connection Test
        # ------------------------------------------------------------------

        @http.route(
            '/nexora/connector/<int:connector_id>/test',
            type='http',
            auth='user',
            methods=['POST'],
            csrf=False,
        )
        def test_connector(self, connector_id: int, **kwargs):
            """
            POST /nexora/connector/<id>/test

            Runs an ephemeral connection test against the MCP server.
            Never modifies the live registry or session cache.

            Returns:
                {
                  "success": true/false,
                  "latency_ms": float,
                  "tool_count": int,
                  "resource_count": int,
                  "prompt_count": int,
                  "error_message": str,
                  "tested_at": str
                }
            """
            self._require_admin()

            connector_record = request.env['nexora.connector'].browse(connector_id)
            if not connector_record.exists():
                return _error_response(
                    f"Connector {connector_id} not found.",
                    'CONNECTOR_NOT_FOUND',
                    status=404,
                )

            try:
                from odoo.addons.nexora_studio.services.connector.onboarding.connection_tester import McpConnectionTester
                from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService

                def onboarding_factory(rt, pipeline, env):
                    return McpOnboardingService(rt, pipeline, env)

                tester = McpConnectionTester(
                    onboarding_service_factory=onboarding_factory,
                    odoo_env=request.env,
                )
                result = tester.test(connector_record)

                return _json_response({
                    'success': result.success,
                    'latency_ms': result.latency_ms,
                    'tool_count': result.tool_count,
                    'resource_count': result.resource_count,
                    'prompt_count': result.prompt_count,
                    'server_info': result.server_info,
                    'error_message': result.error_message,
                    'error_code': result.error_code,
                    'tested_at': result.tested_at,
                })

            except Exception as exc:
                _logger.error(
                    "ConnectorOnboardingController.test_connector: error for connector %s: %s",
                    connector_id, exc,
                )
                return _error_response(
                    "Connection test failed due to an internal error. Please check server logs.",
                    'INTERNAL_ERROR',
                    status=500,
                )

        # ------------------------------------------------------------------
        # Enable (Register in Runtime)
        # ------------------------------------------------------------------

        @http.route(
            '/nexora/connector/<int:connector_id>/enable',
            type='http',
            auth='user',
            methods=['POST'],
            csrf=False,
        )
        def enable_connector(self, connector_id: int, **kwargs):
            """
            POST /nexora/connector/<id>/enable

            Registers the MCP connector in the live ConnectorRuntime.
            Sets the connector record state to 'running'.

            Returns:
                {"success": true, "connector_id": "...", "state": "running"}
            """
            self._require_admin()

            connector_record = request.env['nexora.connector'].browse(connector_id)
            if not connector_record.exists():
                return _error_response(
                    f"Connector {connector_id} not found.",
                    'CONNECTOR_NOT_FOUND',
                    status=404,
                )

            try:
                from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime

                runtime = get_connector_runtime()
                pipeline = runtime.registration_pipeline

                onboarding = McpOnboardingService(runtime, pipeline, request.env)
                onboarding.register_connector(connector_record)

                # Update Odoo record state
                connector_record.write({
                    'state': 'running',
                    'health_status': 'unknown',
                })

                _logger.info(
                    "ConnectorOnboardingController: connector '%s' enabled.",
                    connector_record.connector_id,
                )

                return _json_response({
                    'success': True,
                    'connector_id': connector_record.connector_id,
                    'state': 'running',
                })

            except Exception as exc:
                _logger.error(
                    "ConnectorOnboardingController.enable_connector: failed for %s: %s",
                    connector_id, exc,
                )
                return _error_response(
                    "Failed to enable connector. Check configuration and server logs.",
                    'ENABLE_FAILED',
                    status=500,
                )

        # ------------------------------------------------------------------
        # Disable (Deregister from Runtime)
        # ------------------------------------------------------------------

        @http.route(
            '/nexora/connector/<int:connector_id>/disable',
            type='http',
            auth='user',
            methods=['POST'],
            csrf=False,
        )
        def disable_connector(self, connector_id: int, **kwargs):
            """
            POST /nexora/connector/<id>/disable

            Deregisters the MCP connector from the live ConnectorRuntime
            and evicts any cached sessions.

            Returns:
                {"success": true, "connector_id": "...", "state": "disabled"}
            """
            self._require_admin()

            connector_record = request.env['nexora.connector'].browse(connector_id)
            if not connector_record.exists():
                return _error_response(
                    f"Connector {connector_id} not found.",
                    'CONNECTOR_NOT_FOUND',
                    status=404,
                )

            try:
                from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime

                runtime = get_connector_runtime()
                pipeline = runtime.registration_pipeline

                onboarding = McpOnboardingService(runtime, pipeline, request.env)
                onboarding.deregister_connector(connector_record.connector_id)

                # Update Odoo record state
                connector_record.write({'state': 'disabled'})

                _logger.info(
                    "ConnectorOnboardingController: connector '%s' disabled.",
                    connector_record.connector_id,
                )

                return _json_response({
                    'success': True,
                    'connector_id': connector_record.connector_id,
                    'state': 'disabled',
                })

            except Exception as exc:
                _logger.error(
                    "ConnectorOnboardingController.disable_connector: failed for %s: %s",
                    connector_id, exc,
                )
                return _error_response(
                    "Failed to disable connector. Check server logs.",
                    'DISABLE_FAILED',
                    status=500,
                )

        # ------------------------------------------------------------------
        # Runtime Status
        # ------------------------------------------------------------------

        @http.route(
            '/nexora/connector/<int:connector_id>/status',
            type='http',
            auth='user',
            methods=['GET'],
            csrf=False,
        )
        def connector_status(self, connector_id: int, **kwargs):
            """
            GET /nexora/connector/<id>/status

            Returns the current runtime status of a connector.
            Never returns credential values.

            Returns:
                {
                  "connector_id": str,
                  "is_registered": bool,
                  "lifecycle_state": str,
                  "health_status": str,
                  "odoo_state": str
                }
            """
            connector_record = request.env['nexora.connector'].browse(connector_id)
            if not connector_record.exists():
                return _error_response(
                    f"Connector {connector_id} not found.",
                    'CONNECTOR_NOT_FOUND',
                    status=404,
                )

            try:
                from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime

                runtime = get_connector_runtime()
                cid = connector_record.connector_id
                registered = runtime.registry.get(cid)

                return _json_response({
                    'success': True,
                    'connector_id': cid,
                    'is_registered': registered is not None,
                    'lifecycle_state': registered.lifecycle_state.value if registered else 'unregistered',
                    'health_status': (
                        registered.health.status.value
                        if registered and registered.health
                        else 'unknown'
                    ),
                    'odoo_state': connector_record.state,
                })

            except Exception as exc:
                _logger.error(
                    "ConnectorOnboardingController.connector_status: failed for %s: %s",
                    connector_id, exc,
                )
                return _error_response(
                    "Could not retrieve connector status. Check server logs.",
                    'STATUS_ERROR',
                    status=500,
                )

        # ------------------------------------------------------------------
        # Runtime Overview
        # ------------------------------------------------------------------

        @http.route(
            '/nexora/connectors/runtime_status',
            type='http',
            auth='user',
            methods=['GET'],
            csrf=False,
        )
        def runtime_status_overview(self, **kwargs):
            """
            GET /nexora/connectors/runtime_status

            Returns a high-level overview of all registered connectors
            in the live ConnectorRuntime.
            Never returns credential values.

            Returns:
                {
                  "total_registered": int,
                  "running": int,
                  "connectors": [{"connector_id": str, "state": str, "health": str}]
                }
            """
            self._require_admin()

            try:

                from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime

                runtime = get_connector_runtime()
                all_connectors = runtime.registry.get_all()

                connector_list = []
                for conn in all_connectors:
                    connector_list.append({
                        'connector_id': conn.connector_id,
                        'display_name': conn.manifest.display_name if conn.manifest else '',
                        'state': conn.lifecycle_state.value,
                        'health': (
                            conn.health.status.value
                            if conn.health
                            else 'unknown'
                        ),
                    })

                running_count = sum(
                    1 for c in all_connectors
                    if c.lifecycle_state.value == 'running'
                )

                return _json_response({
                    'success': True,
                    'total_registered': len(all_connectors),
                    'running': running_count,
                    'connectors': connector_list,
                })

            except Exception as exc:
                _logger.error(
                    "ConnectorOnboardingController.runtime_status_overview: %s", exc
                )
                return _error_response(
                    "Could not retrieve runtime status. Check server logs.",
                    'RUNTIME_STATUS_ERROR',
                    status=500,
                )
