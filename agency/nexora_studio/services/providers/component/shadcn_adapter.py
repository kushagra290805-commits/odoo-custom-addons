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

# Phase 47.24 (ADR-0076): the shadcn registry moved from /registry/... to
# /r/... (verified live). Public registry â€” no authentication required.
SHADCN_REGISTRY_BASE = "https://ui.shadcn.com/r"
SHADCN_INDEX_URL = SHADCN_REGISTRY_BASE + "/index.json"

# Dependency versions for the registry payloads, which list dependency
# names without versions. Known-good current versions; emit deterministically.
SHADCN_DEP_VERSIONS = {
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.3.1",
    "tailwindcss": "^4.1.11",
    "@tailwindcss/vite": "^4.1.11",
    "@radix-ui/react-slot": "^1.2.3",
    "@radix-ui/react-accordion": "^1.2.2",
    "@radix-ui/react-tabs": "^1.1.4",
    "@radix-ui/react-avatar": "^1.1.3",
    "@radix-ui/react-separator": "^1.1.2",
}


def resolve_shadcn_item_url(component_id: str, style: str = "default") -> str:
    """Deterministic registry item URL for a component id."""
    return f"{SHADCN_REGISTRY_BASE}/styles/{style}/{component_id}.json"


class ShadcnComponentProvider(BaseProvider):
    """Production adapter for Shadcn/UI."""
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_shadcn", name="Shadcn/UI Component Source", category=ProviderCategory.COMPONENT, provider_version="1.1.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://ui.shadcn.com")
    def check_health(self) -> ProviderHealth:
        try:
            r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", SHADCN_INDEX_URL)
            return ProviderHealth(status="healthy" if r.ok else "degraded", latency_ms=r.elapsed.total_seconds()*1000, error_rate_24h=0.0, last_checked=datetime.utcnow())
        except Exception:
            return ProviderHealth(status="degraded", latency_ms=5000, error_rate_24h=0.0, last_checked=datetime.utcnow(), details="Unreachable")
    def discover_capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability("import_component", "import_component", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {}),
            ProviderCapability("search_components", "search_components", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {})
        ]
    def fetch_registry_item(self, component_id: str, style: str = "default") -> Dict[str, Any]:
        """Retrieve and parse a registry item (files[].content preserved).

        Phase 47.24 (ADR-0076): the registry payload's files[] carry the
        real source; dependencies are name lists resolved against
        SHADCN_DEP_VERSIONS. Raises ProviderExecutionError on
        missing/invalid components.
        """
        if not component_id:
            raise ProviderExecutionError("component_id required", self.metadata.provider_id)
        url = resolve_shadcn_item_url(component_id, style)
        try:
            r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", url)
            r.raise_for_status()
            data = r.json()
        except ProviderExecutionError:
            raise
        except Exception as e:
            raise ProviderExecutionError(
                f"Shadcn registry error for '{component_id}': {e}",
                self.metadata.provider_id)
        if not isinstance(data, dict) or not data.get("files"):
            raise ProviderExecutionError(
                f"Shadcn registry item '{component_id}' returned no files", self.metadata.provider_id)
        files = [
            {"path": f.get("path", ""), "content": f.get("content", "") or ""}
            for f in data.get("files", [])
            if isinstance(f, dict)
        ]
        code = "\n".join(f.get("content", "") for f in files)
        dependencies = [
            {"name": dep, "version": SHADCN_DEP_VERSIONS.get(dep, "latest")}
            for dep in (data.get("dependencies") or [])
            if dep
        ]
        registry_dependencies = [
            {"name": dep, "version": SHADCN_DEP_VERSIONS.get(dep, "latest")}
            for dep in (data.get("registryDependencies") or [])
            if dep
        ]
        return {
            "source": "Shadcn/UI",
            "component_id": component_id,
            "name": data.get("name", component_id),
            "type": data.get("type", "registry:ui"),
            "files": files,
            "code": code,
            "dependencies": dependencies,
            "registry_dependencies": registry_dependencies,
            "tokens": {"colors": [], "typography": []},
        }
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
                data = self.fetch_registry_item(comp_id, style)
                return ProviderExecutionResult(True, data, {}, (time.time()-start)*1000)
            except ProviderExecutionError:
                raise
            except Exception as e:
                raise ProviderExecutionError(f"Shadcn API Error: {str(e)}", self.metadata.provider_id)
        elif operation == "search_components":
            query = payload.get("query", "").lower()
            try:
                start = time.time()
                r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", SHADCN_INDEX_URL)
                r.raise_for_status()
                data = r.json()
                results = []
                for comp in data:
                    name = comp.get("name", "").lower()
                    if query in name or not query:
                        results.append({
                            "component_id": comp.get("name"),
                            "name": comp.get("name", "").title(),
                            "type": comp.get("type", "registry:ui"),
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
        return self.fetch_registry_item(resource_id, kwargs.get("style", "default"))
        
    def search(self, query: str, **kwargs) -> List[Any]:
        return []

