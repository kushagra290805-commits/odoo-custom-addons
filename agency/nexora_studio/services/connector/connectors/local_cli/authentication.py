from odoo.addons.nexora_studio.services.connector.sdk.authentication import BaseAuthenticationProvider
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext

class LocalCliAuthentication(BaseAuthenticationProvider):
    """
    Implements the authentication contract for Local CLI.
    Local CLI inherently runs under the host process privileges, so no external Auth is required.
    """
    
    def authenticate(self, context: ExecutionContext) -> bool:
        # Always successful because no external authentication is required.
        return True

    def refresh_session(self, context: ExecutionContext) -> bool:
        return True

    def revoke_session(self, context: ExecutionContext) -> None:
        pass
