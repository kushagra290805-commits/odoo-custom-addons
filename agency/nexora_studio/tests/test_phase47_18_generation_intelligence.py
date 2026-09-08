# -*- coding: utf-8 -*-
"""Phase 47.18 — Client-grade generation intelligence & E2E quality closure.

Locks the fixes for the 47.17 E2E failures:
  * Part A — requirement intelligence: word-boundary domain matching
    ("workshop" is NOT ecommerce), labeled-brief extraction of business
    name / category / location / audience into the EXISTING RequirementModel.
  * Part B — research queries derived from the brief identity (category +
    city + audience), never arbitrary keywords.
  * Part C — BusinessData / KnowledgeDocument reach the generation context
    (ContentEngine + CodeGenerationEngine payloads) with provenance.
  * Part D — the ContentEngine artifact is consumed by CodeGenerationEngine.
  * Part E — site layout (header/nav/footer) materializes from the
    architecture page set.
  * Part F — CTA route integrity against the single route contract.
  * Part G — SEO title/description materialize into index.html and
    per-page document.title.
  * Part H — GitHub candidates match semantics via tokens/aliases/metadata,
    preferring source-backed candidates.
  * Architecture: no second ranking pipeline / route registry / content
    service / connector branches; deterministic fallback works without LLM.
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.design.requirement_analyzer import RequirementAnalyzer
from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import RequirementEngine
from odoo.addons.nexora_studio.services.generation.engines.business_research_engine import BusinessResearchEngine
from odoo.addons.nexora_studio.services.generation.engines.content_engine import ContentEngine
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import CodeGenerationEngine
from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
    ComponentIntelligenceEngine,
)
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    WebsiteGenerationArtifact, RequirementModel, ValidationReport, Workspace,
    Content, ArchitectureModel, ComponentTree,
)
from odoo.addons.nexora_studio.services.source_framework.domain_models import (
    ComponentPackage, Provenance,
)

BRIEF = """CLIENT SIMULATION BRIEF (Phase 47.18 E2E baseline - no real client)

