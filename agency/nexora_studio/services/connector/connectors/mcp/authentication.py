from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext

class McpAuthentication:
    """
    Dummy authentication provider for stdio MCP.
    Stdio processes generally do not require explicit authentication handshakes beyond filesystem permissions.
    """
    def authenticate(self, context: ExecutionContext) -> None:
        pass
