import requests
import time
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
from typing import Dict, Any, List
from datetime import datetime
from odoo.addons.nexora_studio.services.providers.base_provider import (
    BaseProvider, ProviderMetadata, ProviderCapability, ProviderExecutionResult, 
    ProviderExecutionContext, ProviderHealth, ProviderCategory, ProviderExecutionError
)

class InternalTemplateProvider(BaseProvider):
    def __init__(self, metadata=None, sandbox=None, **kwargs):
        super().__init__(metadata or self.get_default_metadata(), sandbox)
        
    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(provider_id="component_internal", name="Internal Template Store", category=ProviderCategory.COMPONENT, provider_version="1.0.0", manifest_version="1.0", api_version="v1.0", vendor_url="")
    def check_health(self) -> ProviderHealth:
        return ProviderHealth(status="healthy", latency_ms=5.0, error_rate_24h=0.0, last_checked=datetime.utcnow())
    def discover_capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability("import_component", "import_component", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {})]
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        operation = request.payload.get('operation') or request.namespace.split('.')[-1]
        payload = request.payload
        context = request.context
        if operation == "import_component":
            comp_id = payload.get("component_id")
            if not comp_id: raise ProviderExecutionError("component_id required", self.metadata.provider_id)
            start = time.time()
            import odoo
            try:
                # We use the odoo framework env if available in thread, else simulate it
                db = odoo.sql_db.db_connect(odoo.tools.config.get('db_name', 'nexora_studio'))
                registry = odoo.registry(db.dbname)
                with registry.cursor() as cr:
                    env = odoo.api.Environment(cr, context.user_id, {})
                    # If model exists, fetch
                    if 'nexora.component' in env:
                        comp = env['nexora.component'].search([('name', '=', comp_id)], limit=1)
                        code = comp.code if comp else f"/* Component {comp_id} not found in DB */"
                    else:
                        code = f"/* Simulated DB fetch for internal component {comp_id} */"
                return ProviderExecutionResult(True, {"source": "Internal", "component_id": comp_id, "code": code, "dependencies": [], "tokens": {"colors": [], "typography": []}}, {}, (time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"Internal DB Error: {str(e)}", self.metadata.provider_id)
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
