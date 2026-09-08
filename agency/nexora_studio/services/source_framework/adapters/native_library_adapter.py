# -*- coding: utf-8 -*-
"""Phase 47.25 (ADR-0077): native library source-framework adapter.

Exposes the EXISTING ReactComponentLibrary (the 27-component native library
synthesized into every generated workspace by the rendering provider) as
ComponentPackages through the SAME BaseProviderAdapter contract as the
shadcn / react-bits registry adapters. One canonical discovery path; the
source-code gate applies to native candidates exactly as to external ones.

The synthesized code is manifest-independent (static templates), so the
adapter's source_code is byte-identical to the workspace file the provider
scaffold writes — `metadata.workspace_path` points CodeGenerationEngine at
the existing file instead of duplicating it.
"""
import logging
import re
from typing import Dict, Any, List, Optional

from ..domain_models import ComponentPackage, Provenance
from .base_adapter import BaseProviderAdapter

_logger = logging.getLogger(__name__)

# Process-level source cache: component name -> ComponentPackage.
_SOURCE_CACHE: Dict[str, ComponentPackage] = {}


def _library_files() -> Dict[str, str]:
    """Synthesize the native library once per process (module-level)."""
    global _LIBRARY_FILES
    if _LIBRARY_FILES is None:
        from odoo.addons.nexora_studio.services.design.react_component_library import (
            ReactComponentLibrary)
        _LIBRARY_FILES = ReactComponentLibrary().synthesize_all()
    return _LIBRARY_FILES


_LIBRARY_FILES: Optional[Dict[str, str]] = None


# Curated exposure — production-ready, marketing-site-composable components
# (classification A). Native Hero is deliberately NOT exposed: hero
# sections are the LLM-novel path and source-adaptation of a multi-file
# native organism into a page module would break its relative imports
# (deferred; documented in ADR-0077). App-oriented components (Modal,
# Sidebar, Table, AuthForm, Dropdown, Tabs, Pagination, Breadcrumb, Alert,
# Avatar, Badge, Blog*, Dashboard*, StatsCard, ContactForm, Navbar, Footer)
# remain shipped by the scaffold but are NOT exposed for section
# composition. Descriptions deliberately avoid the generic 'section' and
# 'content' tokens so nothing over-matches *_section semantics.
_NATIVE_EXPOSURE = {
    'Card': {
        'category': 'molecule',
        'description': 'Card component for feature, service and grid items '
                       'with title, subtitle, image and badge.',
        'section_types': ['services_grid', 'feature_grid', 'menu_highlights'],
        'domains': ['agency', 'restaurant', 'saas', 'professional_service'],
    },
    'FeatureGrid': {
        'category': 'organism',
        'description': 'Feature grid presenting services, features or menu '
                       'highlights as a responsive card grid.',
        'section_types': ['feature_grid', 'services_grid', 'menu_highlights'],
        'domains': ['agency', 'saas', 'restaurant', 'professional_service'],
        'organism': True,
        'props': {'title': 'str', 'subtitle': 'str',
                  'features': 'list[{title, subtitle, description}]'},
    },
    'Testimonial': {
        'category': 'molecule',
        'description': 'Testimonial quote card with author, role and '
                       'company attribution for review blocks.',
        'section_types': ['testimonial_section'],
        'domains': ['agency', 'restaurant', 'saas', 'professional_service'],
        'organism': True,
        'props': {'quote': 'str', 'author': 'str', 'role': 'str',
                  'company': 'str'},
    },
    'PricingCard': {
        'category': 'molecule',
        'description': 'Pricing plan card with price, features and CTA for '
                       'pricing layouts.',
        'section_types': ['pricing'],
        'domains': ['saas'],
        'organism': True,
        'props': {'title': 'str', 'price': 'str', 'period': 'str',
                  'features': 'list[str]', 'cta': '{label, href}'},
    },
    'ProductGrid': {
        'category': 'organism',
        'description': 'Product grid presenting catalog items, menu dishes '
                       'or featured products with prices.',
        'section_types': ['menu_highlights', 'feature_grid'],
        'domains': ['restaurant', 'ecommerce'],
        'organism': True,
        'props': {'title': 'str',
                  'products': 'list[{title, price, badge, image}]'},
    },
    'FAQ': {
        'category': 'organism',
        'description': 'FAQ accordion with questions and answers.',
        'section_types': ['faq'],
        'domains': ['agency', 'saas', 'restaurant'],
        'organism': True,
    },
    'Button': {
        'category': 'primitive',
        'description': 'Button and CTA trigger with variants, sizes and '
                       'href link support for contact CTA blocks.',
        'section_types': ['contact_cta'],
        'domains': ['agency', 'restaurant', 'saas', 'professional_service'],
    },
}


class NativeLibraryAdapter(BaseProviderAdapter):
    """Native library as a resource source — same contract, same gate."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(transport=None, config=config or {})

    @property
    def capabilities(self) -> List[str]:
        # COMPONENT_SOURCE (component discovery) + FETCH; deliberately NOT
        # generic SEARCH so the knowledge path never queries the library.
        return ['COMPONENT_SOURCE', 'FETCH']

    def _fetch_package(self, name: str) -> ComponentPackage:
        if name in _SOURCE_CACHE:
            return _SOURCE_CACHE[name]
        files = _library_files()
        path = 'src/components/%s.jsx' % name
        code = files.get(path)
        if not code:
            raise ValueError('native library has no component %r' % name)
        spec = _NATIVE_EXPOSURE[name]
        package = ComponentPackage(
            component_id='native/%s' % name,
            name=name,
            description=spec['description'],
            metadata={
                'source_code': code,
                'source_identifier': name,
                'source_provider': 'native_library',
                'workspace_path': path,
                'category': spec['category'],
                'purpose': spec['description'],
                'section_types': spec['section_types'],
                'domains': spec['domains'],
                'organism': bool(spec.get('organism')),
                'props': spec.get('props') or {},
                'requires_tailwind': False,
            },
            dependencies=[{'name': 'react', 'version': '^18.3.1'}],
            license='LGPL-3',
            provenance=Provenance(
                provider='native_library',
                repository='nexora_studio',
                license='LGPL-3',
                import_source=path,
            ),
        )
        _SOURCE_CACHE[name] = package
        return package

    def discover_components(self, params: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        requested = None
        if params:
            raw = params.get('components')
            if isinstance(raw, (list, tuple)) and raw:
                requested = [str(c) for c in raw if str(c) in _NATIVE_EXPOSURE]
        packages: List[ComponentPackage] = []
        for name in (requested or _NATIVE_EXPOSURE):
            try:
                packages.append(self._fetch_package(name))
            except Exception as e:
                _logger.warning("NativeLibraryAdapter: failed '%s': %s", name, e)
        return packages

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        # COMPONENT_SOURCE discovery is this adapter's contract (bounded,
        # source-backed); delegate to discovery for a consistent result.
        return self.discover_components()

    def get_component(self, component_id: str) -> ComponentPackage:
        return self._fetch_package(str(component_id).replace('native/', ''))

    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        name = str(component_id).replace('native/', '')
        spec = _NATIVE_EXPOSURE.get(name, {})
        return {'source_provider': 'native_library', 'component_id': component_id,
                'category': spec.get('category'), 'section_types': spec.get('section_types')}

    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return {'type': 'none'}

    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        return list(self._fetch_package(str(component_id).replace('native/', '')).dependencies)

    def get_license(self, component_id: str) -> str:
        return 'LGPL-3'

    def get_installation_guide(self, component_id: str) -> str:
        return 'Native component: already materialized by the provider scaffold.'