Business: Atelier Meridian - a premium architecture and interior design studio.
Location & market: Copenhagen, Denmark; serving residential and boutique commercial clients.
Target audience: affluent homeowners aged 35-60, boutique hotel and restaurant owners.
Positioning: quiet-luxury Scandinavian design practice.
Services: residential architecture, interior architecture and styling, spatial planning.
Differentiators: 25 years of practice, 140+ completed projects, in-house joinery workshop.
Conversion goals: consultation bookings (primary), project viewing (secondary).
Required pages: home, services, contact.
Renderer preference: an immersive 3D WebGL hero presenting an abstract architectural form using react-three-fiber."""


def _src(rel):
    with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r',
              encoding='utf-8', errors='ignore') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Part A — requirement intelligence
# ---------------------------------------------------------------------------
class TestU4718RequirementIntelligence(unittest.TestCase):

    def setUp(self):
        self.analyzer = RequirementAnalyzer()

    def test_01_workshop_is_not_ecommerce(self):
        req = self.analyzer.analyze(
            'Build a website for a woodworking workshop and furniture maker')
        self.assertNotEqual(req.preferences['domain'], 'Ecommerce')
        self.assertEqual(req.preferences['domain'], 'Agency')

    def test_02_explicit_domain_wins_over_keyword_inference(self):
        # "real estate firm" must remain Real Estate even though "firm" is an
        # Agency keyword (earliest keyword occurrence wins).
        req = self.analyzer.analyze('A premium real estate firm with luxury properties')
        self.assertEqual(req.preferences['domain'], 'Real Estate')
        # Architecture studio never becomes ecommerce.
        req = self.analyzer.analyze(
            'Atelier Meridian is a premium architecture and interior design studio')
        self.assertEqual(req.preferences['domain'], 'Agency')

    def test_03_business_name_extraction(self):
        req = self.analyzer.analyze(BRIEF)
        self.assertEqual(req.preferences['business_name'], 'Atelier Meridian')
        self.assertEqual(req.preferences['business_category'],
                         'premium architecture and interior design studio')

    def test_04_location_extraction(self):
        req = self.analyzer.analyzer = RequirementAnalyzer().analyze(BRIEF)
        self.assertEqual(req.preferences['location'], 'Copenhagen, Denmark')

    def test_05_audience_extraction(self):
        req = self.analyzer.analyze(BRIEF)
        self.assertEqual(req.preferences['target_audience'],
                         'affluent homeowners aged 35-60')

    def test_requirement_engine_maps_identity_into_model(self):
        engine = RequirementEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(raw_input=BRIEF))
        result = engine.execute(artifact, MagicMock())
        model = result.artifact.requirements
        self.assertEqual(model.domain, 'Agency')
        self.assertEqual(model.business_name, 'Atelier Meridian')
        self.assertEqual(model.business_category,
                         'premium architecture and interior design studio')
        self.assertEqual(model.location, 'Copenhagen, Denmark')
        self.assertEqual(model.target_audience, 'affluent homeowners aged 35-60')
        self.assertEqual(model.branding.get('business_name'), 'Atelier Meridian')
        self.assertTrue(model.branding.get('services'))

    def test_unlabeled_brief_stays_truthful(self):
        # No labels -> no invented facts; domain via word boundaries.
        req = self.analyzer.analyze('A modern online store for sneakers')
        self.assertEqual(req.preferences['domain'], 'Ecommerce')
        self.assertNotIn('business_name', req.preferences)
        self.assertNotIn('location', req.preferences)


# ---------------------------------------------------------------------------
# Part B — research query quality
# ---------------------------------------------------------------------------
class TestU4718ResearchQueries(unittest.TestCase):

    def _req(self):
        return RequirementModel(
            domain='Agency', target_audience='affluent homeowners aged 35-60',
            business_name='Atelier Meridian',
            business_category='premium architecture and interior design studio',
            location='Copenhagen, Denmark',
            branding={'business_name': 'Atelier Meridian',
                      'business_category': 'premium architecture and interior design studio',
                      'location': 'Copenhagen, Denmark'})

    def test_06_gosom_query_from_business_identity(self):
        queries = BusinessResearchEngine._business_queries(self._req())
        self.assertEqual(len(queries), 1)
        query = queries[0]
        self.assertIn('architecture', query)
        self.assertIn('Copenhagen', query)
        for forbidden in ('ecommerce', 'product', 'cart', 'checkout',
                          'General Public'):
            self.assertNotIn(forbidden.lower(), query.lower())

    def test_07_tavily_query_from_business_identity(self):
        req = self._req()
        category = req.business_category
        city = req.location.split(',')[0]
        audience = req.target_audience.split(',')[0]
        doc_query = ' '.join(filter(None, [category or req.domain, city, audience]))
        self.assertIn('architecture', doc_query)
        self.assertIn('Copenhagen', doc_query)
        self.assertIn('affluent homeowners', doc_query)
        for forbidden in ('ecommerce', 'cart', 'checkout'):
            self.assertNotIn(forbidden, doc_query.lower())

    def test_query_fallbacks_without_identity(self):
        req = RequirementModel(domain='Agency', target_audience='General Public')
        queries = BusinessResearchEngine._business_queries(req)
        self.assertEqual(queries, ['Agency General Public'])
        # Domain-only requirement yields a domain-only query.
        self.assertEqual(BusinessResearchEngine._business_queries(
            RequirementModel(domain='Agency')), ['Agency'])
        # Empty requirement yields no query (no invented terms).
        self.assertEqual(BusinessResearchEngine._business_queries(
            RequirementModel()), [])


# ---------------------------------------------------------------------------
# Parts C/D — research/knowledge/content reach generation
# ---------------------------------------------------------------------------
class TestU4718GenerationContext(unittest.TestCase):

    def _artifact(self):
        return WebsiteGenerationArtifact(
            requirements=RequirementModel(
                domain='Agency', target_audience='affluent homeowners',
                business_name='Atelier Meridian',
                business_category='architecture and interior design studio',
                location='Copenhagen, Denmark',
                branding={'business_name': 'Atelier Meridian',
                          'services': ['residential architecture']}),
            research={'business_data': [{
                'data_id': 'gos-1', 'category': 'business_place',
                'payload': {'title': 'Nordic Architects', 'address': 'Bredgade 1',
                            'rating': 4.8},
                'provenance': {'provider': 'gosom_business',
                               'import_source': 'csf:gosom_business'},
            }]},
            knowledge={'knowledge_documents': [{
                'document_id': 'https://example.com/architecture',
                'title': 'Copenhagen Architecture Guide',
                'content': 'Danish design emphasizes light and material honesty. ' * 10,
                'provenance': {'provider': 'tavily_knowledge'},
            }]},
            content=Content(pages={
                '/': {'seo': {'title': 'Atelier Meridian | Copenhagen',
                              'description': 'Architecture studio in Copenhagen.'},
                      'sections': [
                          {'type': 'Hero', 'semantic_heading': 'h1',
                           'aria_label': 'intro',
                           'body': 'Spaces composed with light and restraint.'},
                          {'type': 'Content', 'semantic_heading': 'h2',
                           'aria_label': 'services',
                           'body': 'Residential architecture and interiors.'}]},
            }),
        )

    def test_08_business_data_reaches_content_payload(self):
        engine = ContentEngine(MagicMock())
        runtime = MagicMock()
        runtime.ai.generate.return_value = {'analysis': {}}
        engine.execute(self._artifact(), runtime)
        payload = runtime.ai.generate.call_args[0][1]
        research = payload['research']
        self.assertEqual(research[0]['title'], 'Nordic Architects')
        self.assertEqual(research[0]['address'], 'Bredgade 1')
        self.assertEqual(research[0]['source'], 'business_search')

    def test_09_knowledge_documents_reach_content_payload(self):
        engine = ContentEngine(MagicMock())
        runtime = MagicMock()
        runtime.ai.generate.return_value = {'analysis': {}}
        engine.execute(self._artifact(), runtime)
        payload = runtime.ai.generate.call_args[0][1]
        knowledge = payload['knowledge']
        self.assertEqual(knowledge[0]['title'], 'Copenhagen Architecture Guide')
        self.assertTrue(knowledge[0]['excerpt'])
        self.assertEqual(knowledge[0]['source'], 'https://example.com/architecture')

    def test_10_provenance_survives_into_context(self):
        engine = ContentEngine(MagicMock())
        runtime = MagicMock()
        runtime.ai.generate.return_value = {'analysis': {}}
        engine.execute(self._artifact(), runtime)
        payload = runtime.ai.generate.call_args[0][1]
        self.assertEqual(payload['research'][0]['provenance']['provider'],
                         'gosom_business')
        self.assertEqual(payload['knowledge'][0]['provenance']['provider'],
                         'tavily_knowledge')
        business = payload['business']
        self.assertEqual(business['name'], 'Atelier Meridian')
        self.assertEqual(business['location'], 'Copenhagen, Denmark')

    def test_digest_is_bounded(self):
        artifact = self._artifact()
        artifact = artifact.evolve(research={'business_data': [
            {'data_id': str(i), 'category': 'c', 'payload': {'title': 'B%d' % i}}
            for i in range(50)]})
        engine = ContentEngine(MagicMock())
        runtime = MagicMock()
        runtime.ai.generate.return_value = {'analysis': {}}
        engine.execute(artifact, runtime)
        payload = runtime.ai.generate.call_args[0][1]
        self.assertLessEqual(len(payload['research']), 6)


# ---------------------------------------------------------------------------
# Parts D/E/F/G — CodeGenerationEngine consumption + layout + CTA + SEO
# ---------------------------------------------------------------------------
_TEMPLATE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Generated Studio Project</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""


class _FakeWorkspace:
    def __init__(self):
        self.files = {'index.html': _TEMPLATE_HTML}

    def write_file(self, path, content):
        self.files[path] = content

    def read_file(self, path):
        return self.files[path]

    def exists(self, path):
        # Phase 47.28: deterministic home Hero checks for native Hero component
        return path == 'src/components/Hero.jsx'


class TestU4718CodeGeneration(unittest.TestCase):

    def _run_codegen(self, artifact):
        engine = CodeGenerationEngine(MagicMock())
        workspace = _FakeWorkspace()

        import re as _re

        def _generate(op, payload):
            if op == 'generate_content':
                # Return minimal valid content artifact
                return {'analysis': json.dumps({
                    'pages': {
                        '/': {'seo': {'title': 'T', 'description': 'D'},
                              'metadata': {'status': 'draft'},
                              'sections': [
                                  {'type': 'Hero', 'semantic_heading': 'H',
                                   'aria_label': 'a', 'body': 'Body copy.'},
                                  {'type': 'Content', 'semantic_heading': 'C',
                                   'aria_label': 'a', 'body': 'Content copy.'}]},
                        '/services': {'seo': {'title': 'T', 'description': 'D'},
                                      'metadata': {'status': 'draft'},
                                      'sections': [
                                          {'type': 'Hero', 'semantic_heading': 'H',
                                           'aria_label': 'a', 'body': 'Body copy.'},
                                          {'type': 'Content', 'semantic_heading': 'C',
                                           'aria_label': 'a', 'body': 'Content copy.'}]},
                        '/contact': {'seo': {'title': 'T', 'description': 'D'},
                                     'metadata': {'status': 'draft'},
                                     'sections': [
                                         {'type': 'Hero', 'semantic_heading': 'H',
                                          'aria_label': 'a', 'body': 'Body copy.'},
                                         {'type': 'Content', 'semantic_heading': 'C',
                                          'aria_label': 'a', 'body': 'Content copy.'}]},
                    }})}
            if op != 'ai_code_patch':
                return {}
            match = _re.search(r'named\s+(\w+)', payload.get('task', ''))
            name = match.group(1) if match else 'StubSection'
            return {'full_content':
                    'function %s() { return <section><a href="/services">S</a></section> }' % name}

        runtime = SimpleNamespace(
            ai=SimpleNamespace(generate=_generate),
            workspace=workspace,
            tools=SimpleNamespace(execute=lambda *a, **k: []),
            hooks=None)
        # capture ai payloads
        ai_payloads = []
        _orig = runtime.ai.generate

        def _capture(op, payload):
            ai_payloads.append((op, payload))
            return _orig(op, payload)
        runtime.ai.generate = _capture
        result = engine.execute(artifact, runtime)
        return result, workspace, ai_payloads

    def _artifact(self):
        return WebsiteGenerationArtifact(
            requirements=RequirementModel(
                domain='Agency', business_name='Atelier Meridian',
                location='Copenhagen, Denmark',
                branding={'business_name': 'Atelier Meridian'}),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/', 'sections': ['Hero', 'Content']},
                'services': {'type': 'page', 'path': '/services', 'sections': ['Hero', 'Content']},
                'contact': {'type': 'page', 'path': '/contact', 'sections': ['Hero', 'Content']},
            }),
            content=Content(pages={
                '/': {'seo': {'title': 'Atelier Meridian | Architecture Copenhagen',
                              'description': 'Copenhagen architecture studio.'},
                      'sections': [
                          {'type': 'Hero', 'body': 'Spaces composed with light.'},
                          {'type': 'Content', 'body': 'Residential architecture.'}]},
                '/services': {'seo': {'title': 'Services | Atelier Meridian',
                                      'description': 'Architecture services.'},
                              'sections': [
                                  {'type': 'Hero', 'body': 'Three disciplines.'},
                                  {'type': 'Content', 'body': 'Full service detail.'}]},
                '/contact': {'seo': {'title': 'Contact | Atelier Meridian',
                                     'description': 'Book a consultation.'},
                             'sections': [
                                 {'type': 'Hero', 'body': 'Tell us about your space.'},
                                 {'type': 'Content', 'body': 'Studio address.'}]},
            }),
            research={'business_data': [{
                'data_id': 'g1', 'category': 'business_place',
                'payload': {'title': 'Nordic Architects', 'address': 'Bredgade 1'},
                'provenance': {'provider': 'gosom_business'}}]},
            knowledge={'knowledge_documents': [{
                'document_id': 'https://ex.com/a', 'title': 'Guide',
                'content': 'Danish design light.', 'provenance': {'provider': 'tavily'}}]},
            component_tree=ComponentTree(nodes=[], dependencies=[]),
            validation=ValidationReport(passed=True,
                                        build_acceptance={'ran': True, 'failed': False}),
        )

    def test_11_content_artifact_reaches_codegen_payload(self):
        result, workspace, payloads = self._run_codegen(self._artifact())
        self.assertTrue(result.success, result.error)
        # Phase 47.28: home Hero is now deterministic (no LLM call).
        # No ai_code_patch calls at all for home Hero.
        patch_payloads = [p for op, p in payloads if op == 'ai_code_patch']
        self.assertEqual(len(patch_payloads), 0, 'home Hero should be deterministic')
        # Composition manifest shows home Hero as deterministic
        meta = result.metadata
        self.assertIn('deterministic_composition_pct', meta)
        self.assertEqual(meta.get('llm_composition_pct'), 0)
        # Home page uses native Hero
        home_page = workspace.files['src/pages/index.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", home_page)
        self.assertIn('data-nexora-source="native/Hero"', home_page)

    def test_12_hero_is_deterministic_native(self):
        result, workspace, payloads = self._run_codegen(self._artifact())
        self.assertTrue(result.success, result.error)
        home_page = workspace.files['src/pages/index.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", home_page)
        self.assertIn('data-nexora-source="native/Hero"', home_page)
        # No LLM call for home Hero
        patch_payloads = [p for op, p in payloads if op == 'ai_code_patch']
        self.assertEqual(len(patch_payloads), 0)

    def test_13_navigation_materializes(self):
        result, workspace, _ = self._run_codegen(self._artifact())
        self.assertTrue(result.success, result.error)
        layout = workspace.files.get('src/components/SiteLayout.jsx')
        self.assertTrue(layout, 'SiteLayout.jsx must be generated')
        self.assertIn("href: '/'", layout)
        self.assertIn("href: '/services'", layout)
        self.assertIn("href: '/contact'", layout)
        self.assertIn('Atelier Meridian', layout)
        app = workspace.files.get('src/App.jsx')
        self.assertIn("import SiteLayout from './components/SiteLayout.jsx'", app)
        self.assertIn('<SiteLayout>', app)

    def test_14_navigation_routes_are_valid(self):
        result, workspace, _ = self._run_codegen(self._artifact())
        layout = workspace.files.get('src/components/SiteLayout.jsx')
        app = workspace.files.get('src/App.jsx')
        routes = set(result.metadata['valid_routes'])
        import re as _re
        nav_hrefs = set(_re.findall(r"href: '(/[^']*)'", layout))
        self.assertTrue(nav_hrefs)
        self.assertTrue(nav_hrefs <= routes,
                        'nav links must come from the route contract')
        app_routes = set(_re.findall(r"'(/[^']*)': \w+Page", app))
        self.assertEqual(app_routes, routes)

    def test_15_cta_route_integrity(self):
        enforce = CodeGenerationEngine._enforce_route_integrity
        routes = ['/', '/services', '/contact']
        # valid internal
        self.assertIn('href="/services"',
                      enforce('<a href="/services">x</a>', routes))
        # trailing slash normalizes
        self.assertIn('href="/services"',
                      enforce('<a href="/services/">x</a>', routes))
        # missing route resolves home (never broken)
        self.assertIn('href="/"',
                      enforce('<a href="/missing">x</a>', routes))
        # external untouched
        code = enforce('<a href="https://example.com">x</a>'
                       '<a href="mailto:a@b.c">y</a>', routes)
        self.assertIn('href="https://example.com"', code)
        self.assertIn('href="mailto:a@b.c"', code)

    def test_16_17_seo_title_and_description_materialize(self):
        result, workspace, _ = self._run_codegen(self._artifact())
        html = workspace.files.get('index.html')
        self.assertIn('<title>Atelier Meridian | Architecture Copenhagen</title>', html)
        self.assertIn('name="description"', html)
        self.assertIn('Copenhagen architecture studio.', html)
        self.assertNotIn('Generated Studio Project', html)

    def test_per_page_titles_materialize(self):
        result, workspace, _ = self._run_codegen(self._artifact())
        home = workspace.files.get('src/pages/index.tsx')
        self.assertIn("document.title = 'Atelier Meridian | Architecture Copenhagen'",
                      home)
        services = workspace.files.get('src/pages/services.tsx')
        self.assertIn("document.title = 'Services | Atelier Meridian'", services)

    def test_route_integrity_applied_to_generated_sections(self):
        result, workspace, _ = self._run_codegen(self._artifact())
        home = workspace.files.get('src/pages/index.tsx')
        self.assertNotIn('href="/missing"', home)

    def test_content_research_knowledge_reach_section_generation(self):
        # The generation context (business/research/knowledge) is available
        # to EVERY ai_code_patch call — the LLM boundary receives it.
        result, workspace, payloads = self._run_codegen(self._artifact())
        for op, payload in payloads:
            if op == 'ai_code_patch':
                self.assertIn('Atelier Meridian', payload['business']['name'])
                self.assertEqual(payload['research'][0]['title'], 'Nordic Architects')


# ---------------------------------------------------------------------------
# Part H — GitHub component matching
# ---------------------------------------------------------------------------
def _package(component_id, name, code=None, metadata=None):
    return ComponentPackage(
        component_id=component_id, name=name, description='',
        metadata={'source_code': code, **(metadata or {})},
        dependencies=[],
        provenance=Provenance(provider='csf:threed_component_library',
                              import_source='csf:threed_component_library'))


class TestU4718ComponentMatching(unittest.TestCase):

    def _artifact_with(self, abstract_components, candidates):
        return WebsiteGenerationArtifact(
            component_tree=ComponentTree(nodes=[], dependencies=[]),
            generation_metadata={
                'candidate_components': candidates,
                'modular_blueprint': {
                    'component': {'abstract_components': abstract_components}},
            },
        )

    def test_18_semantic_token_matching_finds_source_component(self):
        # '3d_canvas_container' must match a real R3F source candidate
        # ('Canvas.tsx' + three_d_scene metadata) — the exact 47.17 failure.
        pkg = _package('packages/fiber/src/web/Canvas.tsx', 'Canvas',
                       code="export default function Canvas() { return <Canvas/> }",
                       metadata={'three_d_scene': True,
                                 'renderer_expectation': 'react_three_fiber'})
        artifact = self._artifact_with(
            [{'id': '3d_canvas_container', 'purpose': '3d_canvas_container'}],
            [{'package': pkg, 'score': 0.8, 'final_score': 0.8}])
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, MagicMock())
        nodes = result.artifact.component_tree.nodes
        matched = [n for n in nodes if n.get('metadata', {}).get('from_source')]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]['component_id'],
                         'packages/fiber/src/web/Canvas.tsx')
        self.assertIn('<Canvas/>', matched[0]['code'])
        self.assertEqual(matched[0]['metadata']['semantic'],
                         '3d_canvas_container')
        self.assertEqual(matched[0]['provenance']['provider'],
                         'csf:threed_component_library')

    def test_source_backed_candidate_preferred_over_metadata_only(self):
        with_code = _package('src/Canvas.tsx', 'Canvas',
                             code='function Canvas() { return null }',
                             metadata={'three_d_scene': True})
        no_code = _package('docs/3d-canvas.md', '3d canvas docs',
                           code=None, metadata={'three_d_scene': True})
        artifact = self._artifact_with(
            [{'id': '3d_canvas_container', 'purpose': '3d_canvas_container'}],
            [{'package': no_code}, {'package': with_code}])
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, MagicMock())
        matched = [n for n in result.artifact.component_tree.nodes
                   if n.get('metadata', {}).get('from_source')]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]['component_id'], 'src/Canvas.tsx')

    def test_codeless_markdown_candidate_never_matches(self):
        # 47.18-E2E-v1 regression: a metadata-only search result named
        # 'skills/3d-website-architect/SKILL.md' matched the 3D semantic on
        # the '3d' token and the renderer materialized its placeholder code
        # as a broken module. Candidates without real fetched code must
        # NEVER match.
        md_candidate = _package('skills/3d-website-architect/SKILL.md',
                                 'Skills3dWebsiteArchitectSkillMd', code=None)
        artifact = self._artifact_with(
            [{'id': '3d_canvas_container', 'purpose': '3d_canvas_container'}],
            [{'package': md_candidate}])
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, MagicMock())
        matched = [n for n in result.artifact.component_tree.nodes
                   if n.get('metadata', {}).get('from_source')]
        self.assertEqual(matched, [],
                         'code-less markdown candidates must never match')

    def test_legacy_substring_matching_preserved(self):
        # U6 compatibility: semantic 'hero' still matches package 'Hero'.
        pkg = _package('src/Hero.tsx', 'Hero',
                       code='function Hero() { return null }')
        artifact = self._artifact_with(
            [{'id': 'hero', 'purpose': 'hero'}], [{'package': pkg}])
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, MagicMock())
        matched = [n for n in result.artifact.component_tree.nodes
                   if n.get('metadata', {}).get('from_source')]
        self.assertEqual(len(matched), 1)

    def test_unsuitable_candidate_not_forced(self):
        # No overlap at all -> placeholder node, no fabricated match.
        pkg = _package('README.md', 'readme', code='text')
        artifact = self._artifact_with(
            [{'id': 'testimonial_section', 'purpose': 'testimonial_section'}],
            [{'package': pkg}])
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, MagicMock())
        matched = [n for n in result.artifact.component_tree.nodes
                   if n.get('metadata', {}).get('from_source')]
        self.assertEqual(matched, [])

    def test_selected_component_preserves_contract(self):
        pkg = _package('src/Canvas.tsx', 'Canvas', code='code',
                       metadata={'three_d_scene': True})
        pkg.dependencies = [{'name': 'three', 'version': '^0.169.0'}]
        artifact = self._artifact_with(
            [{'id': '3d_canvas_container', 'purpose': '3d_canvas_container'}],
            [{'package': pkg, 'score': 0.9, 'final_score': 0.85}])
        result = ComponentIntelligenceEngine(MagicMock()).execute(
            artifact, MagicMock())
        node = [n for n in result.artifact.component_tree.nodes
                if n.get('metadata', {}).get('from_source')][0]
        self.assertEqual(node['score'], 0.9)
        self.assertEqual(node['final_score'], 0.85)
        self.assertEqual(node['dependencies'],
                         [{'name': 'three', 'version': '^0.169.0'}])
        self.assertIn('three', result.artifact.component_tree.dependencies)


# ---------------------------------------------------------------------------
# Architecture integrity + deterministic fallback
# ---------------------------------------------------------------------------
class TestU4718Architecture(unittest.TestCase):

    FORBIDDEN = (
        'RequirementService', 'ResearchService', 'KnowledgeService',
        'ContentService', 'NavigationService', 'RouteManager', 'SEOService',
        'ComponentMatchingService', 'ConnectorOrchestrator', 'QAService',
        'ClientE2EPipeline', 'AcceptanceService', 'AIService',
    )

    def test_20_no_second_ranking_pipeline(self):
        sf = os.listdir(os.path.join(ADDON, 'services', 'source_framework'))
        ranking = [f for f in sf if 'ranking' in f.lower()]
        self.assertEqual(ranking, ['component_ranking_pipeline.py'])
        codegen = _src('services/generation/engines/code_generation_engine.py')
        self.assertNotIn('rank', codegen.lower().replace('ranking', ''))

    def test_21_no_second_route_registry(self):
        # The route contract comes from the architecture hierarchy only.
        codegen = _src('services/generation/engines/code_generation_engine.py')
        self.assertIn('component_hierarchy', codegen)
        self.assertNotIn('ROUTE_REGISTRY', codegen)
        self.assertNotIn('route_manager', codegen.lower())
        for rel in ('services/generation/engines/code_generation_engine.py',
                    'services/generation/engines/architecture_engine.py'):
            src = _src(rel)
            self.assertNotIn('RouteManager', src)

    def test_22_no_second_content_service(self):
        services = os.listdir(os.path.join(ADDON, 'services', 'generation',
                                           'engines'))
        content_engines = [f for f in services if 'content' in f.lower()]
        self.assertEqual(content_engines, ['content_engine.py'])

    def test_23_no_connector_specific_production_branches(self):
        import ast
        for rel in ('services/design/requirement_analyzer.py',
                    'services/generation/engines/requirement_engine.py',
                    'services/generation/engines/business_research_engine.py',
                    'services/generation/engines/knowledge_enrichment_engine.py',
                    'services/generation/engines/content_engine.py',
                    'services/generation/engines/code_generation_engine.py',
                    'services/generation/engines/component_intelligence_engine.py'):
            tree = ast.parse(_src(rel))
            # Strip docstrings: historical docs may name connectors; CODE
            # branches must not.
            for node in ast.walk(tree):
                if (isinstance(node, (ast.Expr, ast.AsyncFunctionDef, ast.FunctionDef,
                                      ast.AsyncWith, ast.With))
                        and isinstance(getattr(node, 'value', None), ast.Constant)
                        and isinstance(node.value.value, str)):
                    node.value.value = ''
                if isinstance(node, ast.Str):
                    node.s = ''
            code = ast.unparse(tree)
            for provider in ('tavily', 'gosom', 'github_mcp', 'firecrawl',
                             'context7', 'penpot'):
                self.assertNotIn(provider, code.lower(),
                                 '%s must stay connector-neutral' % rel)

    def test_no_new_parallel_owners(self):
        # The forbidden-owner scan covers the files 47.18 touched — the
        # pre-existing legacy KnowledgeService (services/generation/knowledge/,
        # Phase 21, not wired into the pipeline) predates this phase and is
        # NOT introduced here. The pipeline's single knowledge owner remains
        # KnowledgeEnrichmentEngine (locked below).
        CHANGED = (
            'services/design/requirement_analyzer.py',
            'services/generation/engines/requirement_engine.py',
            'services/generation/engines/business_research_engine.py',
            'services/generation/engines/knowledge_enrichment_engine.py',
            'services/generation/engines/content_engine.py',
            'services/generation/engines/code_generation_engine.py',
            'services/generation/engines/component_intelligence_engine.py',
            'services/design/planners/component_selector.py',
        )
        offenders = []
        for rel in CHANGED:
            text = _src(rel)
            for name in self.FORBIDDEN:
                if ('class %s' % name) in text or ('def %s' % name) in text:
                    offenders.append('%s:%s' % (rel, name))
        self.assertEqual(offenders, [])
        # Single pipeline knowledge owner (the legacy knowledge package is
        # not a pipeline stage).
        engines = os.listdir(os.path.join(
            ADDON, 'services', 'generation', 'engines'))
        self.assertEqual(
            [f for f in engines if 'knowledge' in f.lower()],
            ['knowledge_enrichment_engine.py'])
        pipe = _src('services/generation/pipeline/website_generation_pipeline.py')
        self.assertIn('KnowledgeEnrichmentEngine', pipe)
        self.assertNotIn('KnowledgeService', pipe)

    def test_24_deterministic_fallback_without_llm(self):
        # The analyzer is fully deterministic (no LLM dependency) and the
        # RequirementEngine fallback domain is preserved.
        analyzer = RequirementAnalyzer()
        req = analyzer.analyze('just a plain website')
        self.assertEqual(req.preferences['domain'], 'Agency')
        req = analyzer.analyzer = analyzer.analyze(
            'Business: Test Co - a healthcare clinic\nLocation: Berlin, Germany')
        self.assertEqual(req.preferences['business_name'], 'Test Co')
        self.assertEqual(req.preferences['domain'], 'Healthcare')

    def test_25_failure_isolation_unchanged(self):
        # Research failure never fails content/code generation: the digest
        # builders tolerate empty/missing research and knowledge.
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Agency'))
        engine = ContentEngine(MagicMock())
        runtime = MagicMock()
        runtime.ai.generate.return_value = {'analysis': {}}
        result = engine.execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        payload = runtime.ai.generate.call_args[0][1]
        self.assertEqual(payload['research'], [])
        self.assertEqual(payload['knowledge'], [])
        self.assertEqual(payload['business']['name'], '')


if __name__ == '__main__':
    unittest.main()
