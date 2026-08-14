import re
from typing import List, Tuple
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorManifest
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError

class ManifestValidator:
    """
    Validates a ConnectorManifest payload for structural and logical correctness.
    """
    
    # Simple regex for valid connector IDs (e.g. github_mcp, core.local_cli, mcp.github)
    ID_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")
    
    # Simple semantic versioning check
    VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$")
    
    # Capability namespace pattern (e.g. shell.execute)
    CAPABILITY_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")

    def validate(self, manifest: ConnectorManifest) -> None:
        """
        Validates the manifest.
        Raises ConnectorConfigurationError if invalid.
        """
        errors = []

        # 1. Required Fields & ID Format
        if not manifest.connector_id:
            errors.append("connector_id is required.")
        elif not self.ID_PATTERN.match(manifest.connector_id):
            errors.append(f"Invalid connector_id '{manifest.connector_id}'. Must match pattern {self.ID_PATTERN.pattern}")

        if not manifest.connector_type_id:
            errors.append("connector_type_id is required.")
            
        if not manifest.version:
            errors.append("version is required.")
        elif not self.VERSION_PATTERN.match(manifest.version):
            errors.append(f"Invalid version '{manifest.version}'. Must be semantic versioning.")
            
        if not hasattr(manifest, 'sdk_version') or not manifest.sdk_version:
            errors.append("sdk_version is required.")
        elif not self.VERSION_PATTERN.match(manifest.sdk_version):
            errors.append(f"Invalid sdk_version '{manifest.sdk_version}'. Must be semantic versioning.")

        # 2. Capabilities
        if not manifest.capabilities:
            errors.append("At least one capability must be declared.")
        else:
            seen = set()
            for cap in manifest.capabilities:
                if not self.CAPABILITY_PATTERN.match(cap):
                    errors.append(f"Invalid capability namespace '{cap}'.")
                if cap in seen:
                    errors.append(f"Duplicate capability declared: '{cap}'.")
                seen.add(cap)

        # 3. Transports
        if not manifest.transports:
            errors.append("At least one transport must be declared.")

        # 4. Dependency Declarations
        if hasattr(manifest, 'dependencies') and manifest.dependencies:
            for dep in manifest.dependencies:
                if not dep.depends_on_connector_id:
                    errors.append("Dependency missing 'depends_on_connector_id'.")

        if errors:
            raise ConnectorConfigurationError(
                error_code="MANIFEST_INVALID",
                user_safe_message=f"Manifest validation failed for {manifest.connector_id or 'Unknown'}.",
                technical_message="; ".join(errors)
            )
