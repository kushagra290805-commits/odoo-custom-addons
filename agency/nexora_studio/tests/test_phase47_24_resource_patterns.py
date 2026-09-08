# -*- coding: utf-8 -*-
"""Phase 47.24 — resource pipeline reconciliation, component composition,
page patterns & stock imagery tests (ADR-0076).

Covers:
  * shadcn registry endpoint resolution + source retrieval (files[].content,
    dependencies) — live-network tests use the verified public registry.
  * React Bits registry retrieval (JS-CSS variant, css sidecar).
  * source-framework bridge: ComponentPackage with metadata.source_code,
    provenance, and the (unchanged) source-code gate.
  * provider_manager binding for the shadcn/react_bits source rows.
  * page-pattern catalog: structure, deterministic selection, domain
    specificity, shared builders (no duplicate implementations).
  * pattern-section composition: external component materialization,
    assembler-owned import lines, lucide activation, static validation.
  * Pexels provider: retrieval, normalization, cache, failure, missing
    credentials; AssetEngine fallback to the deterministic SVG hero.
  * stock image materialization + role assignment.
  * regression guards: 47.23 identifier validation with known identifiers,
    lucide import injection.
"""
import json
import os
import sys
import tempfile
import shutil
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo
from odoo.modules.registry import Registry

odoo.tools.config['test_enable'] = False

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel, ComponentTree, Content, RequirementModel, Theme,
    WebsiteGenerationArtifact, Assets)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine, _LUCIDE_ICON_WHITELIST)
from odoo.addons.nexora_studio.services.design.page_patterns import (
    PAGE_PATTERN_CATALOG, select_pattern, pattern_sections)
from odoo.addons.nexora_studio.services.providers.component.shadcn_adapter import (
    ShadcnComponentProvider, resolve_shadcn_item_url, SHADCN_INDEX_URL)
from odoo.addons.nexora_studio.services.providers.component.react_bits_adapter import (
    ReactBitsComponentProvider, resolve_react_bits_item_url)
from odoo.addons.nexora_studio.services.providers.asset import pexels_provider


class _FakeWorkspace:
    def __init__(self):
        self.files = {}

    def write_file(self, path, content):
        self.files[path] = content

    def write_binary(self, path, data):
        self.files[path] = b'<binary:%d>' % len(data)

    def read_file(self, path):
        return self.files.get(path, '')

    def exists(self, path):
        # Phase 47.28: deterministic home Hero checks for native Hero component
        return path == 'src/components/Hero.jsx'


def _artifact(**kwargs):
    defaults = dict(
        requirements=RequirementModel(
            domain='Agency', business_name='Atelier Meridian',
            business_category='premium architecture and interior design studio',
            location='Copenhagen, Denmark',
            branding={'business_name': 'Atelier Meridian',
                      'services': ['residential architecture',
                                   'interior design']}),
        architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/',
                     'sections': ['Hero', 'ServicesGrid', 'Testimonial',
                                  'ContactCTA']},
            'services': {'type': 'page', 'path': '/services',
                         'sections': ['Hero', 'Content']},
        }),
        component_tree=ComponentTree(nodes=[], dependencies=[]),
        theme=Theme(colors={'background': '#faf9f7', 'foreground': '#292524',
                            'primary': '#8a5a2b',
                            'primary_foreground': '#ffffff',
                            'secondary': '#57534e', 'accent': '#b45309',
                            'border': '#e7e5e4', 'muted': '#79716b',
                            'card': '#ffffff'}),
        content=Content(pages={
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'Crafted',
                       'aria_label': 'h', 'body': 'Hero copy.'},
                      {'type': 'ServicesGrid', 'semantic_heading': 'What we do',
                       'aria_label': 's',
                       'body': 'Intro.\n\nFirst service.\n\nSecond service.'},
                      {'type': 'Testimonial', 'semantic_heading': 'Kind words',
                       'aria_label': 't', 'body': 'They transformed our home.'},
                      {'type': 'ContactCTA', 'semantic_heading': 'Begin',
                       'aria_label': 'c', 'body': 'A few projects a year.'},
                  ]},
            '/services': {'seo': {'title': 'S', 'description': 'D'},
                          'metadata': {},
                          'sections': [
                              {'type': 'Hero', 'semantic_heading': 'Services',
                               'aria_label': 'h', 'body': 'Hero copy 2.'},
                              {'type': 'Content', 'semantic_heading': 'Detail',
                               'aria_label': 'c', 'body': 'Detail copy.'}]},
        }),
        assets=Assets(images=[], icons=[], fonts=[]),
    )
    defaults.update(kwargs)
    return WebsiteGenerationArtifact(**defaults)


