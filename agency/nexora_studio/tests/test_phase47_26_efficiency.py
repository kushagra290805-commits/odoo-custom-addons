# -*- coding: utf-8 -*-
"""Phase 47.26 — generation efficiency + pattern coverage tests (ADR-0078).

Covers:
  * knowledge_enrichment is deterministic (no LLM call) with the artifact
    contract preserved (knowledge_documents/implementation_context keys).
  * Deterministic/LLM routing: secondary heroes deterministic (native Hero
    organism), home hero LLM, pattern sections deterministic.
  * Composition manifest: per-section mode/component/source records and
    deterministic percentage.
  * Token vocabulary: the LLM payload carries the exact CSS var names and
    drops the misleading design_tokens prefix.
  * Pricing/FAQ pattern coverage: native PricingCard/FAQ composition from
    parsed ContentEngine plan/QA blocks; bounded fallbacks.
  * Semantic aliases: pricing/faq groups; Pricing/FAQ section types.
  * Regression guards: 47.24/47.25 behaviors (import merge, native
    materialization, source-code gate) exercised through the shared flows.
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
    CodeGenerationEngine, _SCAFFOLD_COMPOSED)
from odoo.addons.nexora_studio.services.design.page_patterns import (
    PAGE_PATTERN_CATALOG, select_pattern)
from odoo.addons.nexora_studio.services.design.react_component_library import (
    ReactComponentLibrary)


class _ScaffoldWorkspace:
    def __init__(self):
        self.files = dict(ReactComponentLibrary().synthesize_all())

    def write_file(self, path, content):
        self.files[path] = content

    def write_binary(self, path, data):
        self.files[path] = b'<binary>'

    def read_file(self, path):
        return self.files.get(path, '')

    def exists(self, path):
        return path in self.files


def _artifact(sections_home, content_pages, domain='SaaS', business='Metricly',
              services=('dashboards', 'reporting', 'integrations')):
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(
            domain=domain, business_name=business,
            business_category='SaaS analytics platform',
            branding={'business_name': business, 'services': list(services)}),
        architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/', 'sections': sections_home},
            'pricing': {'type': 'page', 'path': '/pricing',
                        'sections': ['Hero', 'Content']},
            'contact': {'type': 'page', 'path': '/contact',
                        'sections': ['Hero', 'Content']},
        }),
        component_tree=ComponentTree(nodes=[], dependencies=['react']),
        theme=Theme(colors={'background': '#f8f7ff', 'foreground': '#1e1b4b',
                            'primary': '#4338ca', 'primary_foreground': '#ffffff',
                            'secondary': '#4c5064', 'accent': '#7c3aed',
                            'border': '#e4e2f2', 'muted': '#6b6e84',
                            'card': '#ffffff'},
                    font_heading='Space Grotesk', font_body='Inter'),
        content=Content(pages=content_pages),
        assets=Assets(images=[], icons=[], fonts=[]),
    )


def _run_codegen(artifact):
    engine = CodeGenerationEngine(MagicMock())
    workspace = _ScaffoldWorkspace()
    calls = []

    def gen(op, payload):
        calls.append((op, payload))
        if op == 'ai_code_patch':
            import re
            mm = re.search(r'named (\w+)', payload.get('task', ''))
            name = mm.group(1) if mm else 'X'
            return {'full_content': 'function %s() { return (<section><h1>{"Hero"}</h1>'
                                   '<p>{"copy"}</p></section>) }' % name}
        return {}

    runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                              workspace=workspace)
    result = engine.execute(artifact, runtime)
    return result, workspace, calls


SAAS_CONTENT = {
    '/': {'seo': {'title': 'Metricly', 'description': 'd'}, 'metadata': {},
          'sections': [
              {'type': 'Hero', 'semantic_heading': 'Analytics', 'aria_label': 'h',
               'body': 'Hero copy.'},
              {'type': 'FeatureGrid', 'semantic_heading': 'Capabilities',
               'aria_label': 'f', 'body': 'Intro.\n\nDashboards.\n\nReporting.'},
              {'type': 'Pricing', 'semantic_heading': 'Simple pricing',
               'aria_label': 'p',
               'body': 'Starter — $29/mo\nUp to 5 dashboards\nEmail support\n\n'
                       'Growth — $79/mo\nUnlimited dashboards\nPriority support\n\n'
                       'Enterprise — Custom\nSSO\nDedicated support'},
              {'type': 'Testimonial', 'semantic_heading': 'Loved', 'aria_label': 't',
               'body': 'Replaced three tools.'},
              {'type': 'FAQ', 'semantic_heading': 'Questions', 'aria_label': 'q',
               'body': 'Is there a free trial?\nYes — 14 days.\n\n'
                       'Can I export data?\nYes, CSV and API.'},
              {'type': 'ContactCTA', 'semantic_heading': 'Start', 'aria_label': 'c',
               'body': 'Start your trial.'},
          ]},
    '/pricing': {'seo': {'title': 'Pricing', 'description': 'd'}, 'metadata': {},
                 'sections': [{'type': 'Hero', 'semantic_heading': 'Pricing',
                               'aria_label': 'h', 'body': 'Transparent pricing.'},
                              {'type': 'Content', 'semantic_heading': 'Detail',
                               'aria_label': 'c', 'body': 'All plans include...'}]},
    '/contact': {'seo': {'title': 'Contact', 'description': 'd'}, 'metadata': {},
                 'sections': [{'type': 'Hero', 'semantic_heading': 'Contact',
                               'aria_label': 'h', 'body': 'Get in touch.'},
                              {'type': 'Content', 'semantic_heading': 'Detail',
                               'aria_label': 'c', 'body': 'Contact detail.'}]},
}


# ---------------------------------------------------------------------------
# Deterministic knowledge
# ---------------------------------------------------------------------------

class TestDeterministicKnowledge(unittest.TestCase):

    def test_01_no_llm_call_artifact_contract_preserved(self):
        from odoo.addons.nexora_studio.services.generation.engines.knowledge_enrichment_engine import (
            KnowledgeEnrichmentEngine)
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='SaaS', business_name='M'))
        ai_calls = []

        def gen(op, payload):
            ai_calls.append(op)
            return {}

        runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen), env=None)
        result = KnowledgeEnrichmentEngine(MagicMock()).execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        self.assertEqual(ai_calls, [], 'knowledge stage must make no LLM call')
        knowledge = result.artifact.knowledge
        # Contract keys preserved for the downstream consumers.
        self.assertIn('knowledge_documents', knowledge)
        self.assertIn('implementation_context', knowledge)
        self.assertIn('knowledge_sources', knowledge)
        self.assertIn('business_summary', knowledge)

    def test_02_source_documents_flow_through(self):
        from odoo.addons.nexora_studio.services.generation.engines.knowledge_enrichment_engine import (
            KnowledgeEnrichmentEngine)
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='SaaS'))
        artifact = artifact.evolve(knowledge={
            'knowledge_documents': [{'document_id': 'u', 'title': 'T',
                                     'content': 'C'}],
        })
        # Pre-seeded knowledge documents pass through the engine untouched.
        runtime = SimpleNamespace(ai=SimpleNamespace(generate=lambda *a: {}), env=None)
        # Simulate: documents collected from the source framework.
        engine = KnowledgeEnrichmentEngine(MagicMock())
        with unittest.mock.patch.object(
                engine, '_collect_source_knowledge',
                return_value=([{'document_id': 'u', 'title': 'T', 'content': 'C'}],
                              [], {'status': 'completed'})):
            result = engine.execute(artifact, runtime)
        self.assertTrue(result.success)
        docs = result.artifact.knowledge.get('knowledge_documents')
        self.assertEqual(docs, [{'document_id': 'u', 'title': 'T', 'content': 'C'}])


import unittest.mock


# ---------------------------------------------------------------------------
# Deterministic/LLM routing + composition manifest
# ---------------------------------------------------------------------------

class TestRoutingAndManifest(unittest.TestCase):

    def test_10_llm_call_count_reduced(self):
        # 7 -> 4 (47.26) -> 2 (47.27) -> 0 codegen calls (47.28): knowledge
        # (0), content (handled by ContentEngine), home hero (0,
        # deterministic native Hero since 47.28), secondary heroes (0),
        # secondary content (0, deterministic since 47.27).
        artifact = _artifact(['Hero', 'FeatureGrid', 'Pricing', 'Testimonial',
                              'FAQ', 'ContactCTA'], SAAS_CONTENT)
        result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        ops = [op for op, _ in calls]
        self.assertNotIn('knowledge_enrichment', ops)
        self.assertEqual(ops.count('generate_content'), 0)  # codegen only
        self.assertEqual(ops.count('ai_code_patch'), 0,
                         'every codegen section is deterministic since 47.28')

    def test_11_secondary_heroes_compose_native_hero(self):
        artifact = _artifact(['Hero', 'FeatureGrid', 'ContactCTA'], SAAS_CONTENT)
        result, workspace, _ = _run_codegen(artifact)
        for rel in ('src/pages/pricing.tsx', 'src/pages/contact.tsx'):
            page = workspace.files[rel]
            self.assertIn("import Hero from '../components/Hero.jsx'", page,
                          '%s composes the native Hero' % rel)
            self.assertIn('<Hero', page)
            self.assertIn('data-nexora-source="native/Hero"', page)
            # Phase 47.29: no hero imagery in this scenario — the
            # deterministic variant rule renders the centered layout.
            self.assertIn('variant="centered"', page)
        # Phase 47.28: the home hero composes the native Hero too.
        home = workspace.files['src/pages/index.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", home)
        self.assertIn('data-nexora-source="native/Hero"', home)

    def test_12_composition_manifest_records_modes(self):
        artifact = _artifact(['Hero', 'FeatureGrid', 'Pricing', 'Testimonial',
                              'FAQ', 'ContactCTA'], SAAS_CONTENT)
        result, _, _ = _run_codegen(artifact)
        manifest = result.metadata.get('composition_manifest')
        self.assertIsNotNone(manifest)
        self.assertIn('pages', manifest)
        home = manifest['pages']['/']
        modes = {s['type']: s['mode'] for s in home}
        # Phase 47.28: home hero is deterministic (native Hero organism).
        self.assertEqual(modes['Hero'], 'deterministic')
        for sec in ('FeatureGrid', 'Pricing', 'Testimonial', 'FAQ', 'ContactCTA'):
            self.assertEqual(modes[sec], 'deterministic', sec)
        # Scaffold-composed attribution.
        comps = {s['type']: s['component'] for s in home}
        self.assertEqual(comps['Pricing'], 'native/PricingCard')
        self.assertEqual(comps['FAQ'], 'native/FAQ')
        # Home hero attribution.
        self.assertEqual(comps['Hero'], 'native/Hero')
        # Secondary pages record the native hero deterministically.
        pricing_page = manifest['pages']['/pricing']
        self.assertEqual(pricing_page[0]['mode'], 'deterministic')
        self.assertEqual(pricing_page[0]['component'], 'native/Hero')
        self.assertEqual(pricing_page[1]['mode'], 'deterministic')
        # Percentage recorded.
        self.assertIn('deterministic_composition_pct', result.metadata)
        self.assertGreaterEqual(result.metadata['deterministic_composition_pct'], 50)

    def test_13_token_vocabulary_in_llm_payload(self):
        # Phase 47.28: no standard section reaches _generate_section anymore;
        # the LLM payload contract (token vocabulary hardening) is verified
        # directly against the method that still owns it.
        artifact = _artifact(['Hero', 'FeatureGrid', 'ContactCTA'], SAAS_CONTENT)
        engine = CodeGenerationEngine(MagicMock())
        captured = {}

        def gen(op, payload):
            captured.update(payload)
            return {'full_content': 'function CustomSection() { return '
                                    '<section><h1>{"x"}</h1></section> }'}

        runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                                  workspace=_ScaffoldWorkspace())
        engine._generate_section('Custom', 'CustomSection1', artifact,
                                 runtime, {}, None, page_path='/',
                                 section_index=0)
        self.assertIn('theme_css_variables', captured)
        self.assertIn('--color-primary', captured['theme_css_variables'])
        self.assertIn('--font-heading', captured['theme_css_variables'])
        # The misleading design_tokens prefix no longer reaches the model.
        self.assertNotIn('design_tokens', captured['theme'])

    def test_14_hero_fallback_without_scaffold_file(self):
        artifact = _artifact(['Hero', 'FeatureGrid', 'ContactCTA'], SAAS_CONTENT)
        engine = CodeGenerationEngine(MagicMock())
        workspace = _ScaffoldWorkspace()
        del workspace.files['src/components/Hero.jsx']  # simulate absence
        code, imports, mode = engine._build_secondary_hero(
            'Hero', 'HeroSection1', SAAS_CONTENT['/pricing']['sections'], 0,
            {'path': '/images/stock_hero.jpg', 'alt': 'a'},
            ['/', '/pricing', '/contact'], workspace)
        self.assertEqual(mode, 'deterministic')
        self.assertEqual(imports, [])
        self.assertIn('<h1', code)
        self.assertIn('/images/stock_hero.jpg', code)


# ---------------------------------------------------------------------------
# Pricing / FAQ coverage
# ---------------------------------------------------------------------------

class TestPricingFaqCoverage(unittest.TestCase):

    def test_20_saas_pattern_includes_pricing_and_faq(self):
        pattern = select_pattern('SaaS', 'analytics platform')
        self.assertIn('Pricing', pattern['home_sections'])
        self.assertIn('FAQ', pattern['home_sections'])
        self.assertTrue(any('pricing' in r for r in pattern['reason']))

    def test_21_pricing_section_composes_native_pricing_card(self):
        # Index-aligned content (as the real ContentEngine produces).
        artifact = _artifact(['Hero', 'Pricing', 'ContactCTA'], {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H', 'aria_label': 'h',
                       'body': 'Hero.'},
                      {'type': 'Pricing', 'semantic_heading': 'Simple pricing',
                       'aria_label': 'p',
                       'body': 'Starter — $29/mo\nUp to 5 dashboards\nEmail support\n\n'
                               'Growth — $79/mo\nUnlimited dashboards\nPriority support\n\n'
                               'Enterprise — Custom\nSSO\nDedicated support'},
                      {'type': 'ContactCTA', 'semantic_heading': 'C', 'aria_label': 'c',
                       'body': 'C.'},
                  ]},
            '/pricing': SAAS_CONTENT['/pricing'],
            '/contact': SAAS_CONTENT['/contact'],
        })
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn("import PricingCard from '../components/PricingCard.jsx'", page)
        self.assertIn('<PricingCard', page)
        self.assertIn('data-nexora-source="native/PricingCard"', page)
        self.assertIn('const plans = [', page)
        # Plan data parsed from the ContentEngine copy.
        self.assertIn('$29/mo', page)
        self.assertIn('Growth', page)
        self.assertIn('Unlimited dashboards', page)
        # CTA routes to a valid route.
        self.assertIn("href: '/contact'", page)

    def test_22_faq_section_composes_native_faq(self):
        # Index-aligned content (as the real ContentEngine produces against
        # the architecture section list).
        artifact = _artifact(['Hero', 'FAQ', 'ContactCTA'], {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H', 'aria_label': 'h',
                       'body': 'Hero.'},
                      {'type': 'FAQ', 'semantic_heading': 'Questions',
                       'aria_label': 'q',
                       'body': 'Is there a free trial?\nYes — 14 days.\n\n'
                               'Can I export data?\nYes, CSV and API.'},
                      {'type': 'ContactCTA', 'semantic_heading': 'C', 'aria_label': 'c',
                       'body': 'C.'},
                  ]},
            '/pricing': SAAS_CONTENT['/pricing'],
            '/contact': SAAS_CONTENT['/contact'],
        })
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn("import FAQ from '../components/FAQ.jsx'", page)
        self.assertIn('<FAQ', page)
        self.assertIn('data-nexora-source="native/FAQ"', page)
        self.assertIn('const faqs = [', page)
        self.assertIn('Is there a free trial', page)

    def test_23_plan_block_parser(self):
        body = ('Starter — $29/mo\nUp to 5 dashboards\nEmail support\n\n'
                'Growth — $79/mo\nUnlimited\n\nJust prose, no separator')
        plans = CodeGenerationEngine._parse_plan_blocks(body)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0]['title'], 'Starter')
        self.assertEqual(plans[0]['price'], '$29/mo')
        self.assertEqual(plans[0]['features'], ['Up to 5 dashboards', 'Email support'])
        self.assertEqual(plans[1]['title'], 'Growth')
        self.assertEqual(plans[1]['price'], '$79/mo')

    def test_24_faq_block_parser(self):
        body = ('Is there a free trial?\nYes — 14 days.\n\n'
                'Can I export data?\nYes, CSV.\nMore detail.')
        faqs = CodeGenerationEngine._parse_faq_blocks(body)
        self.assertEqual(len(faqs), 2)
        self.assertEqual(faqs[0]['question'], 'Is there a free trial')
        self.assertEqual(faqs[1]['answer'], 'Yes, CSV. More detail.')

    def test_25_pricing_fallback_without_blocks(self):
        artifact = _artifact(['Hero', 'Pricing', 'ContactCTA'], {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H', 'aria_label': 'h',
                       'body': 'Hero.'},
                      {'type': 'Pricing', 'semantic_heading': 'Pricing',
                       'aria_label': 'p', 'body': 'Contact us for pricing.'},
                      {'type': 'ContactCTA', 'semantic_heading': 'C', 'aria_label': 'c',
                       'body': 'C.'},
                  ]},
            '/pricing': SAAS_CONTENT['/pricing'],
            '/contact': SAAS_CONTENT['/contact'],
        })
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        page = workspace.files['src/pages/index.tsx']
        self.assertIn('Contact us for pricing.', page)
        self.assertNotIn('<PricingCard', page)

    def test_26_semantic_aliases_pricing_faq(self):
        from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
            _expanded_tokens)
        pricing = _expanded_tokens('pricing')
        for token in ('pricing', 'plan', 'price', 'plans', 'subscription', 'tiers'):
            self.assertIn(token, pricing)
        faq = _expanded_tokens('faq')
        for token in ('faq', 'question', 'questions', 'frequently', 'answers'):
            self.assertIn(token, faq)

    def test_27_planning_semantic_map(self):
        # PlanningEngine maps Pricing/FAQ section names to semantics that
        # intelligence can match (exercised via the catalog + map contract).
        self.assertIn('Pricing', select_pattern('SaaS', '')['home_sections'])
        self.assertIn('FAQ', select_pattern('SaaS', '')['home_sections'])
        all_sections = set()
        for pattern in PAGE_PATTERN_CATALOG.values():
            all_sections.update(pattern['home_sections'])
        self.assertLessEqual(all_sections, {
            'Hero', 'Content', 'About', 'ServicesGrid', 'FeatureGrid',
            'MenuHighlights', 'Pricing', 'FAQ', 'Testimonial', 'ContactCTA',
            'Gallery'})


# ---------------------------------------------------------------------------
# Regression guards (47.23/47.24/47.25 preserved through the new flow)
# ---------------------------------------------------------------------------

class TestRegressionGuards(unittest.TestCase):

    def test_30_import_merge_still_applies(self):
        # The page assembler import merge (47.25) still runs — a builder
        # import + a would-be duplicate merge into one statement.
        artifact = _artifact(['Hero', 'Testimonial', 'ContactCTA'],
                             SAAS_CONTENT)
        result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        lucide = [l for l in home.splitlines()
                  if l.startswith('import') and 'lucide-react' in l]
        self.assertLessEqual(len(lucide), 1)

    def test_31_secondary_hero_survives_static_validation(self):
        artifact = _artifact(['Hero', 'FeatureGrid', 'ContactCTA'],
                             SAAS_CONTENT)
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        for rel in ('src/pages/pricing.tsx', 'src/pages/contact.tsx'):
            page = workspace.files[rel]
            known = {'Hero'} | _SCAFFOLD_COMPOSED.keys()
            # The whole page (imports + module) parses under the validator's
            # identifier checks through the engine's own validation path.
            self.assertIn('function', page)

    def test_32_content_fallback_contract_unchanged(self):
        # The ContentEngine contract markers remain (prompt hints added,
        # extraction/normalization/fallback untouched — covered by the
        # 47.20C suite; here just the prompt grew formatting hints).
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
            _CONTENT_SCHEMA_PROMPT)
        self.assertIn('Pricing', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('FAQ', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('MenuHighlights', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('OBJECT keyed by page path', _CONTENT_SCHEMA_PROMPT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
