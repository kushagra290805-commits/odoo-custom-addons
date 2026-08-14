from typing import List, Dict, Any
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorManifest
from odoo.addons.nexora_studio.services.connector.sdk.version import SDK_VERSION

def build_mcp_manifest(
    connector_id: str,
    display_name: str,
    capabilities: List[str],
    version: str = "1.0.0"
) -> ConnectorManifest:
    """
    Builds a ConnectorManifest for an MCP-backed connector.
    """
    return ConnectorManifest(
        connector_id=connector_id,
        display_name=display_name,
        connector_type_id="mcp",
        sdk_version=SDK_VERSION,
        version=version,
        capabilities=capabilities,
        transports=["stdio"]
    )