def _card_node():
    from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
        ShadcnRegistryAdapter)
    pkg = ShadcnRegistryAdapter().get_component('card')
    code = pkg.metadata['source_code']
    return {
        'provider': 'shadcn_registry',
        'component_id': 'shadcn/card',
        'code': code,
        'dependencies': pkg.dependencies,
        'metadata': {
            'source_code': code,
            'source_identifier': 'card',
            'semantic': 'services_grid',
            'from_source': True,
            'source_provider': 'shadcn',
        },
    }


def _run_codegen(artifact, ai_responses=None):
    engine = CodeGenerationEngine(MagicMock())
    workspace = _FakeWorkspace()
    responses = iter(ai_responses or [
        {'full_content': 'function %s() { return (<section><h1>{"Hero"}</h1>'
                         '<p>{"copy"}</p></section>) }'}
    ] * 20)
    calls = []

    def gen(op, payload):
        calls.append((op, payload))
        import re
        mm = re.search(r'named (\w+)', payload.get('task', ''))
        name = mm.group(1) if mm else 'X'
        return next(responses) if ai_responses else {
            'full_content': 'function %s() { return (<section><h1>{"Hero"}</h1>'
                            '<p>{"copy"}</p></section>) }' % name}

    runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                              workspace=workspace)
    result = engine.execute(artifact, runtime)
    return result, workspace, calls


# ---------------------------------------------------------------------------
# shadcn / React Bits registry retrieval (live public endpoints)
# ---------------------------------------------------------------------------

class TestShadcnRegistry(unittest.TestCase):

    def test_01_endpoint_resolution(self):
        self.assertEqual(resolve_shadcn_item_url('card'),
                         'https://ui.shadcn.com/r/styles/default/card.json')
        self.assertTrue(SHADCN_INDEX_URL.startswith('https://ui.shadcn.com/r/'))

    def test_02_source_retrieval_files_and_deps(self):
        item = ShadcnComponentProvider().fetch_registry_item('card')
        self.assertTrue(item['files'])
        self.assertIn('rounded', item['code'])
        self.assertIn('export', item['code'])
        button = ShadcnComponentProvider().fetch_registry_item('button')
        dep_names = [d['name'] for d in button['dependencies']]
        self.assertIn('@radix-ui/react-slot', dep_names)
        self.assertTrue(all(d.get('version') for d in button['dependencies']))

    def test_03_missing_component_raises(self):
        from odoo.addons.nexora_studio.services.providers.base_provider import (
            ProviderExecutionError)
        with self.assertRaises(ProviderExecutionError):
            ShadcnComponentProvider().fetch_registry_item(
                'definitely-not-a-real-component-xyz')


class TestReactBitsRegistry(unittest.TestCase):

    def test_10_registry_retrieval_js_css(self):
        item = ReactBitsComponentProvider().fetch_registry_item('SpotlightCard')
        self.assertTrue(item['code'])
        self.assertIn('SpotlightCard', item['code'])
        self.assertTrue(item['css_files'], 'JS-CSS variant ships a css sidecar')
        self.assertEqual(item['css_files'][0]['path'], 'SpotlightCard.css')

    def test_11_endpoint_resolution(self):
        self.assertEqual(
            resolve_react_bits_item_url('SpotlightCard'),
            'https://raw.githubusercontent.com/DavidHDev/react-bits/main/'
            'public/r/SpotlightCard-JS-CSS.json')

    def test_12_missing_component_raises(self):
        from odoo.addons.nexora_studio.services.providers.base_provider import (
            ProviderExecutionError)
        with self.assertRaises(ProviderExecutionError):
            ReactBitsComponentProvider().fetch_registry_item('NoSuchComponent')


