# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from .base_adapter import BaseProviderAdapter
from ..domain_models import ComponentPackage, Provenance
import datetime

class InternalAdapter(BaseProviderAdapter):
        
    @property
    def capabilities(self) -> List[str]:
        return ['SEARCH', 'PREVIEW', 'DOWNLOAD', 'DEPENDENCY_DISCOVERY', 'INSTALLATION_GUIDE', 'LICENSE_INFORMATION']
        
    def _create_mock_package(self, component_id: str) -> ComponentPackage:
        return ComponentPackage(
            component_id=component_id,
            name=f"Internal Template {component_id}",
            provenance=Provenance(
                provider="internal",
                import_timestamp=str(datetime.datetime.now())
            )
        )
        
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        return [self._create_mock_package(f"internal_{query}")]
        
    def get_component(self, component_id: str) -> ComponentPackage:
        return self._create_mock_package(component_id)
        
    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        return {"source": "internal", "template_id": component_id}
        
    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return {"type": "component", "path": f"/templates/{component_id}/preview"}
        
    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        return []
        
    def get_license(self, component_id: str) -> str:
        return "Internal"
        
    def get_installation_guide(self, component_id: str) -> str:
        return "Use Builder Session to insert"
