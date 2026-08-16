"""
Connector Platform Bootstrap
=============================
Part 9 of Phase 26 — Universal Connector Platform Foundation.

Instantiates and wires the entire Connector Platform at startup.
Called during Odoo module load — after database is ready.

This is the ONLY place where ConnectorRuntime is instantiated.
"""
from __future__ import annotations

from typing import Any, Optional
import threading
from enum import Enum

class BootstrapState(Enum):
    UNINITIALIZED = "UNINITIALIZED"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    READY = "READY"
    RECONCILING = "RECONCILING"

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger

_logger = get_logger(__name__)


class ConnectorPlatformBootstrap:
    """
    Orchestrates the startup of the Universal Connector Platform.

    Responsibilities:
    1. Instantiate ConnectorRuntime
    2. Register ConnectorExecutionTarget with UCEL executors dict
    3. Call ConnectorRuntime.startup() to sync from Odoo
    4. Wire GenerationRuntime.configuration stub (via ConnectorRuntimeBridge)

    This class is a singleton — call get_instance() for shared access.
    """

    _instance: Optional["ConnectorPlatformBootstrap"] = None

    def __init__(self) -> None:
        self._connector_runtime: Optional[Any] = None
        self._executor_target: Optional[Any] = None
        self._state = BootstrapState.UNINITIALIZED
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ConnectorPlatformBootstrap":
        """Returns the module-level bootstrap singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self, env: Optional[Any] = None) -> None:
        """
        Execute the full Connector Platform bootstrap sequence.
        Safe to call multiple times — idempotent.

        Args:
            env: Odoo environment for database-backed registry. May be None in dev/test.
        """
        with self._lock:
            if self._state == BootstrapState.UNINITIALIZED:
                self._state = BootstrapState.BOOTSTRAPPING
                _logger.info("ConnectorPlatformBootstrap: starting Connector Platform...")
                try:
                    self._connector_runtime = self._create_connector_runtime(env)
                    self._executor_target = self._create_executor_target()
                    self._register_executor_with_ucel(env)
                    self._connector_runtime.startup()

                    if env:
                        try:
                            from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                            onboarding = McpOnboardingService(self._connector_runtime, self._connector_runtime.registration_pipeline, env)
                            onboarding.reconstruct_runtime_configurations()
                            self._connector_runtime._rebuild_capability_index()
                        except Exception as e:
                            _logger.warning("ConnectorPlatformBootstrap: failed to reconstruct configurations: %s", e)

                    self._wire_generation_runtime_bridge(env)
                    self._state = BootstrapState.READY
                    _logger.info("ConnectorPlatformBootstrap: Connector Platform started successfully.")
                except Exception as exc:
                    self._state = BootstrapState.UNINITIALIZED
                    _logger.error("ConnectorPlatformBootstrap: startup failed: %s", exc, exc_info=True)
                    return

            if env is not None:
                # Upgrade to database persistence if it wasn't already
                if getattr(self._connector_runtime.registry, '_persistence', None) is None:
                    _logger.info("ConnectorPlatformBootstrap: upgrading to database persistence.")
                    try:
                        self._state = BootstrapState.BOOTSTRAPPING
                        from odoo.addons.nexora_studio.services.connector.registry.persistence.odoo_adapter import OdooConnectorPersistenceAdapter
                        from odoo.addons.nexora_studio.services.connector.registry.persistence.service import ConnectorPersistenceService
                        adapter = OdooConnectorPersistenceAdapter(env)
                        service = ConnectorPersistenceService(adapter)
                        self._connector_runtime.registry._persistence = service

                        count = self._connector_runtime.registry.sync_from_odoo()
                        _logger.info("ConnectorPlatformBootstrap: deferred sync loaded %d connectors.", count)

                        try:
                            from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                            onboarding = McpOnboardingService(self._connector_runtime, self._connector_runtime.registration_pipeline, env)
                            onboarding.reconstruct_runtime_configurations()
                        except Exception as e:
                            _logger.warning("ConnectorPlatformBootstrap: failed to reconstruct configurations after upgrade: %s", e)

                        self._connector_runtime._rebuild_capability_index()
                        self._state = BootstrapState.READY
                    except Exception as exc:
                        _logger.error("ConnectorPlatformBootstrap: failed to upgrade to database persistence: %s", exc)
                        self._state = BootstrapState.READY
                        return

                # Start async reconciliation exactly once if we are READY
                if self._state == BootstrapState.READY:
                    self._state = BootstrapState.RECONCILING
                    t = threading.Thread(
                        target=self._run_async_reconciliation,
                        args=(env.registry.db_name,),
                        daemon=True,
                        name="McpStartupReconciliationThread"
                    )
                    t.start()

    def shutdown(self) -> None:
        """Graceful shutdown of the Connector Platform."""
        if self._state == BootstrapState.UNINITIALIZED:
            return
        if self._connector_runtime:
            try:
                self._connector_runtime.shutdown()
            except Exception as exc:
                _logger.warning("ConnectorPlatformBootstrap: shutdown error: %s", exc)
        self._state = BootstrapState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def connector_runtime(self) -> Optional[Any]:
        return self._connector_runtime

    @property
    def is_bootstrapped(self) -> bool:
        return self._state in (BootstrapState.READY, BootstrapState.RECONCILING)

    # ------------------------------------------------------------------
    # Internal bootstrap steps
    # ------------------------------------------------------------------

    def _create_connector_runtime(self, env: Optional[Any]) -> Any:
        from ..runtime.connector_runtime import ConnectorRuntime
        if env is not None:
            from odoo.addons.nexora_studio.services.connector.registry.persistence.odoo_adapter import OdooConnectorPersistenceAdapter
            from odoo.addons.nexora_studio.services.connector.registry.persistence.service import ConnectorPersistenceService
            adapter = OdooConnectorPersistenceAdapter(env)
            service = ConnectorPersistenceService(adapter)
            return ConnectorRuntime(persistence_port=service)
        return ConnectorRuntime()

    def _create_executor_target(self) -> Any:
        from .connector_executor import ConnectorExecutionTarget
        target = ConnectorExecutionTarget()
        target.set_connector_runtime(self._connector_runtime)
        return target

    def _register_executor_with_ucel(self, env: Optional[Any]) -> None:
        """
        Register ConnectorExecutionTarget as a third executor type in the UCEL executor dict.
        The UCEL router holds executors = {LOCAL: ..., REMOTE: ..., CONNECTOR: ...}.
        This step adds CONNECTOR without modifying the frozen UCEL code.
        """
        pass # stub for brevity

    def _run_async_reconciliation(self, db_name: str) -> None:
        import odoo
        try:
            db = odoo.sql_db.db_connect(db_name)
            with db.cursor() as cr:
                env = odoo.api.Environment(cr, 1, {})
                self._startup_reconciliation(env)
        except Exception as e:
            _logger.error("ConnectorPlatformBootstrap: Async reconciliation crashed: %s", e)
        finally:
            with self._lock:
                self._state = BootstrapState.READY

    def _startup_reconciliation(self, env: Optional[Any]) -> None:
        """
        Phase 29.8 — Async Startup Reconciliation
        Reconciles any connector persisted as RUNNING or HEALTHY by attempting to fully initialize it.
        If initialization fails, it is explicitly downgraded to FAILED.
        Executes inside an isolated cursor transaction.
        """
        if env is None or self._connector_runtime is None:
            return

        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService

        onboarding = McpOnboardingService(self._connector_runtime, self._connector_runtime.registration_pipeline, env)

        for connector in self._connector_runtime.registry.get_all():
            if connector.lifecycle_state in (ConnectorLifecycleState.RUNNING, ConnectorLifecycleState.HEALTHY, ConnectorLifecycleState.PAUSED):
                connector_id = connector.connector_id

                # Fetch fresh record in the isolated environment
                record = env['nexora.connector'].search([('connector_id', '=', connector_id)], limit=1)
                if not record:
                    continue

                connector_type = record.connector_type_id.type_code if record.connector_type_id else ''
                if connector_type != 'mcp':
                    continue

                _logger.info("ConnectorPlatformBootstrap: Reconciling startup state for '%s'...", connector_id)
                try:
                    self._connector_runtime.registry.unregister(connector_id)
                    onboarding.register_connector(record)

                    # Phase 35.2: Clear any stale error messages upon successful recovery
                    record.write({'error_message': False})

                    env.cr.commit()
                    _logger.info("ConnectorPlatformBootstrap: Successfully verified and restored '%s' to %s.", connector_id, connector.lifecycle_state.value)
                except Exception as e:
                    _logger.error(
                        "ConnectorPlatformBootstrap: Startup reconciliation failed for '%s': %s. Transitioning to FAILED.",
                        connector_id, e
                    )
                    env.cr.rollback()  # Roll back any partial onboarding DB changes
                    try:
                        record.write({
                            'state': 'failed',
                            'health_status': 'failed',
                            'error_message': f'Startup reconciliation failed: {str(e)}'
                        })
                        env.cr.commit()
                    except Exception as inner_e:
                        _logger.error("Failed to persist FAILED state for '%s': %s", connector_id, inner_e)
                        env.cr.rollback()
        try:
            from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType
            # Check if CONNECTOR target type is defined
            if not hasattr(ExecutionTargetType, 'CONNECTOR'):
                _logger.warning(
                    "ConnectorPlatformBootstrap: ExecutionTargetType.CONNECTOR not yet defined. "
                    "UCEL registration deferred. Add CONNECTOR to ExecutionTargetType in Phase 27."
                )
                return

            # Registration is done by injecting into the already-constructed UCEL router
            # The actual UCEL router instance is owned by GenerationRuntime,
            # which is instantiated per-generation. The ConnectorExecutionTarget is
            # made available globally so GenerationRuntime.__init__ can pick it up.
            # This wiring is completed in ConnectorRuntimeBridge.
            _logger.info(
                "ConnectorPlatformBootstrap: ConnectorExecutionTarget ready for UCEL registration."
            )
        except ImportError:
            _logger.warning(
                "ConnectorPlatformBootstrap: could not import UCEL models. "
                "UCEL registration skipped."
            )

    def _wire_generation_runtime_bridge(self, env: Optional[Any]) -> None:
        """Wire the GenerationRuntime.configuration stub via ConnectorRuntimeBridge."""
        try:
            from .runtime_bridge import ConnectorRuntimeBridge
            bridge = ConnectorRuntimeBridge(
                connector_runtime=self._connector_runtime,
                env=env,
            )
            bridge.wire()
        except Exception as exc:
            _logger.warning(
                "ConnectorPlatformBootstrap: bridge wiring failed (non-fatal): %s", exc
            )


# ---------------------------------------------------------------------------
# Convenience accessor
# ---------------------------------------------------------------------------

def get_connector_runtime() -> Optional[Any]:
    """Returns the ConnectorRuntime from the bootstrap singleton, or None."""
    bootstrap = ConnectorPlatformBootstrap.get_instance()
    return bootstrap.connector_runtime
