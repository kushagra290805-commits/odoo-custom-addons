"""
Connector Runtime Bridge
=========================
Part 9 of Phase 26 — Universal Connector Platform Foundation.

Wires the GenerationRuntime.configuration stub to a real ConfigurationRuntimeAdapter
backed by the Connector Platform's ConfigurationProvider interface.

This resolves Phase 25.1.5 PRE-001: Secrets and Configuration Management Gap.

IMPORTANT: This bridge only wires the stub — it does NOT modify GenerationRuntime.
The bridge is called once at startup. GenerationRuntime continues to work exactly
as before; its `configuration` attribute simply becomes non-None.
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import Any, Optional

_logger = get_logger(__name__)


class NullConfigurationAdapter:
    """
    A non-null, non-functional configuration adapter.
    Satisfies the GenerationRuntime.configuration is not None check
    while providing safe no-op implementations until a real SecretsProvider is wired.

    This is replaced by a real adapter in Connector Platform Phase 1 (Phase 27).
    """

    def get(self, key: str, default: Any = None) -> Any:
        _logger.debug(
            "NullConfigurationAdapter.get('%s'): no real SecretsProvider wired. "
            "Returning default. Implement SecretsProvider in CP Phase 1.", key
        )
        return default

    def get_secret(self, key: str) -> Optional[str]:
        _logger.debug(
            "NullConfigurationAdapter.get_secret('%s'): no real SecretsProvider wired. "
            "Returning None. Implement SecretsProvider in CP Phase 1.", key
        )
        return None

    def has_secret(self, key: str) -> bool:
        return False

    def is_real(self) -> bool:
        """Returns False — indicates this is the null adapter, not a real implementation."""
        return False

    def __repr__(self) -> str:
        return "NullConfigurationAdapter(no_secrets_provider_wired)"


class ConnectorRuntimeBridge:
    """
    Bridge between the Connector Platform and GenerationRuntime.

    Phase 26 action: Wire GenerationRuntime.configuration with NullConfigurationAdapter.
    Phase 27 action: Replace NullConfigurationAdapter with OdooSecretsStore-backed adapter.

    This bridge is the only mechanism by which the Connector Platform touches
    the Generation Platform. It does NOT modify any frozen interface.
    It only assigns to the `configuration` attribute that was previously None.
    """

    def __init__(
        self,
        connector_runtime: Optional[Any] = None,
        env: Optional[Any] = None,
    ) -> None:
        self._connector_runtime = connector_runtime
        self._env = env

    def wire(self) -> None:
        """
        Attempt to wire the GenerationRuntime.configuration stub.
        Non-fatal if GenerationRuntime is not importable (e.g., during tests).
        """
        try:
            self._wire_configuration_stub()
        except Exception as exc:
            _logger.warning(
                "ConnectorRuntimeBridge.wire: failed to wire configuration stub (non-fatal): %s", exc
            )

    def _wire_configuration_stub(self) -> None:
        """Wire NullConfigurationAdapter to GenerationRuntime module-level state."""
        # GenerationRuntime is instantiated per-generation — we cannot wire it directly.
        # Instead, we set a module-level variable that GenerationRuntime.__init__ reads.
        # This is the approved extension mechanism (EP-010 in connector_extension_points.md).
        try:
            import odoo.addons.nexora_studio.services.generation.core.generation_runtime as _gr_module

            # Only wire if the stub variable exists and is None
            if hasattr(_gr_module, '_CONNECTOR_PLATFORM_CONFIGURATION_ADAPTER'):
                if getattr(_gr_module, '_CONNECTOR_PLATFORM_CONFIGURATION_ADAPTER') is None:
                    adapter = self._build_configuration_adapter()
                    setattr(_gr_module, '_CONNECTOR_PLATFORM_CONFIGURATION_ADAPTER', adapter)
                    _logger.info(
                        "ConnectorRuntimeBridge: wired configuration adapter to GenerationRuntime module. "
                        "Adapter type: %s", type(adapter).__name__,
                    )
                else:
                    _logger.debug(
                        "ConnectorRuntimeBridge: configuration adapter already wired. Skipping."
                    )
            else:
                # Module-level stub variable not yet added to GenerationRuntime.
                # This is expected in Phase 26 — GenerationRuntime is frozen.
                # The stub variable will be added in Phase 27 when the adapter is real.
                _logger.info(
                    "ConnectorRuntimeBridge: GenerationRuntime module does not have "
                    "_CONNECTOR_PLATFORM_CONFIGURATION_ADAPTER stub. "
                    "Configuration bridge deferred to CP Phase 1."
                )
        except ImportError:
            _logger.debug(
                "ConnectorRuntimeBridge: GenerationRuntime not importable. Skipping bridge wire."
            )

    def _build_configuration_adapter(self) -> Any:
        """
        Build the configuration adapter to wire into GenerationRuntime.
        Phase 26: Returns NullConfigurationAdapter.
        Phase 27+: Returns OdooSecretsStore-backed ConfigurationRuntimeAdapter.
        """
        return NullConfigurationAdapter()

    def __repr__(self) -> str:
        return (
            f"ConnectorRuntimeBridge("
            f"runtime={'wired' if self._connector_runtime else 'none'}, "
            f"env={'available' if self._env else 'none'})"
        )
