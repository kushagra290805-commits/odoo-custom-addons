from odoo import tools
from odoo.addons.nexora_studio.services.providers.network_client import ProviderNetworkClient
import logging
_logger = logging.getLogger(__name__)
import time
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
from typing import Dict, Any, List
from datetime import datetime
from odoo.addons.nexora_studio.services.providers.base_provider import (
    BaseProvider, ProviderMetadata, ProviderCapability, ProviderExecutionResult, 
    ProviderExecutionContext, ProviderHealth, ProviderCategory, ProviderExecutionError
)

class FigmaComponentProvider(BaseProvider):
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_figma", name="Figma", category=ProviderCategory.COMPONENT, provider_version="1.0.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://figma.com")
    def check_health(self) -> ProviderHealth:
        return ProviderHealth(status="healthy", latency_ms=10.0, error_rate_24h=0.0, last_checked=datetime.utcnow())
    def discover_capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability("import_component", "import_component", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {})]
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        operation = request.payload.get('operation') or request.namespace.split('.')[-1]
        payload = request.payload
        context = request.context
        if operation == "import_component":
            file_key = payload.get("file_key")
            node_id = payload.get("node_id")
            token = tools.config.get(self.metadata.provider_id + "_token", context.auth.get_token() if context.auth else None)
            if not file_key or not node_id or not token: raise ProviderExecutionError("file_key, node_id, token required", self.metadata.provider_id)
            try:
                start = time.time()
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", f"https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}", headers={"X-Figma-Token": token}, timeout=10)
                r.raise_for_status()
                node_data = r.json().get("nodes", {}).get(node_id, {}).get("document", {})
                code = f"/* Generated from Figma Node {node_id} */\nconst FigmaNode = () => {{ return <div style={{{{ width: '{node_data.get('absoluteBoundingBox', {}).get('width')}px' }}}}>{{/* Content */}}</div> }};\nexport default FigmaNode;"
                return ProviderExecutionResult(True, {"source": "Figma", "component_id": node_id, "code": code, "raw_node": node_data, "tokens": {"colors": [], "typography": []}}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"Figma API Error: {str(e)}", self.metadata.provider_id)
        raise ProviderExecutionError(f"Unsupported: {operation}", self.metadata.provider_id)


    def initialize(self, config=None) -> None:
        return None
        
    def authenticate(self, credentials: Dict[str, str]) -> bool:
        return True
        
    def cleanup(self) -> None:
        return None
        
    def fetch(self, resource_id: str, **kwargs) -> Any:
        return self.execute("import_component", {"component_id": resource_id}, kwargs.get("context"))
        
    def search(self, query: str, **kwargs) -> List[Any]:
        return []
