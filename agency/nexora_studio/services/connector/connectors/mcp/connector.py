from typing import Optional, Dict, Any
from odoo.addons.nexora_studio.services.connector.sdk.connector_components import ComponentConnector
from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport
from odoo.addons.nexora_studio.services.connector.connectors.mcp.provider import McpProvider
from odoo.addons.nexora_studio.services.connector.connectors.mcp.health import McpHealthCheck
from odoo.addons.nexora_studio.services.connector.connectors.mcp.pool import SessionTransportPool

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
            allowed_request_context_fields=config.get("allowed_request_context_fields", []),
            auth_location=config.get("auth_location", "none"),
            auth_name=config.get("auth_name", ""),
            auth_scheme=config.get("auth_scheme", "none"),
            auth_secret=config.get("auth_secret", ""),
            session_binding=config.get("session_binding", "none"),
            session_binding_field=config.get("session_binding_field", ""),
            session_binding_location=config.get("session_binding_location", "query"),
            # Phase 44.2 (W8): honor operator-configured timeout and stdio cwd.
            timeout_seconds=int(config.get("timeout_seconds", 60) or 60),
            working_directory=config.get("working_directory") or None,
        )
        
        transport = McpTransport(mcp_config)
        
        pool = None
        if mcp_config.session_binding == 'request_context':
            pool = SessionTransportPool(mcp_config)
            
        provider = McpProvider(mcp_config, transport, pool)
        health_check = McpHealthCheck(transport)
        
        super().__init__(
            provider=provider,
            transport=transport,
            health_check=health_check
        )
        self._pool = pool
        
    def shutdown(self, context: Optional[Any] = None) -> None:
        super().shutdown(context=context)
        if getattr(self, '_pool', None):
            self._pool.shutdown_all()
