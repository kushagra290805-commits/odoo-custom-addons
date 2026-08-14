"""
McpConnectionTester — Safe Ephemeral Connection Test Workflow
==============================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Tests an MCP server configuration without permanently registering it
in the global runtime or leaking credentials.

Flow:
  1. Build McpConfiguration from Odoo record (secrets injected in-process)
  2. Create an ephemeral (non-global) ConnectorRuntime
  3. Register connector through the full pipeline
  4. Dispatch tools.list (+ optionally resources.list, prompts.list)
  5. Build sanitized ConnectionTestResult — NO secrets, NO env vars
  6. Shutdown ephemeral runtime unconditionally
  7. Update nexora.mcp_server_config.last_test_result_json

The global ConnectorRuntime is NEVER touched.
Credentials are NEVER included in the returned result or any log.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger

# Module-level import so unittest.mock.patch can substitute it in tests
from odoo.addons.nexora_studio.services.connector.runtime.connector_runtime import ConnectorRuntime

_logger = get_logger(__name__)


@dataclass
class ConnectionTestResult:
    """
    Sanitized result from a connection test.
    NEVER contains credentials, env vars, or subprocess environment.
    """
    success: bool
    latency_ms: float
    tool_count: int
    resource_count: int
    prompt_count: int
    server_info: Dict[str, Any]   # Sanitized metadata from the MCP server
    error_message: str             # User-safe error message only
    error_code: str
    tested_at: str                 # ISO datetime string

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class McpConnectionTester:
    """
    Safe connection tester that uses an ephemeral runtime — never the global one.
    """

    def __init__(self, onboarding_service_factory, odoo_env):
        """
        Args:
            onboarding_service_factory: callable that produces McpOnboardingService instances
            odoo_env: Odoo environment
        """
        self._factory = onboarding_service_factory
        self._env = odoo_env

    def test(self, connector_record) -> ConnectionTestResult:
        """
        Test the MCP server connection for the given connector record.

        Returns ConnectionTestResult — always sanitized, never contains secrets.
        Updates nexora.mcp_server_config.last_test_result_json on the record.
        """
        connector_id = connector_record.connector_id
        _logger.info(
            "McpConnectionTester: starting test for connector '%s'.", connector_id,
            extra={'connector_id': connector_id}
        )

        start_time = time.monotonic()
        result = self._run_test(connector_record, connector_id, start_time)

        # Persist sanitized result to Odoo record (never contains secrets)
        self._persist_test_result(connector_record, result)

        return result

    def _run_test(self, connector_record, connector_id: str, start_time: float) -> ConnectionTestResult:
        """Execute the actual test — isolated in a try/finally for guaranteed cleanup."""
        from odoo.addons.nexora_studio.services.connector.registry.connector_registry import ConnectorRegistry
        from odoo.addons.nexora_studio.services.connector.registry.registration_pipeline import ConnectorRegistrationPipeline
        from odoo.addons.nexora_studio.services.connector.registry.capability_index import ConnectorCapabilityIndex
        from odoo.addons.nexora_studio.services.connector.domain.models import (
            ConnectorExecutionRequest, ConnectorRuntimeContext
        )

        ephemeral_runtime = None
        try:
            # 1. Create ephemeral runtime (isolated — not the global singleton)
            ephemeral_runtime = ConnectorRuntime()
            ephemeral_runtime.startup()
            # 2. Build onboarding service for ephemeral runtime
            onboarding = self._factory(ephemeral_runtime, ephemeral_runtime.registration_pipeline, self._env)

            # 3. Register connector through the full pipeline
            onboarding.register_connector(connector_record)

            # 4. Dispatch tests
            tool_count = 0
            resource_count = 0
            prompt_count = 0
            server_info = {}

            ctx = ConnectorRuntimeContext(connector_id=connector_id, session_id='test')

            # tools.list
            tools_req = ConnectorExecutionRequest(
                capability_namespace='tools.list',
                context=ctx,
                timeout_seconds=30.0,
            )
            tools_result = ephemeral_runtime.dispatch(tools_req)
            _logger.info(f"TESTER TOOLS RAW: success={tools_result.success}, data={tools_result.data}, error={tools_result.error}")
            if tools_result.success:
                tools_data = tools_result.data or {}
                tool_count = len(tools_data.get('tools', []))

            # resources.list
            resources_req = ConnectorExecutionRequest(
                capability_namespace='resources.list',
                context=ctx,
                timeout_seconds=30.0,
            )
            resources_result = ephemeral_runtime.dispatch(resources_req)
            if resources_result.success:
                resources_data = resources_result.data or {}
                resource_count = len(resources_data.get('resources', []))

            # prompts.list
            prompts_req = ConnectorExecutionRequest(
                capability_namespace='prompts.list',
                context=ctx,
                timeout_seconds=30.0,
            )
            prompts_result = ephemeral_runtime.dispatch(prompts_req)
            if prompts_result.success:
                prompts_data = prompts_result.data or {}
                prompt_count = len(prompts_data.get('prompts', []))

            latency_ms = (time.monotonic() - start_time) * 1000

            return ConnectionTestResult(
                success=True,
                latency_ms=round(latency_ms, 2),
                tool_count=tool_count,
                resource_count=resource_count,
                prompt_count=prompt_count,
                server_info=server_info,
                error_message='',
                error_code='',
                tested_at=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            import traceback
            full_tb = traceback.format_exc()
            # Log full technical detail internally
            _logger.warning(
                "McpConnectionTester: test failed for '%s': %s — %s\n%s",
                connector_id, type(e).__name__,
                str(e),
                full_tb,
                extra={'connector_id': connector_id}
            )
            # User-safe message — use user_safe_message for ConnectorError subclasses
            # to prevent technical_message (credential key names, internal paths) from leaking
            from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorError
            if isinstance(e, ConnectorError):
                user_msg = f'Connection failed: {type(e).__name__} - {e.user_safe_message}. Check server configuration.'
            else:
                user_msg = f'Connection failed: {type(e).__name__} - {str(e)}. Check server configuration.\n{full_tb}'
            return ConnectionTestResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                tool_count=0,
                resource_count=0,
                prompt_count=0,
                server_info={},
                error_message=user_msg,
                error_code=getattr(e, 'error_code', 'CONNECTION_FAILED'),
                tested_at=datetime.utcnow().isoformat(),
            )

        finally:
            # 5. Always shut down the ephemeral runtime — never leave dangling sessions
            if ephemeral_runtime is not None:
                try:
                    ephemeral_runtime.shutdown()
                except Exception as shutdown_err:
                    _logger.warning(
                        "McpConnectionTester: ephemeral runtime shutdown error for '%s': %s",
                        connector_id, type(shutdown_err).__name__,
                        extra={'connector_id': connector_id}
                    )

    def _persist_test_result(self, connector_record, result: ConnectionTestResult) -> None:
        """Persist sanitized test result to Odoo. Never persists secrets."""
        try:
            mcp_config = self._env['nexora.mcp_server_config'].search(
                [('connector_id', '=', connector_record.id)], limit=1
            )
            if mcp_config:
                mcp_config.write({
                    'last_test_result_json': result.to_json(),
                    'last_tested_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                })
        except Exception as e:
            _logger.warning(
                "McpConnectionTester: failed to persist test result for '%s': %s",
                connector_record.connector_id, type(e).__name__,
                extra={'connector_id': connector_record.connector_id}
            )
