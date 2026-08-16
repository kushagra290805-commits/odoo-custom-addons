"""
Connector Runtime
=================
Part 5 of Phase 26 — Universal Connector Platform Foundation.

The central orchestrator for the Connector Platform.
Peer to GenerationRuntime — never owned by it.
Instantiated once at platform startup via ConnectorPlatformBootstrap.

Responsibilities:
- Connector discovery
- Capability lookup
- Lifecycle coordination
- Execution dispatch
- Dependency resolution
- Health monitoring
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import Dict, List, Optional

from ..domain.models import (
    Connector,
    ConnectorLifecycleState,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
)
from ..events.bus import ConnectorEventBus, EventSubscriber
from ..factory import ConnectorFactory, ProviderFactory, TransportFactory
from ..lifecycle.lifecycle_manager import ConnectorLifecycleManager
from ..lifecycle.transitions import ConnectorLifecycleStateMachine
from ..registry.capability_index import ConnectorCapabilityIndex
from ..registry.registration_pipeline import ConnectorRegistrationPipeline
from ..registry.connector_registry import ConnectorRegistry
from ..registry.persistence.port import ConnectorPersistencePort
from .dependency_resolver import ConnectorDependencyResolver
from .dispatcher import ConnectorDispatcher
from .health_monitor import ConnectorHealthMonitor
from ..sdk.telemetry_port import ConnectorTelemetryPort
from .telemetry_recorder import InMemoryTelemetryRecorder

_logger = get_logger(__name__)


class ConnectorRuntime(EventSubscriber):
    """
    The Connector Platform's central orchestrator.

    Architecture invariants:
    - GenerationRuntime must NEVER own or instantiate ConnectorRuntime.
    - ConnectorRuntime is wired at startup, not at generation time.
    - ConnectorRuntime is never aware of generation sessions, pipeline stages,
      or workspace artifacts.
    - All connector execution routes through ConnectorRuntime.dispatch().

    Startup sequence:
    1. ConnectorPlatformBootstrap instantiates ConnectorRuntime
    2. ConnectorRuntime initializes all sub-components
    3. ConnectorRuntime syncs registry from Odoo
    4. ConnectorRuntime registers ConnectorExecutionTarget with UCEL
    """

    def __init__(
        self,
        persistence_port: Optional[ConnectorPersistencePort] = None,
        telemetry_port: Optional[ConnectorTelemetryPort] = None
    ) -> None:
        """
        Args:
            persistence_port: Adapter for database-backed registry sync.
                 If None, runs in memory-only mode.
            telemetry_port: Adapter for tracking runtime metrics.
                 If None, uses InMemoryTelemetryRecorder.
        """
        self._persistence = persistence_port
        self.telemetry = telemetry_port or InMemoryTelemetryRecorder()
        self._initialized = False

        # Recovery state tracking
        import threading
        self._recovery_locks = {}
        self._recovery_state = {}
        self._recovery_timers = {}
        self._is_shutting_down = False

        # Event Bus
        self.event_bus = ConnectorEventBus()
        self.event_bus.subscribe(self)

        # Factories
        self.transport_factory = TransportFactory()
        self.provider_factory = ProviderFactory()
        self.connector_factory = ConnectorFactory(
            transport_factory=self.transport_factory,
            provider_factory=self.provider_factory,
        )

        # Sub-components
        self.registry = ConnectorRegistry(persistence_port=persistence_port)
        self.capability_index = ConnectorCapabilityIndex()
        self.lifecycle_manager = ConnectorLifecycleManager(
            state_machine=ConnectorLifecycleStateMachine(),
            event_bus=self.event_bus,
        )
        self.health_monitor = ConnectorHealthMonitor(
            event_bus=self.event_bus,
        )
        self.dependency_resolver = ConnectorDependencyResolver()

        self.registration_pipeline = ConnectorRegistrationPipeline(
            registry=self.registry,
            capability_index=self.capability_index,
            telemetry=self.telemetry
        )

        self.dispatcher = ConnectorDispatcher(
            registry=self.registry,
            factory=self.connector_factory,
            capability_index=self.capability_index,
            telemetry=self.telemetry
        )

        _logger.info("ConnectorRuntime initialized (persistence=%s).", "available" if persistence_port else "none")

    # ------------------------------------------------------------------
    # Startup / Shutdown
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """
        Initialize the Connector Platform.
        Called once during Odoo module load, after DB is ready.
        """
        if self._initialized:
            _logger.warning("ConnectorRuntime.startup() called more than once. Ignoring.")
            return

        _logger.info("ConnectorRuntime: starting up...")

        # Register built-in connector types with the factory
        self._register_builtin_connector_types()

        # Sync connectors from Odoo (Phase 27+ will populate real connectors)
        count = self.registry.sync_from_odoo()
        _logger.info("ConnectorRuntime: loaded %d connectors from registry.", count)

        # Rebuild capability index from registry
        self._rebuild_capability_index()

        self._initialized = True
        _logger.info("ConnectorRuntime: startup complete. %d connectors registered.", self.registry.count())


    def shutdown(self) -> None:
        """Graceful shutdown. Releases resources held by running connectors."""
        if not self._initialized:
            return
        _logger.info("ConnectorRuntime: shutting down...")
        running = self.registry.get_running()
        for connector in running:
            try:
                self.lifecycle_manager.transition(
                    connector, ConnectorLifecycleState.DISABLED, reason="platform_shutdown"
                )
            except Exception as exc:
                _logger.warning(
                    "Error disabling connector '%s' during shutdown: %s",
                    connector.connector_id, exc
                )

        # Cancel any pending recovery timers
        self._is_shutting_down = True
        for timer in self._recovery_timers.values():
            try:
                timer.cancel()
            except Exception:
                pass
        self._recovery_timers.clear()

        # Phase 27.2: Ensure all cached active connector instances are shut down
        self.dispatcher.shutdown_all()

        self._initialized = False
        _logger.info("ConnectorRuntime: shutdown complete.")    # ------------------------------------------------------------------
    # Capability Lookup
    # ------------------------------------------------------------------

    def resolve_capability(self, namespace: str) -> Optional[ConnectorCapability]:
        """
        Resolve a capability namespace to its ConnectorCapability definition.
        Returns None if no RUNNING connector provides this namespace.
        """
        connector = self.registry.find_for_capability(namespace)
        if connector is None:
            return None
        return connector.get_capability(namespace)

    def can_handle(self, namespace: str) -> bool:
        """Returns True if at least one RUNNING connector provides this namespace."""
        return self.capability_index.has_capability(namespace)

    def list_available_namespaces(self) -> List[str]:
        """Returns all capability namespaces currently available via RUNNING connectors."""
        return self.capability_index.list_namespaces()

    # ------------------------------------------------------------------
    # Execution Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, request: ConnectorExecutionRequest) -> ConnectorExecutionResult:
        """
        Dispatch a capability execution request.
        Routes to the appropriate connector via ConnectorDispatcher.
        Never raises — all failures are encapsulated in ConnectorExecutionResult.
        """
        if not self._initialized:
            return ConnectorExecutionResult.fail(
                request_id=request.request_id,
                error="ConnectorRuntime is not initialized. Call startup() first.",
                error_code="RUNTIME_NOT_INITIALIZED",
            )

        connector_id = request.context.connector_id if request.context else None
        if not connector_id:
            connector_id = self.capability_index.get_primary(request.capability_namespace)

        if connector_id and self._recovery_state.get(connector_id) == "IN_PROGRESS":
            return ConnectorExecutionResult.fail(
                request_id=request.request_id,
                error=f"Connector '{connector_id}' is locally recovering and currently unavailable.",
                error_code="CONNECTOR_UNAVAILABLE",
            )

        result = self.dispatcher.dispatch(request)

        # Intercept genuine transport failures from dispatcher.
        # Application-level errors (tool not found, unsupported capability, protocol error from
        # a specific tool call) must NOT trigger recovery — only transport-level failures do.
        # Capability-discovery namespaces (resources.list, prompts.list) are advisory: MCP
        # servers are not required to implement them, so failures there are never transport errors.
        _CAPABILITY_DISCOVERY_NAMESPACES = {'resources.list', 'prompts.list', 'tools.list'}
        _TRANSPORT_ERROR_CODES = {'TRANSPORT_ERROR', 'TIMEOUT', 'NO_EXECUTION_ADAPTER'}

        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionStatus, ConnectorFailureClass
        if result.status == ConnectorExecutionStatus.FAILURE:
            cap_ns = request.capability_namespace
            is_discovery_ns = cap_ns in _CAPABILITY_DISCOVERY_NAMESPACES
            is_transport_error = result.error_code in _TRANSPORT_ERROR_CODES

            if not is_discovery_ns and is_transport_error:
                connector_id = request.context.connector_id if request.context else None
                if not connector_id:
                    connector_id = self.capability_index.get_primary(cap_ns)

                if connector_id:
                    _logger.warning(
                        "ConnectorRuntime: transport failure '%s' for '%s' on '%s'.",
                        result.error_code, connector_id, cap_ns
                    )
                    self.handle_transport_failure(
                        connector_id=connector_id,
                        failure_class=ConnectorFailureClass.TRANSPORT_ERROR,
                        error_message=result.error
                    )

        return result

    # ------------------------------------------------------------------
    # Lifecycle Management
    # ------------------------------------------------------------------

    def register_connector(self, connector: Connector) -> None:
        """Register a new connector via the registration pipeline."""
        self.registration_pipeline.execute(connector)

    def unregister_connector(self, connector_id: str) -> bool:
        """Unregister a connector and remove it from the index."""
        connector = self.registry.get(connector_id)
        if not connector:
            return False

        if self.registry.unregister(connector_id):
            self.capability_index.remove(connector_id)
            self.dispatcher.shutdown_connector(connector_id)
            # Clear any stale recovery state so re-registration is not blocked
            self._recovery_state.pop(connector_id, None)
            timer = self._recovery_timers.pop(connector_id, None)
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
            return True
        return False

    def rebuild_capability_index(self) -> None:
        """Rebuilds the capability index from the current registry state."""
        self.capability_index.clear()
        for connector in self.registry.get_all():
            for cap in connector.manifest.capabilities:
                self.capability_index.add(cap, connector.connector_id)


    def transition_connector(
        self,
        connector_id: str,
        target_state: ConnectorLifecycleState,
        reason: str = "",
    ) -> bool:
        """
        Request a lifecycle transition for a connector.
        Returns True if the transition succeeded.
        """
        connector = self.registry.get(connector_id)
        if connector is None:
            _logger.warning("ConnectorRuntime.transition_connector: connector '%s' not found.", connector_id)
            return False
        result = self.lifecycle_manager.transition(connector, target_state, reason)
        if result.success:
            # Rebuild index to reflect state changes
            self._rebuild_capability_index()
            # If transitioned to disabled, shutdown the active instance
            if target_state == ConnectorLifecycleState.DISABLED:
                self.dispatcher.shutdown_connector(connector_id)
        return result.success

    # ------------------------------------------------------------------
    # Recovery and Failure Handling (Phase 35.4)
    # ------------------------------------------------------------------

    def handle_transport_failure(
        self,
        connector_id: str,
        failure_class: 'ConnectorFailureClass',
        error_message: str
    ) -> None:
        """
        Handle a failure emitted by the dispatcher during an execution or initialization.
        """
        if self._is_shutting_down:
            return

        import threading

        # Invalidate capabilities immediately to prevent further requests
        self.capability_index.remove(connector_id)

        # Do NOT transition to FAILED here. A worker-local transport failure
        # must not mutate the global persistent lifecycle state.
        # It remains globally RUNNING/HEALTHY, but locally unavailable.

        if not failure_class.is_recoverable():
            _logger.warning(
                "ConnectorRuntime: Connector '%s' encountered non-recoverable failure '%s'. Disabling recovery.",
                connector_id, failure_class.value
            )
            return

        # Single-flight recovery execution
        with self._recovery_locks.setdefault(connector_id, threading.Lock()):
            if self._recovery_state.get(connector_id) == "IN_PROGRESS":
                _logger.debug("ConnectorRuntime: Recovery already in progress for '%s'.", connector_id)
                return

            # Reset recovery attempt count if this is a fresh failure
            if connector_id not in self._recovery_timers:
                self._recovery_state[connector_id] = "IN_PROGRESS"
                _logger.info("ConnectorRuntime: Scheduling recovery for '%s' (Reason: %s).", connector_id, failure_class.value)

                # Debounce/Delay the recovery attempt (e.g. 2 seconds)
                timer = threading.Timer(2.0, self._attempt_recovery, args=[connector_id])
                self._recovery_timers[connector_id] = timer
                timer.start()

    def _attempt_recovery(self, connector_id: str) -> None:
        """
        Attempt to recover a failed connector.
        Invoked asynchronously by a threading.Timer.
        """
        if self._is_shutting_down:
            return

        _logger.info("ConnectorRuntime: Executing recovery attempt for '%s'...", connector_id)
        try:
            connector = self.registry.get(connector_id)
            if not connector:
                _logger.warning("ConnectorRuntime.recovery: Connector '%s' no longer exists.", connector_id)
                return

            from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
            context = ExecutionContext(connector_id=connector_id, request_id='recovery', capability_namespace='init')

            # 1. Clean slate
            self.dispatcher.shutdown_connector(connector_id)

            # 2. Canonical Initialization & Handshake
            result = self.dispatcher.initialize_and_verify(connector, context)
            from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionStatus

            if result.status == ConnectorExecutionStatus.SUCCESS:
                _logger.info("ConnectorRuntime: Recovery successful for '%s'. Restoring capabilities.", connector_id)

                # Restore capabilities index
                for cap in connector.manifest.capabilities:
                    self.capability_index.add(cap, connector_id)

                # Transition back to RUNNING
                self.lifecycle_manager.transition(connector, ConnectorLifecycleState.RUNNING, reason="recovery_success")
                self.record_health_success(connector_id)
            else:
                _logger.warning("ConnectorRuntime: Recovery failed for '%s': %s", connector_id, result.error)
                self.record_health_failure(connector_id, error=result.error)

        except Exception as e:
            import traceback
            _logger.error(f"ConnectorRuntime.recovery exception for '{connector_id}':\n{traceback.format_exc()}")
        finally:
            import threading
            with self._recovery_locks.setdefault(connector_id, threading.Lock()):
                self._recovery_state[connector_id] = "IDLE"
                self._recovery_timers.pop(connector_id, None)

    # ------------------------------------------------------------------
    # Health Monitoring
    # ------------------------------------------------------------------

    def record_health_success(self, connector_id: str, latency_ms: float = 0.0) -> None:
        """Record a successful health check for a connector."""
        connector = self.registry.get(connector_id)
        if connector:
            self.health_monitor.record_success(connector, latency_ms)

    def record_health_failure(self, connector_id: str, error: str = "") -> None:
        """Record a failed health check for a connector."""
        connector = self.registry.get(connector_id)
        if connector:
            self.health_monitor.record_failure(connector, error)

    def get_health_summary(self) -> Dict[str, str]:
        """Returns a dict of connector_id → health_status for all registered connectors."""
        result = {}
        for connector in self.registry.get_all():
            health = connector.health
            result[connector.connector_id] = health.status.value if health else "unknown"
        return result

    def probe_health(self, connector_id: str):
        """
        Actively invokes the health check via the dispatcher and records the result.
        Returns the updated ConnectorHealth object if the connector exists.
        """
        connector = self.registry.get(connector_id)
        if not connector:
            return None

        # Do not probe connectors that are completely shut down or unconfigured
        active_states = {'running', 'healthy', 'paused', 'failed'}
        if getattr(connector.lifecycle_state, 'value', connector.lifecycle_state) not in active_states:
            return None

        # Do not probe connectors that are actively recovering locally
        if self._recovery_state.get(connector_id) == "IN_PROGRESS":
            return None

        from ..domain.models import ConnectorRuntimeContext
        context = ConnectorRuntimeContext(connector_id=connector_id, session_id='health_probe')

        success, latency_ms, error = self.dispatcher.probe_health(connector_id, context)

        if success is None:
            return None
        if success:
            self.health_monitor.record_success(connector, latency_ms)
        else:
            self.health_monitor.record_failure(connector, error)

        return self.health_monitor.get_health(connector)


    # ------------------------------------------------------------------
    # Dependency Resolution
    # ------------------------------------------------------------------

    def resolve_dependencies(self, connector_id: str) -> List[str]:
        """
        Resolve the installation order for a connector and all its dependencies.
        Returns an ordered list of connector_ids (dependencies first).
        """
        manifests = {c.connector_id: c.manifest for c in self.registry.get_all()}
        connector = self.registry.get(connector_id)
        if connector:
            manifests[connector_id] = connector.manifest

        result = self.dependency_resolver.resolve(connector_id, manifests)
        if not result.success:
            _logger.error(
                "ConnectorRuntime: dependency resolution failed for '%s': %s",
                connector_id, result.errors,
            )
            return []
        return result.install_order

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _register_builtin_connector_types(self) -> None:
        """
        Register all built-in connector implementations with the ConnectorFactory.

        This is the wiring step that connects:
          Connector domain aggregate (type_id in manifest)
              → concrete BaseConnector subclass (McpConnector, LocalCliConnector, etc.)

        Called once during startup(). Safe to call multiple times (idempotent).
        """
        try:
            from ..connectors.mcp.connector import McpConnector
            self.connector_factory.register_connector_type("mcp", McpConnector)
            _logger.info("ConnectorRuntime: registered connector type 'mcp'.")
        except ImportError as e:
            _logger.warning("ConnectorRuntime: could not register 'mcp' connector type: %s", e)

        try:
            from ..connectors.local_cli.connector import LocalCliConnector
            self.connector_factory.register_connector_type("local_cli", LocalCliConnector)
            _logger.info("ConnectorRuntime: registered connector type 'local_cli'.")
        except ImportError as e:
            _logger.debug("ConnectorRuntime: 'local_cli' connector type not available: %s", e)

    def _rebuild_capability_index(self) -> None:
        """Rebuild the capability index from the current registry state."""
        self.capability_index.clear()
        for connector in self.registry.get_running():
            for cap_namespace in connector.manifest.capabilities:
                self.capability_index.add(cap_namespace, connector.connector_id)

    def handle_event(self, event: ConnectorEvent) -> None:
        """Handle events from the Event Bus."""
        if event.event_type == "health.failed":
            # P1 FIX: Instead of dropping the connector to FAILED,
            # route it through the canonical single-flight recovery.
            error_detail = event.data.get("error", "Unknown health probe failure")

            # Determine classification based on error detail
            from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorFailureClass
            error_lower = error_detail.lower()
            if "timeout" in error_lower:
                failure_class = ConnectorFailureClass.TIMEOUT
            elif "exited" in error_lower or "closed" in error_lower:
                failure_class = ConnectorFailureClass.PROCESS_EXIT
            elif "unauthorized" in error_lower or "credentials" in error_lower:
                failure_class = ConnectorFailureClass.CREDENTIAL_ERROR
            elif "not found" in error_lower or "configuration" in error_lower:
                failure_class = ConnectorFailureClass.CONFIGURATION_ERROR
            else:
                failure_class = ConnectorFailureClass.TRANSPORT_ERROR

            _logger.warning("ConnectorRuntime: intercepting health failure for '%s' as %s", event.connector_id, failure_class.value)
            self.handle_transport_failure(event.connector_id, failure_class, error_detail)

        elif event.event_type == "health.recovered":
            pass # Health recoveries are handled implicitly by successful initialize_and_verify

        _logger.debug(
            "ConnectorRuntime event handled: type=%s connector=%s severity=%s",
            event.event_type, event.connector_id, event.severity.value,
        )

    def _on_health_change(
        self,
        connector_id: str,
        suggested_state: ConnectorLifecycleState,
    ) -> None:
        """Handle health-triggered lifecycle transitions."""
        connector = self.registry.get(connector_id)
        if not connector:
            return

        _logger.info(
            "ConnectorRuntime: health change for '%s' → %s",
            connector_id, suggested_state.value,
        )
        result = self.lifecycle_manager.transition(connector, suggested_state, reason="health_monitor")
        if result.success:
            self._rebuild_capability_index()

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def __repr__(self) -> str:
        return (
            f"ConnectorRuntime("
            f"initialized={self._initialized}, "
            f"connectors={self.registry.count()}, "
            f"namespaces={self.capability_index.count()})"
        )
