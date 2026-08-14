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

class ShadcnComponentProvider(BaseProvider):
    """Production adapter for Shadcn/UI."""
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_shadcn", name="Shadcn/UI Component Source", category=ProviderCategory.COMPONENT, provider_version="1.0.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://ui.shadcn.com")
    def check_health(self) -> ProviderHealth:
        try:
            r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", "https://ui.shadcn.com/registry/index.json", timeout=5)
            return ProviderHealth(status="healthy" if r.ok else "degraded", latency_ms=r.elapsed.total_seconds()*1000, error_rate_24h=0.0, last_checked=datetime.utcnow())
        except Exception:
            return ProviderHealth(status="degraded", latency_ms=5000, error_rate_24h=0.0, last_checked=datetime.utcnow(), details="Unreachable")
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
            style = payload.get("style", "default")
            if not comp_id: raise ProviderExecutionError("component_id required", self.metadata.provider_id)
            try:
                start = time.time()
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", f"https://ui.shadcn.com/registry/styles/{style}/{comp_id}.json", timeout=10)
                r.raise_for_status()
                data = r.json()
                code = "\n".join([f.get("content", "") for f in data.get("files", [])])
                return ProviderExecutionResult(True, {"source": "Shadcn/UI", "component_id": comp_id, "code": code, "dependencies": data.get("dependencies", []), "registry_dependencies": data.get("registryDependencies", []), "tokens": {"colors": [], "typography": []}}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"Shadcn API Error: {str(e)}", self.metadata.provider_id)
        elif operation == "search_components":
            query = payload.get("query", "").lower()
            try:
                start = time.time()
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", "https://ui.shadcn.com/registry/index.json", timeout=10)
                r.raise_for_status()
                data = r.json()
                results = []
                for comp in data:
                    name = comp.get("name", "").lower()
                    if query in name or not query:
                        results.append({
                            "component_id": comp.get("name"),
                            "name": comp.get("name", "").title(),
                            "score": 0.9 if query == name else 0.5,
                            "compatibility_report": {"is_compatible": True}
                        })
                return ProviderExecutionResult(True, {"components": results[:10]}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"Shadcn Search Error: {str(e)}", self.metadata.provider_id)
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
