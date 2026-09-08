# -*- coding: utf-8 -*-
"""Phase 47.28 — client quality + asset relevance + evidence-gated home Hero.

Covers (ADR-0080):
  * AssetEngine deterministic relevance ranking: relevant candidates
    outrank irrelevant ones; ordering is stable/deterministic.
  * Stock intent construction is section-aware (role + context).
  * Deterministic home Hero: native Hero organism, ContentArtifact copy,
    AssetEngine imagery, business-derived CTA label; zero LLM calls.
  * Composition manifest: home Hero recorded as deterministic.
  * 47.27 structured-content regressions (ProductGrid/PricingCard/FAQ from
    items) remain intact with the deterministic home Hero.
  * Decision-gate evidence: the A/B comparison contract (control = LLM hero,
    candidate = deterministic hero) is captured in this phase's report; these
    tests lock the WINNING candidate's behavior.
"""
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
from odoo.addons.nexora_studio.services.generation.engines.asset_engine import (
    AssetEngine)
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


def _artifact(domain, business, sections_home, content_pages, **kwargs):
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(
            domain=domain, business_name=business,
            business_category='%s business' % domain,
            branding=kwargs.get('branding') or {
                'business_name': business,
                'services': kwargs.get('services') or ['service one',
                                                       'service two']}),
        architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/', 'sections': sections_home},
            'detail': {'type': 'page', 'path': '/detail',
                       'sections': ['Hero', 'Content']},
        }),
        component_tree=ComponentTree(nodes=[], dependencies=['react']),
        theme=Theme(colors={'background': '#f8fafc', 'foreground': '#0f172a',
                            'primary': '#3f5c76', 'primary_foreground': '#ffffff',
                            'secondary': '#475569', 'accent': '#0e7490',
                            'border': '#e2e8f0', 'muted': '#5f6b7a',
                            'card': '#ffffff'}),
        content=Content(pages=content_pages),
        assets=Assets(images=[], icons=[], fonts=[]),
        generation_metadata={'page_pattern': {
            'id': 'test', 'home_sections': sections_home,
            'secondary_sections': ['Hero', 'Content']}})


def _run_codegen(artifact):
    engine = CodeGenerationEngine(MagicMock())
    workspace = _ScaffoldWorkspace()
    calls = []

    def gen(op, payload):
        calls.append((op, payload))
        return {'full_content': 'function X() { return <section /> }'}

    runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                              workspace=workspace)
    result = engine.execute(artifact, runtime)
    return result, workspace, calls


# ---------------------------------------------------------------------------
# AssetEngine: deterministic relevance ranking (Phase 47.28)
# ---------------------------------------------------------------------------

def _photo(photo_id, alt, width=1600, height=1000):
    return {
        'photo_id': photo_id,
        'remote_url': 'https://x/%d.jpg' % photo_id,
        'alt': alt,
        'photographer': 'p%d' % photo_id,
        'source_url': 'https://x/%d' % photo_id,
        'width': width,
        'height': height,
        'license': 'Pexels License',
    }