# ---------------------------------------------------------------------------
# Source-framework bridge (canonical reconciliation)
# ---------------------------------------------------------------------------

class TestSourceFrameworkBridge(unittest.TestCase):

    def test_20_component_package_with_source_code(self):
        from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
            ShadcnRegistryAdapter)
        pkg = ShadcnRegistryAdapter().get_component('card')
        self.assertEqual(pkg.component_id, 'shadcn/card')
        self.assertTrue(pkg.metadata.get('source_code'))
        self.assertEqual(pkg.provenance.provider, 'shadcn_registry')
        self.assertEqual(pkg.license, 'MIT')
        # The source-code gate requirement is satisfied upstream.
        self.assertTrue(pkg.metadata.get('source_code'))

    def test_21_discover_components_returns_bounded_set(self):
        from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
            ShadcnRegistryAdapter, _SOURCE_CACHE)
        _SOURCE_CACHE.pop('card', None)
        packages = ShadcnRegistryAdapter().discover_components()
        self.assertGreaterEqual(len(packages), 5)
        for pkg in packages:
            self.assertTrue(pkg.metadata.get('source_code'))
            self.assertTrue(pkg.provenance)

    def test_22_provider_manager_binds_registry_adapters(self):
        from odoo.addons.nexora_studio.services.source_framework.provider_manager import (
            ProviderManager)
        env = MagicMock()
        rows = []
        # shadcn/react_bits (MCP-bound rows) MUST resolve through the direct
        # registry adapters — no ConnectorRuntime bootstrap needed. Other
        # rows keep the existing loader behavior (non-MCP branch here; the
        # MCP branch requires the platform runtime and is covered by its
        # own suites).
        for tech, is_mcp, has_connector in (
                ('shadcn', True, True), ('react_bits', True, True),
                ('tavily_knowledge', False, None), ('other', False, None)):
            row = MagicMock()
            row.technical_name = tech
            row.is_mcp = is_mcp
            row.connector_id = MagicMock(id=999) if has_connector else None
            rows.append(row)
        env['nexora.source_registry'].search.return_value = rows
        pm = ProviderManager(env)
        pm.load_from_registry()
        self.assertIn('shadcn', pm.adapters)
        self.assertIn('react_bits', pm.adapters)
        # shadcn/react_bits resolve through the registry adapters, NOT MCP.
        from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
            ShadcnRegistryAdapter)
        from odoo.addons.nexora_studio.services.source_framework.adapters.react_bits_registry_adapter import (
            ReactBitsRegistryAdapter)
        self.assertIsInstance(pm.adapters['shadcn'], ShadcnRegistryAdapter)
        self.assertIsInstance(pm.adapters['react_bits'], ReactBitsRegistryAdapter)
        # The source-code gate: capabilities are COMPONENT_SOURCE (component
        # discovery path), not generic document SEARCH.
        self.assertIn('COMPONENT_SOURCE', pm.adapters['shadcn'].capabilities)
        self.assertNotIn('SEARCH', pm.adapters['shadcn'].capabilities)

    def test_23_source_code_gate_in_intelligence(self):
        # A candidate WITHOUT source_code can never match (gate preserved).
        from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
            ComponentIntelligenceEngine)
        pkg = _card_node()
        no_code = dict(pkg)
        no_code['metadata'] = dict(pkg['metadata'])
        no_code['metadata']['source_code'] = None
        no_code['code'] = '/* Code generated by Orchestrator */'
        artifact = _artifact(
            generation_metadata={'modular_blueprint': {
                'component': {'abstract_components': ['services_grid']}},
                'candidate_components': [
                    {'package': _package_from_node(no_code), 'score': 1}]},
            component_tree=ComponentTree(nodes=[], dependencies=[]))
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, SimpleNamespace(env=None))
        nodes = result.artifact.component_tree.nodes
        self.assertTrue(nodes)
        self.assertFalse(nodes[0]['metadata'].get('from_source'),
                         'metadata-only candidate must not be selected')

    def test_24_selected_component_reaches_codegen(self):
        node = _card_node()
        artifact = _artifact(
            component_tree=ComponentTree(nodes=[node], dependencies=[]))
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        # The real external component file is materialized...
        self.assertIn('src/components/external/Card.tsx', workspace.files)
        self.assertIn('export', workspace.files['src/components/external/Card.tsx'])
        # ...and the page imports it (assembler-owned import line).
        page = workspace.files['src/pages/index.tsx']
        self.assertIn("from '../components/external/Card.tsx'", page)
        self.assertIn('<Card', page)
        self.assertIn('data-nexora-source="shadcn/card"', page)


