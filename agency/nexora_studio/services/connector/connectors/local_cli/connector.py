from odoo.addons.nexora_studio.services.connector.sdk.connector_components import ComponentConnector
from .transport import LocalCliTransport
from .provider import LocalCliProvider
from .health import LocalCliHealthCheck

class LocalCliConnector(ComponentConnector):
    """
    The root connector class for Local CLI.
    Utilizes ComponentConnector to eliminate delegation boilerplate.
    """
    
    def __init__(self):
        transport = LocalCliTransport()
        provider = LocalCliProvider(transport)
        health_check = LocalCliHealthCheck()
        super().__init__(provider=provider, transport=transport, health_check=health_check)