class TestAssetRelevanceRanking(unittest.TestCase):

    def _engine(self):
        return AssetEngine(MagicMock())

    def _artifact_for(self, domain='Restaurant'):
        return WebsiteGenerationArtifact(
            requirements=RequirementModel(domain=domain),
            architecture=ArchitectureModel(component_hierarchy={}),
            component_tree=ComponentTree(nodes=[], dependencies=[]),
            generation_metadata={})

    def test_01_relevant_outranks_irrelevant(self):
        engine = self._engine()
        artifact = self._artifact_for()
        intent = {'role': 'hero', 'query': 'restaurant',
                  'orientation': 'landscape',
                  'context': {'section_type': 'Hero', 'page': 'home',
                              'domain': 'restaurant'}}
        candidates = [
            _photo(1, 'random abstract gradient', 1600, 1000),
            _photo(2, 'warm restaurant interior with diners', 1920, 1080),
            _photo(3, 'a person typing on laptop', 1600, 1000),
        ]
        ranked = engine._rank_stock_candidates(candidates, intent, artifact)
        self.assertEqual(ranked[0]['photo_id'], 2,
                         'restaurant-relevant alt text wins')
        self.assertGreater(ranked[0]['_relevance_score'],
                           ranked[1]['_relevance_score'])

    def test_02_landscape_preferred_for_hero(self):
        engine = self._engine()
        artifact = self._artifact_for()
        intent = {'role': 'hero', 'query': 'restaurant',
                  'orientation': 'landscape',
                  'context': {'section_type': 'Hero', 'page': 'home',
                              'domain': 'restaurant'}}
        # Same alt text; square loses to landscape.
        candidates = [
            _photo(1, 'restaurant dining room', 1200, 1200),
            _photo(2, 'restaurant dining room', 1920, 1080),
        ]
        ranked = engine._rank_stock_candidates(candidates, intent, artifact)
        self.assertEqual(ranked[0]['photo_id'], 2)

    def test_03_ranking_deterministic(self):
        engine = self._engine()
        artifact = self._artifact_for()
        intent = {'role': 'section', 'query': 'menu',
                  'orientation': 'landscape',
                  'context': {'section_type': 'MenuHighlights',
                              'page': 'home', 'domain': 'restaurant'}}
        candidates = [
            _photo(1, 'plated pasta dish'),
            _photo(2, 'plated pasta dish'),
            _photo(3, 'office meeting room'),
        ]
        r1 = engine._rank_stock_candidates(list(candidates), intent, artifact)
        r2 = engine._rank_stock_candidates(list(candidates), intent, artifact)
        self.assertEqual([p['photo_id'] for p in r1],
                         [p['photo_id'] for p in r2],
                         'identical input ranks identically')
        # Equal-score ties break deterministically by photo_id.
        self.assertEqual(r1[0]['photo_id'], r1[1]['photo_id'] - 1)

    def test_04_section_keywords_distinguish_roles(self):
        hero_kw = AssetEngine._section_keywords('Hero')
        menu_kw = AssetEngine._section_keywords('MenuHighlights')
        self.assertIn('hero', hero_kw)
        self.assertIn('banner', hero_kw)
        self.assertIn('food', menu_kw)
        self.assertIn('dish', menu_kw)
        self.assertFalse(hero_kw & menu_kw, 'keyword sets are disjoint')

    def test_05_intents_are_section_aware(self):
        engine = self._engine()
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Restaurant'),
            architecture=ArchitectureModel(component_hierarchy={}),
            component_tree=ComponentTree(nodes=[], dependencies=[]),
            generation_metadata={'page_pattern': {
                'id': 'restaurant',
                'home_sections': ['Hero', 'About', 'MenuHighlights',
                                  'Gallery', 'Testimonial', 'ContactCTA'],
                'secondary_sections': ['Hero', 'Content']}})
        intents = engine._build_stock_intents(
            artifact, ['Hero', 'About', 'MenuHighlights', 'Gallery',
                       'Testimonial', 'ContactCTA'], 'restaurant')
        roles = [i['role'] for i in intents]
        self.assertIn('hero', roles)
        self.assertIn('gallery', roles)
        self.assertIn('section', roles)
        # Section intents carry context with the section type.
        menu_intent = next(
            i for i in intents
            if i['role'] == 'section'
            and i['context']['section_type'] == 'MenuHighlights')
        self.assertIn('restaurant food dishes', menu_intent['query'])

    def test_06_relevance_score_recorded_in_evidence(self):
        engine = self._engine()
        artifact = self._artifact_for()
        intent = {'role': 'hero', 'query': 'restaurant',
                  'orientation': 'landscape',
                  'context': {'section_type': 'Hero', 'page': 'home',
                              'domain': 'restaurant'}}
        candidates = [_photo(1, 'restaurant interior', 1920, 1080)]
        ranked = engine._rank_stock_candidates(candidates, intent, artifact)
        self.assertIn('_relevance_score', ranked[0])


# ---------------------------------------------------------------------------
# Deterministic home Hero (Phase 47.28, ADR-0080)
# ---------------------------------------------------------------------------

HOME_CONTENT = {
    '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
          'sections': [
              {'type': 'Hero', 'semantic_heading': 'Crafted spaces',
               'aria_label': 'h', 'body': 'Hero copy for the studio.'},
              {'type': 'ServicesGrid', 'semantic_heading': 'What we do',
               'aria_label': 's', 'body': 'S.'},
          ]},
    '/detail': {'seo': {'title': 'Detail', 'description': 'd'}, 'metadata': {},
                'sections': [
                    {'type': 'Hero', 'semantic_heading': 'Detail',
                     'aria_label': 'h', 'body': 'Detail hero copy.'},
                    {'type': 'Content', 'semantic_heading': 'How it works',
                     'aria_label': 'c',
                     'body': "Alpha\n\nAlpha body text here."},
                ]},
}


