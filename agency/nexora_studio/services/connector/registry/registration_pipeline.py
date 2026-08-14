from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from typing import Any, Optional

from odoo.addons.nexora_studio.services.connector.domain.models import Connector, ConnectorManifest
from odoo.addons.nexora_studio.services.connector.registry.manifest_validator import ManifestValidator
from odoo.addons.nexora_studio.services.connector.registry.compatibility_validator import CompatibilityValidator
from odoo.addons.nexora_studio.services.connector.registry.connector_registry import ConnectorRegistry
from odoo.addons.nexora_studio.services.connector.registry.capability_index import ConnectorCapabilityIndex
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError
from odoo.addons.nexora_studio.services.connector.sdk.telemetry_port import ConnectorTelemetryPort
from odoo.addons.nexora_studio.services.connector.runtime.telemetry_recorder import InMemoryTelemetryRecorder
from odoo.addons.nexora_studio.services.connector.sdk.version import SDK_VERSION, MIN_RUNTIME_VERSION

_logger = get_logger(__name__)

class SDKVersionValidator:
    def validate(self, manifest: ConnectorManifest) -> None:
        if not hasattr(manifest, 'sdk_version') or not manifest.sdk_version:
            # Manifest validator will already catch this, but just in case
            raise ConnectorConfigurationError(
                error_code="SDK_VERSION_MISSING",
                user_safe_message="Manifest is missing sdk_version.",
                technical_message="Manifest is missing sdk_version."
            )
        
        # Simple semantic version check for demo
        # A real implementation would parse the semantic version using packaging.version
        if manifest.sdk_version < MIN_RUNTIME_VERSION:
            raise ConnectorConfigurationError(
                error_code="SDK_VERSION_INCOMPATIBLE",
                user_safe_message=f"Connector SDK version {manifest.sdk_version} is incompatible with runtime.",
                technical_message=f"Connector requires SDK {manifest.sdk_version}, but runtime requires at least {MIN_RUNTIME_VERSION}."
            )

class ConfigurationValidator:
    def validate(self, manifest: ConnectorManifest) -> None:
        pass # Stub for Phase 27

class DependencyValidator:
    def validate(self, manifest: ConnectorManifest) -> None:
        pass # Stub for Phase 27

class SecurityValidator:
    def validate(self, manifest: ConnectorManifest) -> None:
        pass # Stub for Phase 27

class ConnectorRegistrationPipeline:
    """
    Orchestrates the admission of a Connector into the Connector Platform.
    Enforces all validations before any mutation occurs.
    """
    
    def __init__(
        self, 
        registry: ConnectorRegistry, 
        capability_index: ConnectorCapabilityIndex,
        telemetry: Optional[ConnectorTelemetryPort] = None
    ):
        self._registry = registry
        self._capability_index = capability_index
        self.telemetry = telemetry or InMemoryTelemetryRecorder()
        
        self.manifest_validator = ManifestValidator()
        self.sdk_version_validator = SDKVersionValidator()
        self.configuration_validator = ConfigurationValidator()
        self.dependency_validator = DependencyValidator()
        self.compatibility_validator = CompatibilityValidator()
        self.security_validator = SecurityValidator()

    def execute(self, connector: Connector) -> None:
        """
        Executes the registration pipeline.
        Raises ConnectorConfigurationError if any step fails.
        """
        manifest = connector.manifest
        
        # 1. Validation Phase
        self.manifest_validator.validate(manifest)
        self.sdk_version_validator.validate(manifest)
        self.configuration_validator.validate(manifest)
        self.dependency_validator.validate(manifest)
        self.compatibility_validator.validate(manifest)
        self.security_validator.validate(manifest)
        
        # 2. Registration Execution Phase
        self._registry.register(connector)
        
        # 3. Indexing Phase
        for cap in connector.manifest.capabilities:
            self._capability_index.add(cap, connector.connector_id)
            
        self.telemetry.record_counter("registration.count", tags={"connector_id": connector.connector_id})
        _logger.info(
            "ConnectorRegistrationPipeline: registered connector '%s' with %d capabilities.", 
            connector.connector_id, 
            len(connector.manifest.capabilities)
        )
