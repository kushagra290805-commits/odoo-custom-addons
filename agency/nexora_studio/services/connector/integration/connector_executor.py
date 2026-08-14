"""
Connector Execution Target — UCEL Integration
==============================================
Part 9 of Phase 26 — Universal Connector Platform Foundation.

Implements ExecutionTarget ABC from capabilities/executors/base.py.
Added as a third executor type to the UCEL executor registry.
This is the sole communication channel between UCEL and ConnectorRuntime.

Architecture invariants:
- UCEL calls this via ExecutionScheduler — it knows nothing about ConnectorRuntime.
- This target translates UCEL payloads to ConnectorExecutionRequests.
- It translates ConnectorExecutionResults back to CapabilityResults.
- The Generation Platform does not import from ConnectorRuntime directly.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
import uuid
from typing import Any, Optional

_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Import shims — allow module to load even without full Odoo environment
# ---------------------------------------------------------------------------

try:
    from odoo.addons.nexora_studio.services.capabilities.executors.base import ExecutionTarget
    from odoo.addons.nexora_studio.services.capabilities.models import CapabilityResult
except ImportError:
    # Fallback for standalone module loading / testing
    class ExecutionTarget:  # type: ignore
        def execute(self, payload: dict) -> Any:
            raise NotImplementedError

    class CapabilityResult:  # type: ignore
        def __init__(self, success: bool, result: Any = None, logs: list = None):
            self.success = success
            self.result = result
            self.logs = logs or []


from ..domain.models import (
    ConnectorExecutionRequest,
    ConnectorExecutionStatus,
    ConnectorRuntimeContext,
)


class ConnectorExecutionTarget(ExecutionTarget):
    """
    UCEL execution target that routes capability calls to ConnectorRuntime.

    This is the EP-004 extension point bridge defined in ADR-0050.

    UCEL payload format expected:
    {
        "namespace": "search.web",      # capability namespace
        "inputs": {...},                # capability inputs
        "context": {...},               # UCEL execution context
        "correlation_id": "uuid",       # tracing
        "timeout": 60.0,               # timeout in seconds
    }
    """

    # Type identifier for UCEL executor registry key
    EXECUTOR_TYPE_KEY = "connector"

    def __init__(self, connector_runtime: Optional[Any] = None) -> None:
        """
        Args:
            connector_runtime: ConnectorRuntime instance.
                               If None, all executions return NOT_INITIALIZED failure.
        """
        self._connector_runtime = connector_runtime

    def execute(self, payload: dict) -> Any:
        """
        Translate a UCEL payload to a ConnectorExecutionRequest,
        dispatch through ConnectorRuntime, and translate the result back to CapabilityResult.

        Never raises — all failures are returned as CapabilityResult(success=False).
        """
        if self._connector_runtime is None:
            _logger.warning("ConnectorExecutionTarget: no ConnectorRuntime wired. Returning failure.")
            return CapabilityResult(
                success=False,
                result=None,
                logs=["ConnectorRuntime not initialized. Connector Platform bootstrap has not completed."],
            )

        # Translate UCEL payload → ConnectorExecutionRequest
        request = self._build_request(payload)

        # Dispatch through ConnectorRuntime
        result = self._connector_runtime.dispatch(request)

        # Translate ConnectorExecutionResult → CapabilityResult
        return self._build_capability_result(result)

    def set_connector_runtime(self, connector_runtime: Any) -> None:
        """
        Wire the ConnectorRuntime after construction.
        Called by ConnectorPlatformBootstrap.
        """
        self._connector_runtime = connector_runtime

    # ------------------------------------------------------------------
    # Translation Helpers
    # ------------------------------------------------------------------

    def _build_request(self, payload: dict) -> ConnectorExecutionRequest:
        """Build a ConnectorExecutionRequest from a UCEL payload dict."""
        namespace = payload.get("namespace", payload.get("capability_namespace", ""))
        inputs = payload.get("inputs", payload.get("payload", {}))
        context_data = payload.get("context", {})
        correlation_id = payload.get("correlation_id", str(uuid.uuid4()))
        timeout = float(payload.get("timeout", 60.0))

        context = ConnectorRuntimeContext(
            connector_id=context_data.get("connector_id", ""),  # Fixed: read from payload context
            session_id=correlation_id,
            correlation_id=correlation_id,
            configuration_snapshot=context_data,
            timeout_seconds=timeout,
        )

        return ConnectorExecutionRequest(
            capability_namespace=namespace,
            payload=inputs if isinstance(inputs, dict) else {},
            context=context,
            timeout_seconds=timeout,
        )

    def _build_capability_result(self, result: Any) -> Any:
        """Translate ConnectorExecutionResult to CapabilityResult."""
        if result.success:
            return CapabilityResult(
                success=True,
                result=result.data,
                logs=[f"Connector execution: {result.request_id} ({result.execution_ms:.1f}ms)"],
            )

        error_detail = result.error or "Unknown connector error"
        if result.status == ConnectorExecutionStatus.TIMEOUT:
            error_detail = f"Connector execution timed out after {result.execution_ms:.0f}ms."
        elif result.status == ConnectorExecutionStatus.CANCELLED:
            error_detail = "Connector execution was cancelled."

        return CapabilityResult(
            success=False,
            result=None,
            logs=[
                f"Connector execution failed: {error_detail}",
                f"Error code: {result.error_code}",
                f"Request ID: {result.request_id}",
            ],
        )

    def __repr__(self) -> str:
        return (
            f"ConnectorExecutionTarget("
            f"runtime={'wired' if self._connector_runtime else 'none'})"
        )