class TestDeterministicHomeHero(unittest.TestCase):

    def test_10_home_hero_deterministic_no_llm(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        code_calls = [op for op, _ in calls if op == 'ai_code_patch']
        self.assertEqual(len(code_calls), 0,
                         'home Hero is deterministic — zero code LLM calls')

    def test_11_home_hero_native_organism(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", home)
        self.assertIn('data-nexora-source="native/Hero"', home)
        self.assertIn("{'Crafted spaces'}", home,
                      'ContentArtifact copy reaches the Hero title')
        self.assertIn("{'Hero copy for the studio.'}", home,
                      'ContentArtifact copy reaches the Hero subtitle')

    def test_12_cta_label_business_aware(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT),
                             branding={'business_name': 'Test Studio',
                                       'services': ['design consultation']})
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn("View work", home,
                      "design service drives 'View work' CTA label")

    def test_13_cta_label_default(self):
        artifact = _artifact('SaaS', 'Metricly',
                             ['Hero', 'FeatureGrid'], dict(HOME_CONTENT),
                             branding={'business_name': 'Metricly',
                                       'services': ['dashboards']})
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn("Get started", home,
                      'default CTA label for non-matching services')

    def test_14_home_hero_missing_copy_falls_back_to_business(self):
        content = dict(HOME_CONTENT)
        content['/'] = {'seo': {'title': 'T', 'description': 'D'},
                        'metadata': {},
                        'sections': [
                            {'type': 'Hero', 'semantic_heading': '',
                             'aria_label': 'h', 'body': ''},
                            {'type': 'ServicesGrid', 'semantic_heading': 'S',
                             'aria_label': 's', 'body': 'S.'}]}
        artifact = _artifact('Agency', 'Fallback Studio',
                             ['Hero', 'ServicesGrid'], content)
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn("{'Fallback Studio'}", home,
                      'business name is the heading fallback')

    def test_15_stock_hero_image_reaches_home_hero(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT),
                             )
        # Simulate a materialized stock hero (AssetEngine path).
        artifact = artifact.evolve(assets=Assets(images=[
            {'id': 'stock_hero', 'format': 'jpg', 'role': 'hero',
             'remote_url': 'https://x/hero.jpg', 'content': None,
             'metadata': {'alt': 'studio workspace', 'ownership': 'pexels'}},
        ], icons=[], fonts=[]))
        from unittest.mock import patch
        from odoo.addons.nexora_studio.services.providers.asset import pexels_provider
        engine = CodeGenerationEngine(MagicMock())
        workspace = _ScaffoldWorkspace()
        with patch.object(pexels_provider, 'download_photo',
                          return_value=b'\xff\xd8fakejpeg'):
            runtime = SimpleNamespace(
                ai=SimpleNamespace(generate=lambda op, p: {}),
                workspace=workspace)
            result = engine.execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn('/images/stock_hero.jpg', home,
                      'stock hero image reaches the deterministic home Hero')
        self.assertIn('studio workspace', home)

    def test_16_manifest_home_hero_deterministic(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        result, _, _ = _run_codegen(artifact)
        manifest = result.metadata['composition_manifest']
        home_sections = manifest['pages']['/']
        hero_record = home_sections[0]
        self.assertEqual(hero_record['type'], 'Hero')
        self.assertEqual(hero_record['mode'], 'deterministic')
        self.assertEqual(hero_record['component'], 'native/Hero')
        self.assertEqual(hero_record['source'], 'native_library')
        # Whole-site composition: no llm mode anywhere.
        modes = [s['mode'] for sections in manifest['pages'].values()
                 for s in sections]
        self.assertNotIn('llm', modes)
        self.assertNotIn('fallback', modes)
        self.assertEqual(result.metadata['llm_composition_pct'], 0)


# ---------------------------------------------------------------------------
# 47.27 structured-content regressions under the deterministic home Hero
# ---------------------------------------------------------------------------

class TestStructuredContentRegressions(unittest.TestCase):

    def test_20_productgrid_from_items_still_works(self):
        content = {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero.'},
                      {'type': 'MenuHighlights',
                       'semantic_heading': 'Our menu',
                       'aria_label': 'm', 'body': 'Dishes follow.',
                       'items': [
                           {'title': 'Tagliatelle', 'price': '€14',
                            'body': 'Hand-rolled pasta.'},
                           {'title': 'Margherita', 'price': '€11',
                            'body': 'Wood-fired pizza.'}]},
                  ]},
            '/detail': HOME_CONTENT['/detail'],
        }
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights'], content)
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn('<ProductGrid data-nexora-source="native/ProductGrid"',
                      home)
        self.assertIn("'€14'", home)
        self.assertIn('Tagliatelle', home)

    def test_21_pricing_faq_from_items_still_works(self):
        content = {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero.'},
                      {'type': 'Pricing', 'semantic_heading': 'Pricing',
                       'aria_label': 'p', 'body': 'b',
                       'items': [{'title': 'Starter', 'price': '$29/mo',
                                  'body': '5 dashboards; email support'}]},
                      {'type': 'FAQ', 'semantic_heading': 'FAQ',
                       'aria_label': 'q', 'body': 'b',
                       'items': [{'question': 'Free trial?',
                                  'answer': 'Yes, 14 days.'}]},
                  ]},
            '/detail': HOME_CONTENT['/detail'],
        }
        artifact = _artifact('SaaS', 'Metricly',
                             ['Hero', 'Pricing', 'FAQ'], content)
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn('<PricingCard', home)
        self.assertIn("'$29/mo'", home)
        self.assertIn('<FAQ', home)
        self.assertIn('Free trial?', home)

    def test_22_secondary_hero_still_native(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        result, workspace, _ = _run_codegen(artifact)
        detail = workspace.files['src/pages/detail.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", detail)
        self.assertIn('data-nexora-source="native/Hero"', detail)

    def test_23_content_sections_deterministic(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        result, workspace, _ = _run_codegen(artifact)
        detail = workspace.files['src/pages/detail.tsx']
        self.assertIn('function ContentSection2', detail)
        self.assertIn("{'How it works'}", detail)
        self.assertIn('Alpha body text here', detail)


if __name__ == '__main__':
    unittest.main(verbosity=2)
