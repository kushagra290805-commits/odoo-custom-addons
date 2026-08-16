from typing import Optional, Dict, Any
from odoo.addons.nexora_studio.services.connector.sdk.connector_components import ComponentConnector
from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport
from odoo.addons.nexora_studio.services.connector.connectors.mcp.provider import McpProvider
from odoo.addons.nexora_studio.services.connector.connectors.mcp.health import McpHealthCheck

class McpConnector(ComponentConnector):
    """
    Standard MCP Connector using stdio transport.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}

        mcp_config = McpConfiguration(
            command=config.get("command", ""),
            transport=config.get("transport", "stdio"),
            args=config.get("args", []),
            env=config.get("env", None),
            trace_file=config.get("trace_file", None),
            auth_location=config.get("auth_location", "none"),
            auth_name=config.get("auth_name", ""),
            auth_scheme=config.get("auth_scheme", "none"),
            auth_secret=config.get("auth_secret", ""),
        )
        transport = McpTransport(mcp_config)
        provider = McpProvider(transport)
        health_check = McpHealthCheck(transport)
        super().__init__(
            provider=provider,
            transport=transport,
            health_check=health_check
        )
