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

class ReactBitsComponentProvider(BaseProvider):
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_react_bits", name="React Bits", category=ProviderCategory.COMPONENT, provider_version="1.0.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://reactbits.dev")
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
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", f"https://raw.githubusercontent.com/DavidHDev/react-bits/main/src/components/{comp_id}.jsx", timeout=10)
                if not r.ok:
                    r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", f"https://raw.githubusercontent.com/DavidHDev/react-bits/main/src/components/{comp_id}.tsx", timeout=10)
                r.raise_for_status()
                return ProviderExecutionResult(True, {"source": "React Bits", "component_id": comp_id, "code": r.text, "dependencies": [], "tokens": {"colors": [], "typography": []}}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"React Bits API Error: {str(e)}", self.metadata.provider_id)
        elif operation == "search_components":
            query = payload.get("query", "").lower()
            start = time.time()
            curated_list = [
                "SpotlightCard", "FuzzyText", "SplashCursor", "BlobCursor", 
                "StarBorder", "RotatingText", "TrueFocus", "Magnet", 
                "CircularText", "GradientText", "DecayCard", "TiltedCard",
                "TextPressure", "VariableProximity", "SplitText", "BlurText",
                "Waves", "Hyperspeed", "GridDistortion", "Squares", "FlowingMenu"
            ]
            results = []
            for comp in curated_list:
                if query in comp.lower() or not query:
                    results.append({
                        "component_id": comp,
                        "name": comp,
                        "score": 0.9 if query == comp.lower() else 0.5,
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
