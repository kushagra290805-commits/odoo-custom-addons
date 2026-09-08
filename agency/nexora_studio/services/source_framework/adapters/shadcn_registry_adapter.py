# -*- coding: utf-8 -*-
"""Phase 47.24 (ADR-0076): source-framework bridge for the shadcn registry.

The source-framework (ComponentDiscoveryEngine → SearchEngine → adapters)
is the canonical runtime component path. This adapter implements the
BaseProviderAdapter contract and DELEGATES retrieval to the existing
provider-platform ShadcnComponentProvider — one retrieval implementation,
two contracts bridged, no third path. Registered by ProviderManager for
the existing `shadcn` source row; requires no MCP connector lifecycle.
"""
import logging
import re
from typing import Dict, Any, List, Optional

from ..domain_models import ComponentPackage, Provenance
from .base_adapter import BaseProviderAdapter

_logger = logging.getLogger(__name__)

# Curated marketing-site-relevant registry entries. discover_components()
# receives no query from the SearchEngine COMPONENT_SOURCE contract, so the
# adapter serves this bounded set (each fetched once, then cached).
SHADCN_CURATED_COMPONENTS = [
    "card", "button", "badge", "tabs", "separator",
    "avatar", "accordion", "input", "textarea",
]

# Process-level source cache: component_id -> ComponentPackage. Repeated
# generation never re-downloads the same component source (ADR-0076 §cost).
_SOURCE_CACHE: Dict[str, ComponentPackage] = {}


def _pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in re.split(r'[^A-Za-z0-9]+', str(name)) if part)


class ShadcnRegistryAdapter(BaseProviderAdapter):
    """Delegates to ShadcnComponentProvider; emits ComponentPackage with
    metadata.source_code (satisfying the — unchanged — source-code gate),
    dependencies (with versions) and full provenance."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(transport=None, config=config or {})
        from odoo.addons.nexora_studio.services.providers.component.shadcn_adapter import (
            ShadcnComponentProvider)
        self._provider = ShadcnComponentProvider()

    @property
    def capabilities(self) -> List[str]:
        # COMPONENT_SOURCE: SearchEngine's component-discovery contract.
        # FETCH: source retrieval. Deliberately NOT generic SEARCH so the
        # knowledge path never queries the component registry for documents.
        return ['COMPONENT_SOURCE', 'FETCH']

    def _fetch_package(self, component_id: str) -> ComponentPackage:
        if component_id in _SOURCE_CACHE:
            return _SOURCE_CACHE[component_id]
        item = self._provider.fetch_registry_item(component_id)
        code = item.get('code') or ''
        if not code:
            raise ValueError(f"shadcn registry item '{component_id}' carried no source")
        deps = list(item.get('dependencies') or []) + list(item.get('registry_dependencies') or [])
        package = ComponentPackage(
            component_id=f"shadcn/{component_id}",
            name=item.get('name') or _pascal(component_id),
            description=item.get('type'),
            metadata={
                'source_code': code,
                'source_identifier': component_id,
                'source_provider': 'shadcn',
                'files': item.get('files') or [],
                'requires_tailwind': True,
            },
            dependencies=deps,
            license='MIT',
            provenance=Provenance(
                provider='shadcn_registry',
                repository='https://ui.shadcn.com',
                license='MIT',
                import_source=f'https://ui.shadcn.com/r/styles/default/{component_id}.json',
            ),
        )
        _SOURCE_CACHE[component_id] = package
        return package

    def discover_components(self, params: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        packages: List[ComponentPackage] = []
        requested = None
        if params:
            raw = params.get('components')
            if isinstance(raw, (list, tuple)) and raw:
                requested = [str(c) for c in raw]
        for component_id in (requested or SHADCN_CURATED_COMPONENTS):
            try:
                packages.append(self._fetch_package(component_id))
            except Exception as e:
                _logger.warning(
                    "ShadcnRegistryAdapter: failed to retrieve '%s': %s",
                    component_id, e)
        return packages

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        # Semantic search through the SearchEngine generic path is not this
        # adapter's contract (COMPONENT_SOURCE discovery is); delegate to
        # discovery for a bounded, source-backed result set.
        return self.discover_components()

    def get_component(self, component_id: str) -> ComponentPackage:
        return self._fetch_package(str(component_id).replace('shadcn/', ''))

    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        return {'source_provider': 'shadcn', 'component_id': component_id}

    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return {'type': 'none'}

    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        return list(self._fetch_package(str(component_id).replace('shadcn/', '')).dependencies)

    def get_license(self, component_id: str) -> str:
        return 'MIT'

    def get_installation_guide(self, component_id: str) -> str:
        return 'Registry component: materialize as its own module; dependencies emitted to package.json.'
