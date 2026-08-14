from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorManifest
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError

class CompatibilityValidator:
    """
    Verifies that the connector's manifest is compatible with the current runtime environment.
    """
    
    def __init__(self, platform_version: str = "1.0.0", supported_transports: list = None):
        self.platform_version = platform_version
        # By default, pretend the platform supports all transports requested, 
        # but in a real platform we'd check registered transport types.
        self.supported_transports = supported_transports or ["local_subprocess", "http", "stdio", "unix_socket", "tcp"]

    def validate(self, manifest: ConnectorManifest) -> None:
        """
        Raises ConnectorConfigurationError if incompatible.
        """
        errors = []
        
        # Validate transports
        for transport in manifest.transports:
            if transport not in self.supported_transports:
                errors.append(f"Transport '{transport}' is not supported by the current platform.")
                
        # Future: validate SDK versions, platform versions from manifest.metadata
        min_platform_version = manifest.metadata.get("min_platform_version")
        if min_platform_version:
            # Simple check (real semver needed in production)
            if min_platform_version > self.platform_version:
                errors.append(f"Connector requires platform >= {min_platform_version}, but running {self.platform_version}")

        if errors:
            raise ConnectorConfigurationError(
                error_code="COMPATIBILITY_INVALID",
                user_safe_message=f"Compatibility validation failed for {manifest.connector_id}.",
                technical_message="; ".join(errors)
            )
