from typing import Dict, Any, List
from odoo.addons.nexora_studio.services.connector.sdk.capability import BaseCapabilityProvider
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.sdk.transport import BaseTransport
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorExecutionError

from . import capabilities

class LocalCliProvider(BaseCapabilityProvider):
    """
    Routes capability execution requests to specific capability modules.
    Never directly invokes subprocesses; passes the transport to the capability logic.
    """
    
    def __init__(self, transport: BaseTransport):
        self.transport = transport
        self._registry = {
            "shell.execute": capabilities.execute_shell,
            "process.spawn": capabilities.spawn_process,
            "process.kill": capabilities.kill_process,
            "dependency.install": capabilities.install_dependency,
        }

    def list_capabilities(self, context: ExecutionContext) -> List[str]:
        return list(self._registry.keys())

    def has_capability(self, namespace: str, context: ExecutionContext) -> bool:
        return namespace in self._registry

    def execute(self, capability_namespace: str, parameters: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        handler = self._registry.get(capability_namespace)
        if not handler:
            from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ProviderException
            raise ProviderException(
                error_code="CAPABILITY_NOT_FOUND",
                user_safe_message=f"Capability '{capability_namespace}' is not supported.",
                technical_message=f"No capability handler registered for namespace '{capability_namespace}'."
            )
            
        return handler(parameters, context, self.transport)