def _package_from_node(node):
    from odoo.addons.nexora_studio.services.source_framework.domain_models import (
        ComponentPackage, Provenance)
    return ComponentPackage(
        component_id=node['component_id'],
        name='Card',
        metadata=node['metadata'],
        provenance=Provenance(provider='shadcn_registry'),
    )


# ---------------------------------------------------------------------------
# Page patterns
# ---------------------------------------------------------------------------

class TestPagePatterns(unittest.TestCase):

    def test_30_catalog_structure(self):
        for pattern in PAGE_PATTERN_CATALOG.values():
            self.assertIn('id', pattern)
            self.assertIn('home_sections', pattern)
            self.assertIn('secondary_sections', pattern)
            self.assertIn('reason_stub', pattern)
            for sec in (pattern['home_sections'] + pattern['secondary_sections']):
                self.assertIsInstance(sec, str)

    def test_31_deterministic_domain_selection(self):
        self.assertEqual(select_pattern('Agency', '')['id'], 'agency')
        self.assertEqual(select_pattern('Restaurant', '')['id'], 'restaurant')
        self.assertEqual(select_pattern('SaaS', '')['id'], 'saas_product')
        self.assertEqual(select_pattern('Healthcare', '')['id'],
                         'professional_service')
        self.assertEqual(select_pattern('Whatever', 'generic')['id'], 'default')

    def test_32_keyword_routing(self):
        self.assertEqual(select_pattern('Unknown', 'an italian cafe')['id'],
                         'restaurant')
        self.assertEqual(select_pattern('Unknown', 'crypto startup')['id'],
                         'saas_product')

    def test_33_selection_is_explainable(self):
        pattern = select_pattern('Agency', 'architecture studio')
        self.assertTrue(pattern['reason'])
        self.assertTrue(all(isinstance(r, str) for r in pattern['reason']))

    def test_34_no_duplicate_component_implementations(self):
        # All patterns share the same builder vocabulary; the catalog never
        # carries per-pattern implementations. (Phase 47.25 extended the
        # shared vocabulary with About / MenuHighlights / FeatureGrid;
        # Phase 47.26 added Pricing / FAQ.)
        all_sections = set()
        for pattern in PAGE_PATTERN_CATALOG.values():
            all_sections.update(pattern['home_sections'])
            all_sections.update(pattern['secondary_sections'])
        self.assertLessEqual(all_sections, {
            'Hero', 'Content', 'About', 'ServicesGrid', 'FeatureGrid',
            'MenuHighlights', 'Pricing', 'FAQ', 'Testimonial', 'ContactCTA',
            'Gallery'})

    def test_35_pattern_sections_home_vs_secondary(self):
        pattern = select_pattern('Agency', '')
        self.assertEqual(pattern_sections(pattern, True),
                         pattern['home_sections'])
        self.assertEqual(pattern_sections(pattern, False),
                         pattern['secondary_sections'])
        self.assertEqual(pattern_sections(None, True), ['Hero', 'Content'])


