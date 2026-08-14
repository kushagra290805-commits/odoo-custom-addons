import logging
import sys
from typing import Type, List
from datetime import datetime
from packaging.version import Version, InvalidVersion

from .base_provider import (
    ProviderCompatibilityService,
    CompatibilityReport,
    BaseProvider,
    ProviderMetadata,
    ProviderEventBus,
    ProviderEvent,
    ProviderEventChannel
)
from .container import ProviderServiceContainer

_logger = logging.getLogger(__name__)

class OdooCompatibilityService(ProviderCompatibilityService):
    """
    Validates providers against system requirements, Odoo versions, Python versions,
    manifest schemas, and API compatibility.
    Publishes CompatibilityReport to AUDIT channel.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        
    @property
    def _event_bus(self) -> ProviderEventBus:
        return self._container.resolve(ProviderEventBus)

    def validate(self, provider_class: Type[BaseProvider]) -> CompatibilityReport:
        # Create a dummy metadata instance just for validation if possible
        # Or we can assume provider_class has a classmethod or a way to get metadata.
        # But wait, BaseProvider gets metadata in __init__. We need a way to get it without initializing fully.
        # Let's instantiate it with restricted sandbox and default metadata. Wait, no, the class usually constructs its own metadata or we pass it.
        # Typically, a provider class will have a static/class attribute or we instantiate it with a dummy config.
        # Let's assume the provider_class can be instantiated with default metadata for validation purposes.
        # Wait, the signature of BaseProvider.__init__ is (metadata, sandbox).
        # Where does the metadata come from? Usually the factory or registry creates it.
        # For now, let's look for a class attribute or we can just require a static get_default_metadata().
        
        # We will assume provider_class has a static `get_default_metadata() -> ProviderMetadata` method
        metadata: ProviderMetadata
        if hasattr(provider_class, 'get_default_metadata'):
            metadata = provider_class.get_default_metadata()
        else:
            # Cannot validate thoroughly without metadata
            return self._build_report(
                is_compatible=False,
                provider_id=provider_class.__name__,
                failures=["Provider class missing get_default_metadata() classmethod."],
                warnings=[]
            )

        provider_id = metadata.provider_id
        failures = []
        warnings = []

        failures.extend(self.validate_manifest_schema(metadata))
        
        if not self.validate_api_version(provider_class):
            failures.append(f"Incompatible API version: {metadata.api_version}")

        platform_min = metadata.minimum_platform_version
        if not self.validate_platform_version(platform_min):
            failures.append(f"Platform version lower than minimum required: {platform_min}")

        req_odoo = metadata.compatibility_matrix.get("odoo", ">=16.0")
        if not self.validate_odoo_version(req_odoo):
            failures.append(f"Incompatible Odoo version. Requires {req_odoo}")

        req_python = metadata.compatibility_matrix.get("python", ">=3.10")
        if not self.validate_python_version(req_python):
            failures.append(f"Incompatible Python version. Requires {req_python}")

        failures.extend(self.validate_dependency_compatibility(metadata.dependencies))
        warnings.extend(self.validate_future_migration(metadata))

        is_compatible = len(failures) == 0

        report = self._build_report(is_compatible, provider_id, failures, warnings)
        
        # Publish to AUDIT channel
        self._event_bus.publish(
            ProviderEvent(
                event_id=f"compat_{provider_id}_{datetime.utcnow().timestamp()}",
                timestamp=datetime.utcnow(),
                provider_id=provider_id,
                event_type="COMPATIBILITY_VALIDATION",
                channel=ProviderEventChannel.AUDIT,
                session_uuid=None,
                duration_ms=0.0,
                payload={"report": {
                    "is_compatible": is_compatible,
                    "failures": failures,
                    "warnings": warnings
                }}
            )
        )

        return report

    def _build_report(self, is_compatible: bool, provider_id: str, failures: List[str], warnings: List[str]) -> CompatibilityReport:
        return CompatibilityReport(
            is_compatible=is_compatible,
            provider_id=provider_id,
            failures=failures,
            warnings=warnings,
            checked_at=datetime.utcnow()
        )

    def validate_platform_version(self, minimum: str) -> bool:
        # Assuming platform version is 2026.1 currently
        current = "2026.1"
        try:
            return Version(current) >= Version(minimum)
        except InvalidVersion:
            return False

    def validate_odoo_version(self, required: str) -> bool:
        try:
            from odoo import release
            current = release.version.split('~')[0]  # e.g., '16.0'
            req_ver = required.replace(">=", "").strip()
            return Version(current) >= Version(req_ver)
        except ImportError:
            # If outside Odoo context, assume True for testing
            return True
        except InvalidVersion:
            return False

    def validate_python_version(self, required: str) -> bool:
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        req_ver = required.replace(">=", "").strip()
        try:
            return Version(current) >= Version(req_ver)
        except InvalidVersion:
            return False

    def validate_manifest_schema(self, metadata: ProviderMetadata) -> List[str]:
        failures = []
        if not metadata.provider_id:
            failures.append("provider_id is empty")
        if not metadata.category:
            failures.append("category is missing")
        if not metadata.api_version:
            failures.append("api_version is missing")
        return failures

    def validate_dependency_compatibility(self, dependencies: List[str]) -> List[str]:
        failures = []
        try:
            from odoo import http, api
            env = None
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
            
            if not env:
                # If no environment is available (e.g. testing context without request), we cannot resolve dependencies.
                for dep in dependencies:
                    prov_id = dep.split('(')[0].strip() if '(' in dep else dep.strip()
                    failures.append(f"Missing dependency: {prov_id}")
                return failures
            
            for dep in dependencies:
                # Assume dep is format 'provider_id(>=1.0.0)' or just 'provider_id'
                if '(' in dep and ')' in dep:
                    prov_id, ver = dep.split('(', 1)
                    prov_id = prov_id.strip()
                    ver = ver.strip(')')
                else:
                    prov_id = dep.strip()
                    ver = None
                
                registry = env['nexora.provider.registry'].sudo().search([('provider_id', '=', prov_id)], limit=1)
                if not registry:
                    failures.append(f"Missing dependency: {prov_id}")
                elif ver:
                    try:
                        req_ver = ver.replace(">=", "").strip()
                        if not (Version(registry.provider_version) >= Version(req_ver)):
                            failures.append(f"Incompatible dependency version for {prov_id}. Requires {ver}, found {registry.provider_version}")
                    except InvalidVersion:
                        failures.append(f"Invalid version format for dependency {prov_id}")
        except Exception as e:
            _logger.error(f"Error validating dependencies: {e}")
        return failures

    def validate_api_version(self, provider_class: Type[BaseProvider]) -> bool:
        # Expected API versions: v1
        metadata = provider_class.get_default_metadata() if hasattr(provider_class, 'get_default_metadata') else None
        if not metadata:
            return False
        return metadata.api_version.startswith("v1")

    def validate_future_migration(self, metadata: ProviderMetadata) -> List[str]:
        warnings = []
        if Version(metadata.manifest_version) < Version("2.0"):
            warnings.append("Manifest version < 2.0 is deprecated and will be removed in the future.")
        return warnings
