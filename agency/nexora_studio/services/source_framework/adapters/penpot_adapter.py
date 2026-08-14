# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from .base_adapter import BaseProviderAdapter
from ..domain_models import ComponentPackage, Provenance, DesignTokenPackage, ComponentPreview, ComponentMetadata
import datetime
import warnings

class PenpotAdapter(BaseProviderAdapter):
    """
    DEPRECATED (Phase 23.1).
    This legacy adapter bypasses the Universal Capability Execution Layer (UCEL).
    MIGRATION REFERENCE: Use the canonical 'nexora.provider.penpot' model when available.
    """
    def __init__(self, transport: Optional[Any] = None, config: Optional[Dict[str, Any]] = None):
        warnings.warn(
            "PenpotAdapter is deprecated and will be removed. "
            "Please migrate to the canonical UCEL provider once available.",
            DeprecationWarning, stacklevel=2
        )
        super().__init__(transport, config)
        if self.transport is None:
            from ..transport.mock_transport import MockTransport
            self.transport = MockTransport({
                "penpot_search": lambda args: {
                    "nodes": [{"id": f"search_res_{args.get('query', 'default')}", "name": f"Penpot Node search_res_{args.get('query', 'default')}"}]
                },
                "penpot_get_node": lambda args: {
                    "node": {"id": args.get("node_id", "default"), "name": f"Penpot Node {args.get('node_id', 'default')}"}
                }
            })
        
    @property
    def capabilities(self) -> List[str]:
        return ['SEARCH', 'PREVIEW', 'DEPENDENCY_DISCOVERY', 'DESIGN_TOKENS', 'VARIABLES']
        
    def _parse_tokens(self, node_data: Dict[str, Any]) -> DesignTokenPackage:
        tokens = node_data.get("tokens", {})
        if not isinstance(tokens, dict):
            tokens = {}
            
        return DesignTokenPackage(
            colors=tokens.get("colors", {}),
            typography=tokens.get("typography", {}),
            spacing=tokens.get("spacing", {}),
            radius=tokens.get("radius", {}),
            shadows=tokens.get("shadows", {}),
            effects=tokens.get("effects", {}),
            layout_grids=tokens.get("grids", {}),
            variables=tokens.get("variables", {})
        )

    def _create_package(self, node_id: str, node_data: Dict[str, Any]) -> ComponentPackage:
        name = node_data.get("name", f"Penpot Node {node_id}")
        
        return ComponentPackage(
            component_id=node_id,
            name=name,
            provenance=Provenance(
                provider="penpot",
                import_timestamp=str(datetime.datetime.now())
            ),
            design_tokens=self._parse_tokens(node_data),
            extended_preview=ComponentPreview(
                preview_url=f"https://penpot.app/preview/{node_id}"
            ),
            extended_metadata=ComponentMetadata(
                source_id=node_id,
                author=node_data.get("author", "Penpot"),
                version=node_data.get("version", "1.0.0")
            )
        )

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        try:
            res = self.transport.call_tool("penpot_search", {"query": query})
        except Exception as e:
            print(f"Penpot transport failed: {str(e)}")
            return []
            
        packages = []
        for node in res.get("nodes", []):
            if not isinstance(node, dict) or "id" not in node:
                continue
            packages.append(self._create_package(node["id"], node))
        return packages
        
    def get_component(self, component_id: str) -> ComponentPackage:
        res = self.transport.call_tool("penpot_get_node", {"node_id": component_id})
        node_data = res.get("node", {})
        if not node_data:
            raise ValueError(f"Penpot node {component_id} not found or malformed payload.")
        return self._create_package(component_id, node_data)
        
    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        return {"source": "penpot", "node_id": component_id}
        
    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return {"type": "image", "url": f"https://penpot.app/preview/{component_id}"}
        
    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        return []
        
    def get_license(self, component_id: str) -> str:
        return "MPL-2.0"
        
    def get_installation_guide(self, component_id: str) -> str:
        return "Export from Penpot via REST API / Plugin"