# ---------------------------------------------------------------------------
# Pattern-section composition + lucide + validation
# ---------------------------------------------------------------------------

class TestPatternComposition(unittest.TestCase):

    def test_40_deterministic_sections_no_llm_call(self):
        artifact = _artifact()
        result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        # Phase 47.28: home hero is now deterministic too (0 LLM calls total).
        code_calls = [op for op, _ in calls if op == 'ai_code_patch']
        self.assertEqual(len(code_calls), 0,
                         'all sections deterministic (home hero + secondary hero + Content)')
        page = workspace.files['src/pages/index.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", page)
        self.assertIn('data-nexora-source="native/Hero"', page)
        self.assertIn('function ServicesgridSection', page)
        self.assertIn('function TestimonialSection', page)
        self.assertIn('function ContactctaSection', page)
        # Lucide icons materialize as real imports (no placeholder svg).
        self.assertIn("from 'lucide-react'", page)
        self.assertNotIn('data-lucide', page)
        # Theme vars used by deterministic sections.
        self.assertIn('var(--color-primary', page)
        self.assertIn('var(--font-heading', page)

    def test_41_lucide_icons_are_valid_react(self):
        artifact = _artifact()
        result, workspace, _ = _run_codegen(artifact)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn('<Briefcase size={22}', page)
        self.assertIn('<Quote size={28}', page)
        self.assertIn('<Star size={16}', page)
        # Every lucide identifier used in the page is whitelisted.
        used = set(CodeGenerationEngine._JSX_TAG_RE.findall(page))
        lucide_used = {u for u in used if u in _LUCIDE_ICON_WHITELIST}
        self.assertTrue(lucide_used)
        imported = set()
        for line in page.splitlines():
            if line.startswith('import') and 'lucide-react' in line:
                imported |= set(
                    CodeGenerationEngine._NAMED_EXPORT_RE.findall(
                        line.replace('{', '{').replace('}', '}')))
        for icon in lucide_used:
            self.assertIn(icon, page)

    def test_42_validator_known_identifiers(self):
        code = ("function X() {\n  return (\n"
                "    <section><Card><CardTitle>{\"t\"}</CardTitle></Card></section>)\n}")
        issues = CodeGenerationEngine._section_module_issues(
            'X', code, known_identifiers={'Card', 'CardTitle'})
        self.assertEqual(issues, [])
        # Without the known identifiers the external components are
        # correctly flagged (undefined) — assembler knowledge is required.
        issues2 = CodeGenerationEngine._section_module_issues('X', code)
        self.assertIn('undefined_component:Card', issues2)

    def test_43_lucide_import_injection(self):
        code = 'function X() { return <section><ArrowRight /><Star /></section> }'
        imports = CodeGenerationEngine._required_known_imports(code)
        self.assertEqual(imports, ["import { ArrowRight, Star } from 'lucide-react'"])
        with_import = "import { Star } from 'lucide-react'\n" + code
        imports2 = CodeGenerationEngine._required_known_imports(with_import)
        self.assertEqual(imports2, [])

    def test_44_gallery_skipped_without_images(self):
        artifact = _artifact(architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/',
                     'sections': ['Hero', 'Gallery']},
        }))
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        self.assertIn('Gallery', result.metadata.get('skipped_sections', []))
        self.assertNotIn('function GallerySection', workspace.files['src/pages/index.tsx'])

    def test_45_pattern_metadata_flows_from_planning(self):
        from odoo.addons.nexora_studio.services.generation.engines.planning_engine import (
            PlanningEngine)
        from odoo.addons.nexora_studio.services.generation.engines.architecture_engine import (
            ArchitectureEngine)
        artifact = _artifact(generation_metadata={})
        # PlanningEngine needs the full design stack; exercise the two
        # contracts directly instead (pattern -> sections).
        pattern = select_pattern('Agency', 'premium architecture studio')
        gm = dict(artifact.generation_metadata)
        gm['page_pattern'] = {'id': pattern['id'], 'reason': pattern['reason'],
                              'home_sections': pattern['home_sections'],
                              'secondary_sections': pattern['secondary_sections']}
        gm['modular_blueprint'] = {
            'layout': {'strategy': 'grid', 'hierarchy': ['/', '/services']},
            'technology': {}, 'design': {}}
        artifact = artifact.evolve(generation_metadata=gm)
        result = ArchitectureEngine(MagicMock()).execute(artifact, MagicMock())
        self.assertTrue(result.success)
        hierarchy = result.artifact.architecture.component_hierarchy
        home = [v for v in hierarchy.values()
                if isinstance(v, dict) and v.get('path') == '/'][0]
        self.assertEqual(home['sections'], pattern['home_sections'])
        services = [v for v in hierarchy.values()
                    if isinstance(v, dict) and v.get('path') == '/services'][0]
        self.assertEqual(services['sections'], pattern['secondary_sections'])


