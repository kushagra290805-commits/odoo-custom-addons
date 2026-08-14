from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport

class McpHealthCheck:
    """
    Health check provider for MCP connectors.
    Verifies the connection by calling tools.list.
    """
    def __init__(self, transport: McpTransport):
        self.transport = transport

    def check_health(self, context: ExecutionContext) -> bool:
        if not self.transport.is_connected():
            return False
            
        try:
            self.transport.list_tools()
            return True
        except Exception:
            return False
