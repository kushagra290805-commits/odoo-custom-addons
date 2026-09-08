# -*- coding: utf-8 -*-
"""Phase 47.27 — structured content contract + deterministic secondary
rendering tests (ADR-0079).

Covers:
  * ContentArtifact item normalization: canonical/natural shapes, aliases,
    bounding, backward compatibility (sections without items unchanged).
  * ContentEngine schema extension (optional items in response_format).
  * Deterministic Content sections: title-line/paragraph blocks + items.
  * ProductGrid composition from structured items (with prices).
  * Pricing/FAQ from structured items (prose parsing as fallback).
  * LLM call count (1 per site: home hero).
  * Composition manifest percentages (deterministic/llm/hybrid/fallback).
  * 47.20C contract regressions (fence, natural shape, fallback).
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


def _artifact(domain, business, sections_home, content_pages):
    from odoo.addons.nexora_studio.services.design.page_patterns import select_pattern
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(
            domain=domain, business_name=business,
            business_category='%s business' % domain,
            branding={'business_name': business,
                      'services': ['service one', 'service two']}),
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
        # A VALID home-hero section (passes 47.23 static validation so the
        # manifest records it as 'llm', not 'fallback').
        import re
        mm = re.search(r'named (\w+)', payload.get('task', ''))
        name = mm.group(1) if mm else 'X'
        return {'full_content':
                'function %s() { return (<section aria-label="hero">'
                '<h1>{"Hero"}</h1><p>{"copy"}</p></section>) }' % name}

    runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                              workspace=workspace)
    result = engine.execute(artifact, runtime)
    return result, workspace, calls


# ---------------------------------------------------------------------------
# ContentArtifact item normalization
# ---------------------------------------------------------------------------

class TestItemNormalization(unittest.TestCase):

    def _normalize(self, raw):
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
            ContentEngine)
        engine = ContentEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Test'))
        return engine._normalize_content_schema(raw, artifact)

    def test_01_canonical_items_preserved(self):
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [
                {"type": "Pricing", "semantic_heading": "P",
                 "body": "b",
                 "items": [{"title": "Starter", "price": "$29",
                            "body": "features"}]},
            ]}}}
        normalized = self._normalize(raw)
        section = normalized['pages']['/']['sections'][0]
        self.assertEqual(section['items'],
                         [{'title': 'Starter', 'price': '$29',
                           'body': 'features'}])

    def test_02_natural_shape_menu(self):
        raw = {"site": {}, "pages": [{
            "slug": "/",
            "sections": [
                {"type": "MenuHighlights",
                 "editable": {"heading": {"value": "Our menu"},
                              "menu": [
                                  {"name": "Pasta", "price": "€12",
                                   "description": "Fresh pasta"},
                                  {"name": "Pizza", "price": "€10"},
                              ]}},
            ]}]}
        normalized = self._normalize(raw)
        section = normalized['pages']['/']['sections'][0]
        self.assertEqual(section['type'], 'MenuHighlights')
        self.assertEqual(section['semantic_heading'], 'Our menu')
        self.assertEqual(len(section['items']), 2)
        self.assertEqual(section['items'][0]['title'], 'Pasta')
        self.assertEqual(section['items'][0]['price'], '€12')
        self.assertEqual(section['items'][0]['body'], 'Fresh pasta')

    def test_03_faqs_and_plans_keys(self):
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [
                {"type": "FAQ", "semantic_heading": "Q",
                 "body": "b", "faqs": [
                     {"question": "Free trial?", "answer": "Yes"},
                 ]},
                {"type": "Pricing", "semantic_heading": "P",
                 "body": "b", "plans": [
                     {"name": "Pro", "cost": "$50",
                      "features": ["a", "b"]},
                 ]},
            ]}}}
        normalized = self._normalize(raw)
        sections = normalized['pages']['/']['sections']
        faq = sections[0]
        self.assertEqual(faq['items'][0]['question'], 'Free trial?')
        self.assertEqual(faq['items'][0]['answer'], 'Yes')
        plan = sections[1]
        self.assertEqual(plan['items'][0]['title'], 'Pro')
        self.assertEqual(plan['items'][0]['price'], '$50')

    def test_04_backward_compatible_no_items(self):
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [
                {"type": "Content", "semantic_heading": "C", "body": "b"},
            ]}}}
        normalized = self._normalize(raw)
        section = normalized['pages']['/']['sections'][0]
        self.assertEqual(section['items'], [])
        self.assertEqual(section['body'], 'b')

    def test_05_items_bounded(self):
        many = [{"title": "Item %d" % i, "body": "x"} for i in range(20)]
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "MenuHighlights", "semantic_heading": "M",
                          "body": "b", "items": many}]}}}
        normalized = self._normalize(raw)
        section = normalized['pages']['/']['sections'][0]
        self.assertEqual(len(section['items']), 8)

    def test_06_47_20c_regressions_intact(self):
        # Fenced content still extracts.
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
            ContentEngine)
        engine = ContentEngine(MagicMock())
        raw = "```json\n" + json.dumps({"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Content", "semantic_heading": "C",
                          "body": "b"}]}}}) + "\n```"
        parsed = engine._extract_json_payload(raw)
        self.assertIn('pages', parsed)
        # Natural list shape still normalizes.
        natural = {"site": {"business_name": "B"}, "pages": [{
            "slug": "/",
            "sections": [{"type": "Hero",
                          "editable": {"headline": {"value": "H"},
                                       "subheadline": {"value": "S"}}}]}]}
        normalized = self._normalize(natural)
        self.assertEqual(normalized['pages']['/']['seo']['title'], 'H')


# ---------------------------------------------------------------------------
# Deterministic secondary Content + structured items → components
# ---------------------------------------------------------------------------

DETAIL_CONTENT = {
    '/detail': {'seo': {'title': 'Detail', 'description': 'd'}, 'metadata': {},
                'sections': [
                    {'type': 'Hero', 'semantic_heading': 'Detail',
                     'aria_label': 'h', 'body': 'Detail hero copy.'},
                    {'type': 'Content', 'semantic_heading': 'How it works',
                     'body': "Alpha\n\nAlpha body text here.\n\nBeta\n\nBeta body text here."},
                ]},
}


class TestDeterministicSecondary(unittest.TestCase):

    def test_10_llm_call_count_one_per_site(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid', 'ContactCTA'],
                             {**DETAIL_CONTENT,
                              '/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'ServicesGrid', 'semantic_heading': 'S',
                                         'aria_label': 's', 'body': 'S.'},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]}})
        result, workspace, calls = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        # Phase 47.28: the home hero is deterministic too — ZERO code LLM
        # calls; generate_content (ContentEngine) is the only site LLM call.
        ops = [op for op, _ in calls]
        self.assertEqual(ops.count('ai_code_patch'), 0)

    def test_11_deterministic_content_cards(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid', 'ContactCTA'],
                             {**DETAIL_CONTENT,
                              '/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'ServicesGrid', 'semantic_heading': 'S',
                                         'aria_label': 's', 'body': 'S.'},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]}})
        result, workspace, _ = _run_codegen(artifact)
        detail = workspace.files['src/pages/detail.tsx']
        self.assertIn('function ContentSection2', detail)
        self.assertIn('<article', detail, 'content renders themed cards')
        # Title-line + paragraph blocks parsed.
        self.assertIn('Alpha', detail)
        self.assertIn('Alpha body text here', detail)
        self.assertIn('Beta body text here', detail)
        # Copy comes from the ContentArtifact (no LLM invention).
        self.assertIn('How it works', detail)

    def test_12_deterministic_content_from_items(self):
        detail = dict(DETAIL_CONTENT)
        detail['/detail'] = {
            'seo': {'title': 'D', 'description': 'd'}, 'metadata': {},
            'sections': [
                {'type': 'Hero', 'semantic_heading': 'Detail',
                 'aria_label': 'h', 'body': 'Hero.'},
                {'type': 'Content', 'semantic_heading': 'Offerings',
                 'body': 'b',
                 'items': [{'title': 'First', 'body': 'First description.'},
                           {'title': 'Second', 'body': 'Second description.'}]},
            ]}
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ContactCTA'],
                             {**detail,
                              '/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]}})
        result, workspace, _ = _run_codegen(artifact)
        detail_page = workspace.files['src/pages/detail.tsx']
        self.assertIn('First', detail_page)
        self.assertIn('First description.', detail_page)
        self.assertIn('Second description.', detail_page)

    def test_13_manifest_percentages(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid', 'ContactCTA'],
                             {**DETAIL_CONTENT,
                              '/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'ServicesGrid', 'semantic_heading': 'S',
                                         'aria_label': 's', 'body': 'S.'},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]}})
        result, _, _ = _run_codegen(artifact)
        meta = result.metadata
        self.assertIn('deterministic_composition_pct', meta)
        self.assertIn('llm_composition_pct', meta)
        self.assertIn('hybrid_composition_pct', meta)
        self.assertIn('fallback_composition_pct', meta)
        # Phase 47.28: 5 sections, ALL deterministic (home hero included):
        # home Hero + ServicesGrid + ContactCTA + detail hero + detail
        # Content.
        self.assertEqual(meta['llm_composition_pct'], 0)
        self.assertEqual(meta['deterministic_composition_pct'], 100)

    def test_14_content_unparseable_body_honest_paragraph(self):
        detail = dict(DETAIL_CONTENT)
        detail['/detail'] = {
            'seo': {'title': 'D', 'description': 'd'}, 'metadata': {},
            'sections': [
                {'type': 'Hero', 'semantic_heading': 'D',
                 'aria_label': 'h', 'body': 'H.'},
                {'type': 'Content', 'semantic_heading': 'C',
                 'body': 'Just one long unstructured paragraph of copy.'},
            ]}
        artifact = _artifact('Agency', 'Test Studio', ['Hero', 'ContactCTA'],
                             {**detail,
                              '/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]}})
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        detail_page = workspace.files['src/pages/detail.tsx']
        self.assertIn('Just one long unstructured paragraph', detail_page)


class TestStructuredItemComposition(unittest.TestCase):

    def _restaurant_artifact(self, with_items):
        section = {'type': 'MenuHighlights', 'semantic_heading': 'Our menu',
                   'aria_label': 'm', 'body': 'Dishes follow.'}
        if with_items:
            section['items'] = [
                {'title': 'Tagliatelle', 'price': '€14',
                 'body': 'Hand-rolled pasta with ragù.'},
                {'title': 'Margherita', 'price': '€11',
                 'body': 'Wood-fired pizza.'},
            ]
        return _artifact('Restaurant', 'Trattoria',
                         ['Hero', 'MenuHighlights', 'ContactCTA'],
                         {'/': {'seo': {'title': 'T', 'description': 'D'},
                                'metadata': {},
                                'sections': [
                                    {'type': 'Hero', 'semantic_heading': 'H',
                                     'aria_label': 'h', 'body': 'Hero.'},
                                    section,
                                    {'type': 'ContactCTA', 'semantic_heading': 'C',
                                     'aria_label': 'c', 'body': 'C.'},
                                ]},
                          **DETAIL_CONTENT})

    def test_20_productgrid_from_structured_items(self):
        artifact = self._restaurant_artifact(with_items=True)
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn("import ProductGrid from '../components/ProductGrid.jsx'", home)
        self.assertIn('<ProductGrid data-nexora-source="native/ProductGrid"', home)
        self.assertIn('const products = [', home)
        self.assertIn("'€14'", home)
        self.assertIn('Tagliatelle', home)

    def test_21_menu_without_items_falls_back(self):
        artifact = self._restaurant_artifact(with_items=False)
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        self.assertNotIn('<ProductGrid', home)
        self.assertIn('aria-label="featured menu items"', home)

    def test_22_pricing_from_structured_items(self):
        artifact = _artifact('SaaS', 'Metricly',
                             ['Hero', 'Pricing', 'FAQ', 'ContactCTA'],
                             {'/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'Pricing', 'semantic_heading': 'Pricing',
                                         'aria_label': 'p', 'body': 'b',
                                         'items': [
                                             {'title': 'Starter', 'price': '$29/mo',
                                              'body': '5 dashboards; email support'},
                                             {'title': 'Growth', 'price': '$79/mo',
                                              'body': 'unlimited; API'},
                                         ]},
                                        {'type': 'FAQ', 'semantic_heading': 'FAQ',
                                         'aria_label': 'q', 'body': 'b',
                                         'items': [
                                             {'question': 'Free trial?',
                                              'answer': 'Yes, 14 days.'},
                                         ]},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]},
                              **DETAIL_CONTENT})
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn('<PricingCard', home)
        self.assertIn("'$29/mo'", home)
        self.assertIn('email support', home,
                      'feature list split from the item body')
        self.assertIn('<FAQ', home)
        self.assertIn('Free trial?', home)
        self.assertIn('Yes, 14 days.', home)

    def test_23_pricing_prose_fallback_still_works(self):
        artifact = _artifact('SaaS', 'Metricly',
                             ['Hero', 'Pricing', 'ContactCTA'],
                             {'/': {'seo': {'title': 'T', 'description': 'D'},
                                    'metadata': {},
                                    'sections': [
                                        {'type': 'Hero', 'semantic_heading': 'H',
                                         'aria_label': 'h', 'body': 'Hero.'},
                                        {'type': 'Pricing', 'semantic_heading': 'Pricing',
                                         'aria_label': 'p',
                                         'body': 'Starter — $29/mo\nfeature one\n\n'
                                                 'Growth — $79/mo\nfeature two'},
                                        {'type': 'ContactCTA', 'semantic_heading': 'C',
                                         'aria_label': 'c', 'body': 'C.'},
                                    ]},
                              **DETAIL_CONTENT})
        result, workspace, _ = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn('<PricingCard', home)
        self.assertIn('$29/mo', home)

    def test_24_secondary_hero_still_native(self):
        artifact = self._restaurant_artifact(with_items=True)
        result, workspace, _ = _run_codegen(artifact)
        detail = workspace.files['src/pages/detail.tsx']
        self.assertIn("import Hero from '../components/Hero.jsx'", detail)
        self.assertIn('data-nexora-source="native/Hero"', detail)


# ---------------------------------------------------------------------------
# ContentEngine boundary regressions
# ---------------------------------------------------------------------------

class TestContentEngineBoundary(unittest.TestCase):

    def test_30_no_duplicate_generate_content(self):
        # The single content call remains the semantic owner (schema
        # extension present, prompt carries the items hint).
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
            _CONTENT_SCHEMA_PROMPT)
        self.assertIn('items', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('Pricing', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('MenuHighlights', _CONTENT_SCHEMA_PROMPT)

    def test_31_fallback_contract_unchanged(self):
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
            ContentEngine)
        engine = ContentEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Test'),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/',
                         'sections': ['Hero', 'Content']}}))
        runtime = SimpleNamespace(
            ai=SimpleNamespace(generate=lambda op, p: {'analysis': 'not json'}),
            env=None)
        result = engine.execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.metadata.get('content_fallback_reason'),
                         'ai_content_schema_validation_failed')
        pages = result.artifact.content.pages
        self.assertIn('/', pages)
        self.assertIn('items', pages['/']['sections'][0])
        self.assertEqual(pages['/']['sections'][0]['items'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
