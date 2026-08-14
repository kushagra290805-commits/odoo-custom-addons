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

class TwentyFirstDevComponentProvider(BaseProvider):
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_21st_dev", name="21st.dev", category=ProviderCategory.COMPONENT, provider_version="1.0.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://21st.dev")
    def check_health(self) -> ProviderHealth:
        return ProviderHealth(status="healthy", latency_ms=10.0, error_rate_24h=0.0, last_checked=datetime.utcnow())
    def discover_capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability("import_component", "import_component", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {}),
            ProviderCapability("search_components", "search_components", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {})
        ]
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        operation = request.payload.get('operation') or request.namespace.split('.')[-1]
        payload = request.payload
        context = request.context
        if operation == "import_component":
            comp_id = payload.get("component_id")
            if not comp_id: raise ProviderExecutionError("component_id required", self.metadata.provider_id)
            try:
                start = time.time()
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", f"https://21st.dev/api/components/{comp_id}", timeout=10)
                r.raise_for_status()
                data = r.json()
                code = data.get("code", f"/* Fetched from 21st.dev: {comp_id} */\n" + "\n".join([f.get("content", "") for f in data.get("files", [])]))
                return ProviderExecutionResult(True, {"source": "21st.dev", "component_id": comp_id, "code": code, "dependencies": data.get("dependencies", []), "tokens": {"colors": [], "typography": []}}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"21st.dev API Error: {str(e)}", self.metadata.provider_id)
        elif operation == "search_components":
            query = payload.get("query", "").lower()
            start = time.time()
            curated_list = [
                "button", "card", "input", "nav", "dialog", 
                "dropdown", "accordion", "slider", "switch", "tooltip",
                "badge", "avatar", "tabs", "toast", "skeleton"
            ]
            results = []
            for comp in curated_list:
                if query in comp or not query:
                    results.append({
                        "component_id": comp,
                        "name": comp.title(),
                        "score": 0.9 if query == comp else 0.5,
                        "compatibility_report": {"is_compatible": True}
                    })
            return ProviderExecutionResult(True, {"components": results[:10]}, {}, (time.time()-start)*1000)
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