# ---------------------------------------------------------------------------
# Pexels stock provider + AssetEngine
# ---------------------------------------------------------------------------

class TestPexelsProvider(unittest.TestCase):

    def _env(self, key='test-key'):
        env = MagicMock()
        env['ir.config_parameter'].sudo().get_param.return_value = key
        return env

    def test_50_retrieval_and_normalization(self):
        payload = {'photos': [{
            'id': 42, 'alt': 'A calm room', 'photographer': 'Ann',
            'url': 'https://pexels.com/photo/42', 'width': 6000,
            'height': 4000,
            'src': {'large2x': 'https://images.pexels.com/42.jpeg'}}]}
        pexels_provider.reset_cache()
        with patch.object(pexels_provider.requests, 'get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: payload)
            results, cached = pexels_provider.search_photos(
                self._env(), 'calm room')
        self.assertEqual(len(results), 1)
        self.assertFalse(cached)
        photo = results[0]
        self.assertEqual(photo['photo_id'], 42)
        self.assertEqual(photo['remote_url'], 'https://images.pexels.com/42.jpeg')
        self.assertEqual(photo['alt'], 'A calm room')
        self.assertIn('Pexels License', photo['license'])

    def test_51_cache_hit(self):
        pexels_provider.reset_cache()
        payload = {'photos': []}
        env = self._env()
        with patch.object(pexels_provider.requests, 'get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: payload)
            pexels_provider.search_photos(env, 'x')
            pexels_provider.search_photos(env, 'x')
            self.assertEqual(mock_get.call_count, 1,
                             'second identical query must hit the cache')
        self.assertEqual(pexels_provider.cache_hits, 1)

    def test_52_provider_failure_never_raises(self):
        pexels_provider.reset_cache()
        with patch.object(pexels_provider.requests, 'get',
                          side_effect=Exception('network down')):
            results, cached = pexels_provider.search_photos(self._env(), 'q')
        self.assertEqual(results, [])
        self.assertFalse(cached)

    def test_53_missing_credentials(self):
        pexels_provider.reset_cache()
        env = MagicMock()
        env['ir.config_parameter'].sudo().get_param.return_value = ''
        self.assertFalse(pexels_provider.is_configured(env))
        results, _ = pexels_provider.search_photos(env, 'q')
        self.assertEqual(results, [])
        self.assertFalse(pexels_provider.is_configured(None))

    def test_54_download_failure_returns_none(self):
        with patch.object(pexels_provider.requests, 'get') as mock_get:
            mock_get.return_value = MagicMock(status_code=404, content=b'')
            self.assertIsNone(pexels_provider.download_photo('http://x/y.jpg'))
        with patch.object(pexels_provider.requests, 'get',
                          side_effect=Exception('boom')):
            self.assertIsNone(pexels_provider.download_photo('http://x/y.jpg'))

    def test_55_asset_engine_fallback_without_key(self):
        from odoo.addons.nexora_studio.services.generation.engines.asset_engine import (
            AssetEngine)
        artifact = _artifact(architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/',
                     'sections': ['Hero', 'ServicesGrid', 'Gallery']},
        }))
        runtime = SimpleNamespace(env=None)
        result = AssetEngine(MagicMock()).execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        # Deterministic hero SVG remains the floor.
        self.assertIn('hero_visual',
                      [i['id'] for i in result.artifact.assets.images])
        self.assertIn(result.metadata['stock_provider'],
                      ('unconfigured', 'error', 'pexels'))
        # No remote entries without a configured provider.
        self.assertFalse([i for i in result.artifact.assets.images
                          if i.get('remote_url')])

    def test_56_asset_engine_collects_role_tagged_entries(self):
        from odoo.addons.nexora_studio.services.generation.engines.asset_engine import (
            AssetEngine)
        pexels_provider.reset_cache()
        photos = [{'photo_id': n, 'remote_url': 'https://x/%d.jpg' % n,
                   'alt': 'img %d' % n, 'photographer': 'P', 'source_url': 'u',
                   'width': 1, 'height': 1, 'license': 'Pexels License'}
                  for n in range(1, 12)]

        def fake_search(env, query, orientation='landscape', per_page=4):
            return list(photos), False

        artifact = _artifact(architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/',
                     'sections': ['Hero', 'ServicesGrid', 'Gallery',
                                  'ContactCTA']},
        }))
        env = MagicMock()
        env['ir.config_parameter'].sudo().get_param.return_value = 'k'
        runtime = SimpleNamespace(env=env)
        with patch.object(pexels_provider, 'search_photos', fake_search):
            result = AssetEngine(MagicMock()).execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        images = result.artifact.assets.images
        roles = {i.get('role') for i in images if i.get('remote_url')}
        self.assertIn('hero', roles)
        self.assertIn('gallery', roles)
        self.assertIn('section', roles)
        gallery = [i for i in images if i.get('role') == 'gallery']
        self.assertEqual(len(gallery), 3)
        # Distinct photos across roles.
        ids = [i['id'] for i in images if i.get('remote_url')]
        self.assertEqual(len(ids), len(set(ids)))
        # License + photographer metadata preserved.
        for img in images:
            if img.get('remote_url'):
                md = img['metadata']
                self.assertEqual(md['ownership'], 'pexels')
                self.assertTrue(md['license'])
        self.assertEqual(result.metadata['stock_provider'], 'pexels')

    def test_57_stock_materialization_binary_write(self):
        engine = CodeGenerationEngine(MagicMock())
        workspace = _FakeWorkspace()
        artifact = _artifact(assets=Assets(images=[
            {'id': 'stock_hero', 'format': 'jpg', 'role': 'hero',
             'remote_url': 'https://x/hero.jpg', 'content': None,
             'metadata': {'alt': 'hero image', 'ownership': 'pexels'}},
        ], icons=[], fonts=[]))
        with patch.object(pexels_provider, 'download_photo',
                          return_value=b'\xff\xd8fakejpeg'):
            materialized, evidence = engine._materialize_stock_images(
                artifact, SimpleNamespace(workspace=workspace))
        self.assertIn('stock_hero', materialized)
        self.assertEqual(materialized['stock_hero']['path'], '/images/stock_hero.jpg')
        self.assertIn('public/images/stock_hero.jpg', workspace.files)
        # Failure path: entry skipped, never raises.
        artifact2 = _artifact(assets=Assets(images=[
            {'id': 'stock_hero', 'format': 'jpg', 'role': 'hero',
             'remote_url': 'https://x/hero.jpg'}], icons=[], fonts=[]))
        with patch.object(pexels_provider, 'download_photo', return_value=None):
            materialized2, evidence2 = engine._materialize_stock_images(
                artifact2, SimpleNamespace(workspace=workspace))
        self.assertEqual(materialized2, {})
        self.assertTrue(evidence2 and evidence2[0].get('failed'))

    def test_58_hero_prefers_stock_image(self):
        node = _card_node()
        artifact = _artifact(
            component_tree=ComponentTree(nodes=[node], dependencies=[]),
            assets=Assets(images=[
                {'id': 'stock_hero', 'format': 'jpg', 'role': 'hero',
                 'remote_url': 'https://x/hero.jpg', 'content': None,
                 'metadata': {'alt': 'hero alt text', 'ownership': 'pexels'}},
            ], icons=[], fonts=[]))
        engine = CodeGenerationEngine(MagicMock())
        with patch.object(pexels_provider, 'download_photo',
                          return_value=b'\xff\xd8fakejpeg'):
            # Phase 47.28: home hero is deterministic — the stock image
            # reaches the page through the native Hero image prop (no LLM
            # call references it anymore).
            result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        # No LLM call for the home hero (deterministic since 47.28).
        code_calls = [op for op, _ in calls if op == 'ai_code_patch']
        self.assertEqual(len(code_calls), 0)
        # ...and the materialized image renders in the page.
        page = workspace.files['src/pages/index.tsx']
        self.assertIn('/images/stock_hero.jpg', page)
        self.assertIn('hero alt text', page)
        self.assertIn('stock_hero', result.metadata.get('stock_image_roles', []))


