# -*- coding: utf-8 -*-
"""Phase 47.25 — native component library activation tests (ADR-0077).

Covers:
  * Native library inventory + production-ready classification.
  * Native ComponentPackage: source_code, workspace_path, semantic metadata.
  * Unified selection: native + shadcn + react_bits candidates through ONE
    discovery path; source-code gate; explainable selection evidence;
    camelCase tokenizer.
  * Native materialization: import lines against the EXISTING scaffold
    files (no external/ duplicates); organism composition (FeatureGrid,
    Testimonial, Button CTA).
  * Pattern catalog quality: domain-appropriate sections (restaurant
    About/MenuHighlights, saas FeatureGrid); shared builder vocabulary.
  * Selection remains semantic (no hardcoded source preference) — a
    lighter/more-relevant candidate still wins on merit.
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel, ComponentTree, Content, RequirementModel, Theme,
    WebsiteGenerationArtifact, Assets)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine)
from odoo.addons.nexora_studio.services.design.page_patterns import (
    PAGE_PATTERN_CATALOG, select_pattern, pattern_sections)
from odoo.addons.nexora_studio.services.design.react_component_library import (
    ReactComponentLibrary)


# ---------------------------------------------------------------------------
# Native library inventory
# ---------------------------------------------------------------------------

class TestNativeInventory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = ReactComponentLibrary().synthesize_all()

    def test_01_inventory_complete(self):
        # 28 component modules + the barrel exporter.
        components = [f for f in self.files
                      if f.startswith('src/components/') and f.endswith('.jsx')]
        self.assertEqual(len(components), 28)
        self.assertIn('src/components/index.js', self.files)
        for expected in ('Card', 'FeatureGrid', 'Testimonial', 'PricingCard',
                         'ProductGrid', 'FAQ', 'Button', 'Hero'):
            self.assertIn('src/components/%s.jsx' % expected, self.files)

    def test_02_exports_and_styling(self):
        # Direct-token styling for the standalone components; composed
        # organisms inherit tokens through the primitives they compose.
        for name in ('Card', 'FeatureGrid', 'Button'):
            code = self.files['src/components/%s.jsx' % name]
            self.assertIn('export default', code, '%s default export' % name)
            self.assertIn('var(--', code, '%s uses design tokens' % name)
        testimonial = self.files['src/components/Testimonial.jsx']
        self.assertIn('export default', testimonial)
        self.assertIn("import Card from './Card.jsx'", testimonial,
                      'Testimonial composes the Card primitive')

    def test_03_card_border_token_fix(self):
        # Phase 47.25 (ADR-0077): the dark-only translucent borders are gone.
        code = self.files['src/components/Card.jsx']
        self.assertNotIn('rgba(255,255,255,0.1)', code)
        self.assertNotIn('rgba(255,255,255,0.2)', code)
        self.assertIn('var(--color-border', code)

    def test_04_native_adapter_packages(self):
        from odoo.addons.nexora_studio.services.source_framework.adapters.native_library_adapter import (
            NativeLibraryAdapter, _NATIVE_EXPOSURE)
        adapter = NativeLibraryAdapter()
        packages = adapter.discover_components()
        self.assertEqual(len(packages), len(_NATIVE_EXPOSURE))
        for pkg in packages:
            self.assertTrue(pkg.metadata.get('source_code'),
                            '%s carries source_code' % pkg.component_id)
            self.assertTrue(pkg.metadata.get('workspace_path'))
            self.assertTrue(pkg.description,
                            '%s carries a semantic description' % pkg.component_id)
            self.assertTrue(pkg.metadata.get('section_types'))
            self.assertEqual(pkg.metadata.get('source_provider'), 'native_library')
            self.assertEqual(pkg.provenance.provider, 'native_library')
        # Hero is deliberately NOT exposed (LLM-novel section; deferred).
        self.assertNotIn('Hero', _NATIVE_EXPOSURE)

    def test_05_source_code_matches_scaffold(self):
        # The adapter's code is byte-identical to the workspace file the
        # provider scaffold writes (manifest-independent generators).
        from odoo.addons.nexora_studio.services.source_framework.adapters.native_library_adapter import (
            NativeLibraryAdapter)
        adapter = NativeLibraryAdapter()
        for name in ('Card', 'FeatureGrid', 'Testimonial', 'Button'):
            pkg = adapter.get_component('native/%s' % name)
            self.assertEqual(pkg.metadata['source_code'],
                             self.files[pkg.metadata['workspace_path']])


# ---------------------------------------------------------------------------
# Unified selection (one canonical path)
# ---------------------------------------------------------------------------

class TestUnifiedSelection(unittest.TestCase):

    def _candidates(self):
        from odoo.addons.nexora_studio.services.source_framework.adapters.native_library_adapter import (
            NativeLibraryAdapter)
        from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
            ShadcnRegistryAdapter)
        from odoo.addons.nexora_studio.services.source_framework.adapters.react_bits_registry_adapter import (
            ReactBitsRegistryAdapter)
        candidates = []
        for adapter in (NativeLibraryAdapter(), ShadcnRegistryAdapter(),
                        ReactBitsRegistryAdapter()):
            for pkg in adapter.discover_components():
                candidates.append({'package': pkg, 'score': 1.0})
        return candidates

    def _match(self, semantics, candidates):
        from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
            ComponentIntelligenceEngine)
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Agency'),
            component_tree=ComponentTree(nodes=[], dependencies=[]),
            generation_metadata={
                'modular_blueprint': {'component': {
                    'abstract_components': semantics}},
                'candidate_components': candidates})
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, SimpleNamespace(env=None))
        out = {}
        for node in result.artifact.component_tree.nodes:
            md = node.get('metadata') or {}
            out[md.get('semantic')] = (node.get('component_id'),
                                       md.get('from_source'),
                                       md.get('selection') or {})
        return out

    def test_10_provider_manager_registers_native_builtin(self):
        from odoo.addons.nexora_studio.services.source_framework.provider_manager import (
            ProviderManager)
        from odoo.addons.nexora_studio.services.source_framework.adapters.native_library_adapter import (
            NativeLibraryAdapter)
        env = MagicMock()
        env['nexora.source_registry'].search.return_value = []
        pm = ProviderManager(env)
        pm.load_from_registry()
        self.assertIn('native_library', pm.adapters)
        self.assertIsInstance(pm.adapters['native_library'], NativeLibraryAdapter)
        # Built-in — no registry row, no connector lifecycle dependency.
        self.assertIn('COMPONENT_SOURCE', pm.adapters['native_library'].capabilities)
        self.assertNotIn('SEARCH', pm.adapters['native_library'].capabilities)

    def test_11_unified_matching_prefers_on_merit(self):
        candidates = self._candidates()
        matched = self._match(
            ['services_grid', 'feature_grid', 'menu_highlights',
             'testimonial_section', 'contact_cta', 'hero_section',
             'content_section', 'about_section', 'gallery'],
            candidates)
        # Semantically strong native organisms win on merit (overlap + zero
        # deps + local) — with recorded, explainable evidence.
        for semantic in ('services_grid', 'feature_grid', 'menu_highlights'):
            comp_id, from_source, evidence = matched[semantic]
            self.assertEqual(comp_id, 'native/FeatureGrid')
            self.assertTrue(from_source)
            self.assertGreaterEqual(evidence.get('overlap', 0), 2)
            self.assertEqual(evidence.get('dependency_weight'), 0)
            self.assertTrue(evidence.get('local'))
            self.assertEqual(evidence.get('source'), 'native_library')
        self.assertEqual(matched['testimonial_section'][0], 'native/Testimonial')
        self.assertEqual(matched['contact_cta'][0], 'native/Button')
        # Sections with no semantically-relevant candidate stay unmatched
        # (the source-code gate + semantic relevance are NOT weakened).
        for semantic in ('hero_section', 'content_section', 'about_section',
                         'gallery'):
            self.assertFalse(matched[semantic][1],
                             '%s must not match a weak candidate' % semantic)

    def test_12_camelcase_tokenizer(self):
        from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
            _tokens)
        self.assertEqual(_tokens('FeatureGrid'), {'feature', 'grid'})
        self.assertEqual(_tokens('SpotlightCard'), {'spotlight', 'card'})
        self.assertEqual(_tokens('services_grid'), {'services', 'grid'})
        self.assertEqual(_tokens('XMLHttpRequest'), {'xml', 'http', 'request'})

    def test_13_source_code_gate_for_native(self):
        # A native candidate WITHOUT source_code can never match.
        candidates = self._candidates()
        stripped = []
        for c in candidates:
            pkg = c['package']
            if pkg.metadata.get('source_provider') == 'native_library':
                # strip the code from a copy
                import copy
                pkg2 = copy.copy(pkg)
                pkg2.metadata = {k: v for k, v in pkg.metadata.items()
                                 if k != 'source_code'}
                stripped.append({'package': pkg2})
        matched = self._match(['services_grid'], stripped)
        self.assertFalse(matched['services_grid'][1])

    def test_14_semantic_not_hardcoded_shadcn_wins_when_relevant(self):
        # 'tabs' semantic: shadcn Tabs is the only candidate with tab
        # semantics — the selection is NOT hardcoded to native.
        from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
            ShadcnRegistryAdapter)
        candidates = [{'package': p, 'score': 1.0}
                      for p in ShadcnRegistryAdapter().discover_components()]
        candidates += self._candidates()
        matched = self._match(['tabs_section'], candidates)
        comp_id, from_source, _ = matched['tabs_section']
        self.assertEqual(comp_id, 'shadcn/tabs')
        self.assertTrue(from_source)


# ---------------------------------------------------------------------------
# Native materialization + pattern composition
# ---------------------------------------------------------------------------

def _node(name, semantic):
    from odoo.addons.nexora_studio.services.source_framework.adapters.native_library_adapter import (
        NativeLibraryAdapter)
    pkg = NativeLibraryAdapter().get_component('native/%s' % name)
    return {
        'provider': 'native_library',
        'component_id': pkg.component_id,
        'code': pkg.metadata['source_code'],
        'dependencies': pkg.dependencies,
        'metadata': {**pkg.metadata, 'semantic': semantic, 'from_source': True},
    }


class _ScaffoldWorkspace:
    """Simulates the provider scaffold (library files already present)."""

    def __init__(self):
        self.files = dict(ReactComponentLibrary().synthesize_all())

    def write_file(self, path, content):
        self.files[path] = content

    def write_binary(self, path, data):
        self.files[path] = data

    def read_file(self, path):
        return self.files.get(path, '')

    def exists(self, path):
        return path in self.files


def _artifact(nodes, sections=None):
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(
            domain='Agency', business_name='Atelier Meridian',
            location='Copenhagen, Denmark',
            branding={'business_name': 'Atelier Meridian',
                      'services': ['residential architecture',
                                   'interior design', 'spatial planning']}),
        architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/',
                     'sections': sections or ['Hero', 'ServicesGrid',
                                              'Testimonial', 'ContactCTA']},
            'services': {'type': 'page', 'path': '/services',
                         'sections': ['Hero', 'Content']},
        }),
        component_tree=ComponentTree(nodes=nodes, dependencies=['react']),
        theme=Theme(colors={'background': '#faf9f7', 'foreground': '#292524',
                            'primary': '#8a5a2b', 'primary_foreground': '#ffffff',
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
                       'body': 'Intro.\n\nFirst.\n\nSecond.\n\nThird.'},
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


def _run_codegen(artifact):
    engine = CodeGenerationEngine(MagicMock())
    workspace = _ScaffoldWorkspace()
    calls = []

    def gen(op, payload):
        calls.append(op)
        import re
        mm = re.search(r'named (\w+)', payload.get('task', ''))
        name = mm.group(1) if mm else 'X'
        return {'full_content': 'function %s() { return (<section><h1>{"Hero"}</h1>'
                                '<p>{"copy"}</p></section>) }' % name}

    runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                              workspace=workspace)
    result = engine.execute(artifact, runtime)
    return result, workspace, calls


class TestNativeMaterialization(unittest.TestCase):

    def test_20_native_reaches_codegen_no_duplicate_writes(self):
        nodes = [_node('FeatureGrid', 'services_grid'),
                 _node('Testimonial', 'testimonial_section'),
                 _node('Button', 'contact_cta')]
        result, workspace, calls = _run_codegen(_artifact(nodes))
        self.assertTrue(result.success, result.error)
        # Native evidence points at the EXISTING scaffold files.
        evidence = result.metadata.get('external_components') or []
        native = [e for e in evidence if e.get('kind') == 'native']
        self.assertEqual(len(native), 3)
        for e in native:
            self.assertTrue(e['path'].startswith('src/components/'))
        # No duplicates under external/.
        ext = [f for f in workspace.files
               if f.startswith('src/components/external/')]
        self.assertEqual(ext, [])
        # Pages import from the scaffold location.
        page = workspace.files['src/pages/index.tsx']
        self.assertIn("import FeatureGrid from '../components/FeatureGrid.jsx'", page)
        self.assertIn("import Testimonial from '../components/Testimonial.jsx'", page)
        self.assertIn("import Button from '../components/Button.jsx'", page)
        # The REAL organisms render with source attribution.
        self.assertIn('<FeatureGrid data-nexora-source="native/FeatureGrid"', page)
        self.assertIn('features={features}', page)
        self.assertIn('const features = [', page)
        self.assertIn('<Testimonial data-nexora-source="native/Testimonial"', page)
        self.assertIn('<Button data-nexora-source="native/Button"', page)
        # LLM call count (Phase 47.28 ADR-0080): ALL sections deterministic.
        code_calls = [op for op in calls if op == 'ai_code_patch']
        self.assertEqual(len(code_calls), 0)

    def test_21_native_testimonial_props(self):
        nodes = [_node('Testimonial', 'testimonial_section'),
                 _node('Button', 'contact_cta')]
        result, workspace, _ = _run_codegen(_artifact(nodes))
        page = workspace.files['src/pages/index.tsx']
        # quote/author flow from ContentEngine copy + requirements.
        self.assertIn('quote=', page)
        self.assertIn("They transformed our home.", page)
        self.assertIn('Atelier Meridian', page)

    def test_22_shadcn_still_materializes_when_fabricated(self):
        # 47.24 regression: a shadcn card node still materializes under
        # external/ with the .tsx import path (both paths coexist).
        from odoo.addons.nexora_studio.services.source_framework.adapters.shadcn_registry_adapter import (
            ShadcnRegistryAdapter)
        pkg = ShadcnRegistryAdapter().get_component('card')
        node = {
            'provider': 'shadcn_registry',
            'component_id': 'shadcn/card',
            'code': pkg.metadata['source_code'],
            'dependencies': pkg.dependencies,
            'metadata': {**pkg.metadata, 'semantic': 'services_grid',
                         'from_source': True},
        }
        # shadcn node + no native node: services section uses the shadcn card.
        result, workspace, _ = _run_codegen(_artifact([node]))
        self.assertTrue(result.success, result.error)
        self.assertIn('src/components/external/Card.tsx', workspace.files)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn("from '../components/external/Card.tsx'", page)

    def test_23_page_import_merge_duplicate_bindings(self):
        # The observed E2E failure class: an LLM hero section self-carries a
        # whitelisted lucide import despite the instruction, and the
        # deterministic ContactCTA builder injects its own lucide import —
        # duplicate BINDINGS from the same module (esbuild: "Identifier
        # 'MapPin' has already been declared" -> Vite 500). The assembler
        # merges same-module imports into ONE statement.
        nodes = [_node('Button', 'contact_cta')]
        artifact = _artifact(nodes)
        engine = CodeGenerationEngine(MagicMock())
        workspace = _ScaffoldWorkspace()

        def gen(op, payload):
            if op == 'ai_code_patch':
                return {'full_content':
                        "import { ArrowRight, MapPin, Star } from 'lucide-react'\n"
                        'function HeroSection1() { return '
                        '(<section><h1>{"Hero"}</h1><MapPin /></section>) }'}
            return {}

        runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                                  workspace=workspace)
        result = engine.execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        lucide_imports = [l for l in page.splitlines()
                          if l.startswith('import') and 'lucide-react' in l]
        self.assertEqual(len(lucide_imports), 1,
                         'same-module imports must merge into one statement')
        # Union of bindings from BOTH statements (hero self-carried +
        # builder-injected), no duplicate declarations.
        for icon in ('ArrowRight', 'MapPin', 'Star', 'Building2'):
            self.assertIn(icon, lucide_imports[0])
        # Single react import too.
        react_imports = [l for l in page.splitlines()
                         if l.startswith('import') and "from 'react'" in l]
        self.assertEqual(len(react_imports), 1)
        # Body preserved (ContactCTA -> 'Contactcta' + 'Section4').
        self.assertIn('function HeroSection1', page)
        self.assertIn('function ContactctaSection4', page)
        # The hero's lucide import was whitelisted (self-carried), NOT a
        # fallback trigger — the hero body survived validation.
        self.assertIn('MapPin', page)


# ---------------------------------------------------------------------------
# Pattern catalog quality
# ---------------------------------------------------------------------------

class TestPatternQuality(unittest.TestCase):

    def test_30_restaurant_pattern_domain_appropriate(self):
        pattern = select_pattern('Restaurant', 'italian restaurant and cafe')
        self.assertEqual(pattern['id'], 'restaurant')
        home = pattern['home_sections']
        # Menu/featured items replace generic services; About precedes the
        # offer (information architecture).
        self.assertIn('MenuHighlights', home)
        self.assertIn('About', home)
        self.assertNotIn('ServicesGrid', home)
        self.assertLess(home.index('About'), home.index('MenuHighlights'))
        self.assertTrue(any('menu' in r for r in pattern['reason']))

    def test_31_saas_pattern_uses_feature_grid(self):
        pattern = select_pattern('SaaS', 'analytics platform')
        self.assertEqual(pattern['id'], 'saas_product')
        self.assertIn('FeatureGrid', pattern['home_sections'])
        self.assertNotIn('ServicesGrid', pattern['home_sections'])

    def test_32_agency_unchanged(self):
        pattern = select_pattern('Agency', 'architecture studio')
        self.assertEqual(pattern['home_sections'],
                         ['Hero', 'ServicesGrid', 'Testimonial', 'Gallery',
                          'ContactCTA'])

    def test_33_no_duplicate_implementations(self):
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

    def test_34_menuhighlights_builder_menu_typed(self):
        nodes = [_node('Button', 'contact_cta')]
        artifact = _artifact(nodes, sections=['Hero', 'MenuHighlights',
                                              'ContactCTA'])
        artifact = artifact.evolve(content=Content(pages={
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero copy.'},
                      {'type': 'MenuHighlights', 'semantic_heading': 'Our menu',
                       'aria_label': 'm',
                       'body': 'Fresh pasta.\n\nWood-fired pizza.\n\nWine.'},
                      {'type': 'ContactCTA', 'semantic_heading': 'Book',
                       'aria_label': 'c', 'body': 'Book a table.'},
                  ]}},
        ))
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn('function MenuhighlightsSection', page)
        self.assertIn('featured menu items', page)
        # Menu icon vocabulary (no briefcases in the menu).
        self.assertIn('UtensilsCrossed', page)
        self.assertNotIn('Briefcase', page)

    def test_35_featuregrid_section_composes_native(self):
        nodes = [_node('FeatureGrid', 'feature_grid')]
        artifact = _artifact(nodes, sections=['Hero', 'FeatureGrid',
                                              'ContactCTA'])
        artifact = artifact.evolve(content=Content(pages={
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero copy.'},
                      {'type': 'FeatureGrid', 'semantic_heading': 'Capabilities',
                       'aria_label': 'f',
                       'body': 'Intro.\n\nDashboards.\n\nReporting.'},
                      {'type': 'ContactCTA', 'semantic_heading': 'Start',
                       'aria_label': 'c', 'body': 'Start today.'},
                  ]}},
        ))
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn('function FeaturegridSection', page)
        self.assertIn('<FeatureGrid data-nexora-source="native/FeatureGrid"', page)

    def test_36_about_section_deterministic(self):
        nodes = []
        artifact = _artifact(nodes, sections=['Hero', 'About'])
        artifact = artifact.evolve(content=Content(pages={
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero copy.'},
                      {'type': 'About', 'semantic_heading': 'Our story',
                       'aria_label': 'a', 'body': 'Family-run since 1985.'},
                  ]}},
        ))
        result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn('function AboutSection', page)
        self.assertIn('Family-run since 1985.', page)
        self.assertIn('about section', page)


if __name__ == '__main__':
    unittest.main(verbosity=2)
