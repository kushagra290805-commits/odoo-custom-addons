# -*- coding: utf-8 -*-
"""Phase 47.24 (ADR-0076): source-framework bridge for the React Bits registry.

Delegates retrieval to the existing provider-platform
ReactBitsComponentProvider (JS-CSS variant: self-contained JSX+CSS, zero
external dependencies). Same bridge contract as ShadcnRegistryAdapter.
"""
import logging
import re
from typing import Dict, Any, List, Optional

from ..domain_models import ComponentPackage, Provenance
from .base_adapter import BaseProviderAdapter

_logger = logging.getLogger(__name__)

REACT_BITS_CURATED = [
    "SpotlightCard", "GradientText", "StarBorder", "TiltedCard",
]

_SOURCE_CACHE: Dict[str, ComponentPackage] = {}


def _pascal(name: str) -> str:
    return ''.join(part.capitalize() for part in re.split(r'[^A-Za-z0-9]+', str(name)) if part)


class ReactBitsRegistryAdapter(BaseProviderAdapter):

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(transport=None, config=config or {})
        from odoo.addons.nexora_studio.services.providers.component.react_bits_adapter import (
            ReactBitsComponentProvider)
        self._provider = ReactBitsComponentProvider()

    @property
    def capabilities(self) -> List[str]:
        return ['COMPONENT_SOURCE', 'FETCH']

    def _fetch_package(self, component_id: str) -> ComponentPackage:
        if component_id in _SOURCE_CACHE:
            return _SOURCE_CACHE[component_id]
        item = self._provider.fetch_registry_item(component_id)
        code = item.get('code') or ''
        if not code:
            raise ValueError(f"react-bits registry item '{component_id}' carried no source")
        css_files = item.get('css_files') or []
        auxiliary = {}
        for f in css_files:
            fname = str(f.get('path') or '').rsplit('/', 1)[-1] or f"{component_id}.css"
            auxiliary[fname] = f.get('content') or ''
        package = ComponentPackage(
            component_id=f"react_bits/{component_id}",
            name=item.get('name') or component_id,
            description=item.get('type'),
            metadata={
                'source_code': code,
                'source_identifier': component_id,
                'source_provider': 'react_bits',
                'auxiliary_files': auxiliary,
                'requires_tailwind': False,
            },
            dependencies=list(item.get('dependencies') or []),
            license='MIT',
            provenance=Provenance(
                provider='react_bits_registry',
                repository='https://reactbits.dev',
                license='MIT',
                import_source=f'https://raw.githubusercontent.com/DavidHDev/react-bits/main/public/r/{component_id}-JS-CSS.json',
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
        for component_id in (requested or REACT_BITS_CURATED):
            try:
                packages.append(self._fetch_package(component_id))
            except Exception as e:
                _logger.warning(
                    "ReactBitsRegistryAdapter: failed to retrieve '%s': %s",
                    component_id, e)
        return packages

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        return self.discover_components()

    def get_component(self, component_id: str) -> ComponentPackage:
        return self._fetch_package(str(component_id).replace('react_bits/', ''))

    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        return {'source_provider': 'react_bits', 'component_id': component_id}

    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return {'type': 'none'}

    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        return list(self._fetch_package(str(component_id).replace('react_bits/', '')).dependencies)

    def get_license(self, component_id: str) -> str:
        return 'MIT'

    def get_installation_guide(self, component_id: str) -> str:
        return 'Registry component: materialize JSX + CSS sidecar as own modules.'