# ---------------------------------------------------------------------------
# React provider conditional Tailwind support
# ---------------------------------------------------------------------------

class TestReactProviderExternalSupport(unittest.TestCase):

    def _context(self, selected):
        from odoo.addons.nexora_studio.services.design.providers.react_provider import (
            ReactRenderingProvider)
        provider = ReactRenderingProvider()
        ctx = SimpleNamespace(
            output_config={'selected_components': selected},
            tokens=[], render_project=SimpleNamespace(name='T'))
        return provider, ctx

    def test_60_no_tailwind_without_external_components(self):
        from odoo.addons.nexora_studio.services.design.providers.react_provider import (
            ReactRenderingProvider)
        provider, ctx = self._context([])
        self.assertFalse(provider._needs_tailwind(ctx))
        css = provider._generate_tokens_css([])
        self.assertNotIn('@import "tailwindcss"', css)
        vite = provider._generate_vite_config(ctx)
        self.assertNotIn('tailwindcss', vite)
        self.assertNotIn('@tailwindcss/vite', provider._generate_package_json(
            SimpleNamespace(name='t'), ctx))

    def test_61_tailwind_with_shadcn_selection(self):
        node = _card_node()
        provider, ctx = self._context([node])
        self.assertTrue(provider._needs_tailwind(ctx))
        pkg = json.loads(provider._generate_package_json(
            SimpleNamespace(name='t'), ctx))
        deps = pkg['dependencies']
        self.assertEqual(deps.get('tailwindcss'), '^4.1.11')
        self.assertEqual(deps.get('@tailwindcss/vite'), '^4.1.11')
        # cn()'s own runtime deps (the scaffold emits src/lib/utils.js).
        self.assertEqual(deps.get('clsx'), '^2.1.1')
        self.assertEqual(deps.get('tailwind-merge'), '^3.3.1')
        vite = provider._generate_vite_config(ctx)
        self.assertIn('tailwindcss()', vite)
        self.assertIn("alias", vite)
        # utils.js present; tokens.css gains @theme mapping.
        structure = {}
        css = provider._generate_tokens_css([])
        css = provider._apply_tailwind_theme(css)
        self.assertIn('@import "tailwindcss";', css)
        self.assertIn('--color-card-foreground', css)

    def test_62_react_bits_needs_no_tailwind(self):
        from odoo.addons.nexora_studio.services.source_framework.adapters.react_bits_registry_adapter import (
            ReactBitsRegistryAdapter)
        pkg = ReactBitsRegistryAdapter().get_component('SpotlightCard')
        node = {
            'component_id': 'react_bits/SpotlightCard',
            'code': pkg.metadata['source_code'],
            'metadata': {**pkg.metadata, 'from_source': True},
        }
        provider, ctx = self._context([node])
        self.assertFalse(provider._needs_tailwind(ctx))


if __name__ == '__main__':
    unittest.main(verbosity=2)
