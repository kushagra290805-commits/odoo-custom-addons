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

import base64
class GitHubComponentProvider(BaseProvider):
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_github", name="GitHub", category=ProviderCategory.COMPONENT, provider_version="1.0.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://github.com")
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
            repo = payload.get("repo")
            path = payload.get("path")
            token = payload.get("token", "")
            if not repo or not path: raise ProviderExecutionError("repo and path required", self.metadata.provider_id)
            try:
                start = time.time()
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"} if token else {"Accept": "application/vnd.github.v3+json"}
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", f"https://api.github.com/repos/{repo}/contents/{path}", headers=headers, timeout=10)
                r.raise_for_status()
                data = r.json()
                content = base64.b64decode(data.get("content", "")).decode("utf-8") if data.get("encoding") == "base64" else ""
                return ProviderExecutionResult(True, {"source": "GitHub", "component_id": path, "code": content, "tokens": {"colors": [], "typography": []}}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"GitHub API Error: {str(e)}", self.metadata.provider_id)
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
