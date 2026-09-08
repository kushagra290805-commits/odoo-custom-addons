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

# Phase 47.24 (ADR-0076): React Bits moved from a source tree
# (src/components/<Name>.jsx â€” now dead, 404) to a published registry:
# public/r/<Name>-<Variant>.json on the repository main branch (verified
# live). The -JS-CSS variant is self-contained (JSX + CSS, zero external
# dependencies) â€” chosen so components need no Tailwind setup.
REACT_BITS_RAW_BASE = "https://raw.githubusercontent.com/DavidHDev/react-bits/main/public/r"
REACT_BITS_VARIANT = "JS-CSS"

# Curated registry entries relevant to marketing-site composition.
REACT_BITS_CURATED = [
    "SpotlightCard", "GradientText", "StarBorder", "TiltedCard",
    "DecayCard", "SplitText", "BlurText", "CircularText",
    "Magnet", "TrueFocus",
]


def resolve_react_bits_item_url(component_id: str) -> str:
    """Deterministic registry item URL (JS-CSS variant) for a component id."""
    return f"{REACT_BITS_RAW_BASE}/{component_id}-{REACT_BITS_VARIANT}.json"


class ReactBitsComponentProvider(BaseProvider):
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_react_bits", name="React Bits", category=ProviderCategory.COMPONENT, provider_version="1.1.0", manifest_version="1.0", api_version="v1.0", vendor_url="https://reactbits.dev")
    def check_health(self) -> ProviderHealth:
        return ProviderHealth(status="healthy", latency_ms=10.0, error_rate_24h=0.0, last_checked=datetime.utcnow())
    def discover_capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability("import_component", "import_component", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {}),
            ProviderCapability("search_components", "search_components", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {})
        ]
    def fetch_registry_item(self, component_id: str) -> Dict[str, Any]:
        """Retrieve and parse a React Bits registry item (JS-CSS variant).

        files[] carry the real source; the JSX and any CSS sidecars are
        preserved separately so consumers can materialize both. Raises
        ProviderExecutionError on missing/invalid components.
        """
        if not component_id:
            raise ProviderExecutionError("component_id required", self.metadata.provider_id)
        url = resolve_react_bits_item_url(component_id)
        try:
            r = ProviderNetworkClient.request(self.metadata.provider_id, "GET", url)
            r.raise_for_status()
            data = r.json()
        except ProviderExecutionError:
            raise
        except Exception as e:
            raise ProviderExecutionError(
                f"React Bits registry error for '{component_id}': {e}",
                self.metadata.provider_id)
        if not isinstance(data, dict) or not data.get("files"):
            raise ProviderExecutionError(
                f"React Bits registry item '{component_id}' returned no files",
                self.metadata.provider_id)
        files = [
            {"path": f.get("path", "") or f.get("target", ""), "content": f.get("content", "") or ""}
            for f in data.get("files", [])
            if isinstance(f, dict)
        ]
        js_files = [f for f in files if f["path"].endswith((".jsx", ".tsx", ".js"))]
        css_files = [f for f in files if f["path"].endswith(".css")]
        code = "\n".join(f["content"] for f in js_files)
        dependencies = [
            {"name": dep, "version": "latest"}
            for dep in (data.get("dependencies") or [])
            if dep
        ]
        return {
            "source": "React Bits",
            "component_id": component_id,
            "name": data.get("name", component_id),
            "type": data.get("type", "registry:component"),
            "files": files,
            "code": code,
            "css_files": css_files,
            "dependencies": dependencies,
            "registry_dependencies": [
                {"name": dep, "version": "latest"}
                for dep in (data.get("registryDependencies") or []) if dep
            ],
            "tokens": {"colors": [], "typography": []},
        }
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
                data = self.fetch_registry_item(comp_id)
                return ProviderExecutionResult(True, data, {}, (time.time()-start)*1000)
            except ProviderExecutionError:
                raise
            except Exception as e:
                raise ProviderExecutionError(f"React Bits API Error: {str(e)}", self.metadata.provider_id)
        elif operation == "search_components":
            query = payload.get("query", "").lower()
            start = time.time()
            results = []
            for comp in REACT_BITS_CURATED:
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
        return self.fetch_registry_item(resource_id)

    def search(self, query: str, **kwargs) -> List[Any]:
        return []

