# -*- coding: utf-8 -*-
"""Phase 47.29 — client quality hardening tests.

Covers:
  * generate_content contract: stronger structured-output prompt, natural
    malformed item shapes (nested objects, object containers, priced
    strings, list-valued fields), prose-block repair into items.
  * Image-to-section assignment: per-section entry ids, deterministic
    uniqueness across sections, subject-aware queries, renderer per-
    section lookup with legacy fallback.
  * Native Hero polish: deterministic variant (split with imagery /
    centered without), badge/eyebrow from brief, bounded subtitle.
  * MenuHighlights prose fallback composing ProductGrid.
  * Composition manifest surfacing: bounded EngineCompleted event
    metadata and the generation.completed runtime-event summary.
"""
import json
import os
import shutil
import sys
import tempfile
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

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel, ComponentTree, Content, RequirementModel, Theme,
    WebsiteGenerationArtifact, Assets)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine)
from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
    ContentEngine)
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
            business_category=kwargs.get(
                'business_category', '%s business' % domain),
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
# generate_content contract: prompt + malformed-shape normalization
# ---------------------------------------------------------------------------

class TestContentContractHardening(unittest.TestCase):

    def _normalize(self, raw):
        engine = ContentEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Test'))
        return engine._normalize_content_schema(raw, artifact)

    def test_01_prompt_requires_structured_items(self):
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
            _CONTENT_SCHEMA_PROMPT)
        self.assertIn('REQUIRED', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('"question"', _CONTENT_SCHEMA_PROMPT)
        self.assertIn('"answer"', _CONTENT_SCHEMA_PROMPT)
        # A concrete item example rides the prompt (few-shot anchoring).
        self.assertIn('"title": "Starter"', _CONTENT_SCHEMA_PROMPT)

    def test_02_nested_natural_plan_object(self):
        # Weak-model shape: {"plan": {"name": ..., "price": ...}}.
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Pricing", "semantic_heading": "P",
                          "body": "b",
                          "items": [{"plan": {"name": "Pro",
                                              "price": "$50"}}]}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(section['items'][0]['title'], 'Pro')
        self.assertEqual(section['items'][0]['price'], '$50')

    def test_03_object_shaped_container(self):
        # Weak-model shape: items as an object keyed by index.
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "MenuHighlights", "semantic_heading": "M",
                          "body": "b",
                          "items": {"0": {"name": "Pasta", "price": "€12"},
                                    "1": {"name": "Pizza", "price": "€10"}}}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(len(section['items']), 2)
        self.assertEqual(section['items'][0]['title'], 'Pasta')

    def test_04_priced_string_items(self):
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Pricing", "semantic_heading": "P",
                          "body": "b",
                          "items": ["Starter - $29/mo", "Pro: $79/mo",
                                     "Just a title"]}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        items = section['items']
        self.assertEqual(items[0], {'title': 'Starter', 'price': '$29/mo'})
        self.assertEqual(items[1], {'title': 'Pro', 'price': '$79/mo'})
        # Non-priced prose stays a plain title (no false positive).
        self.assertEqual(items[2], {'title': 'Just a title', 'body': ''})

    def test_05_list_valued_feature_field_flattens(self):
        item = {"name": "Pro", "price": "$50",
                "features": ["5 dashboards", "email support"]}
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Pricing", "semantic_heading": "P",
                          "body": "b", "items": [item]}]}}
        }
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(section['items'][0]['body'],
                         '5 dashboards; email support')


    def test_10_pricing_prose_blocks_become_items(self):
        # The prompt's instructed prose fallback format normalizes back
        # into structured items at the ContentArtifact boundary.
        body = ("Simple, transparent pricing.\n\n"
                "Starter - $29/mo\n5 dashboards\nemail support\n\n"
                "Pro - $79/mo\nUnlimited dashboards\npriority support")
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Pricing", "semantic_heading": "Pricing",
                          "body": body}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(section['items'][0]['title'], 'Starter')
        self.assertEqual(section['items'][0]['price'], '$29/mo')
        self.assertIn('5 dashboards', section['items'][0]['body'])
        self.assertEqual(section['items'][1]['title'], 'Pro')

    def test_11_faq_prose_blocks_become_items(self):
        body = ("Answers to common questions.\n\n"
                "Is there a free trial?\nYes, 14 days, no card needed.\n\n"
                "Can I cancel anytime?\nYes — monthly plans cancel instantly.")
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "FAQ", "semantic_heading": "FAQ",
                          "body": body}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(section['items'][0]['question'],
                         'Is there a free trial?')
        self.assertIn('14 days', section['items'][0]['answer'])
        self.assertEqual(section['items'][1]['question'],
                         'Can I cancel anytime?')

    def test_12_menu_prose_blocks_become_items(self):
        body = ("Our favourite dishes this season.\n\n"
                "Tagliatelle - €14\nHand-rolled pasta with ragù.\n\n"
                "Margherita - €11\nWood-fired pizza with basil.")
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "MenuHighlights", "semantic_heading":
                          "Our menu", "body": body}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(section['items'][0]['title'], 'Tagliatelle')
        self.assertEqual(section['items'][0]['price'], '€14')
        self.assertIn('ragù', section['items'][0]['body'])

    def test_13_prose_without_grammar_gets_no_items(self):
        # Ordinary narrative body (no priced blocks, no questions) must
        # NOT be misparsed into items.
        body = ("We are a small studio doing careful work.\n\n"
                "Our approach - research first, then design")
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Content", "semantic_heading": "About",
                          "body": body},
                         {"type": "Pricing", "semantic_heading": "P",
                          "body": "Pricing is simple - just ask us"}]}}}
        sections = self._normalize(raw)['pages']['/']['sections']
        self.assertEqual(sections[0]['items'], [])
        # 'just ask us' is not price-like: no false-positive pricing item.
        self.assertEqual(sections[1]['items'], [])

    def test_14_explicit_items_not_overridden_by_prose(self):
        body = "Starter - $29/mo\nfeature one"
        raw = {"pages": {"/": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Pricing", "semantic_heading": "P",
                          "body": body,
                          "items": [{"title": "Explicit",
                                     "price": "$10"}]}]}}}
        section = self._normalize(raw)['pages']['/']['sections'][0]
        self.assertEqual(section['items'][0]['title'], 'Explicit')

    def test_16_bracket_repair_mismatched_closers(self):
        # The observed weak-model failure class: "pages" opened as an
        # object but closed with list brackets / stray closers.
        engine = ContentEngine(MagicMock())
        broken = ('```json\n{"pages": {"/home": {"seo": {"title": "T", '
                  '"description": "D"}, "sections": [{"type": "Content", '
                  '"semantic_heading": "C", "body": "b"}]}]}\n```')
        payload = engine._extract_json_payload(broken)
        self.assertIn('pages', payload)
        self.assertIn('/home', payload['pages'])

    def test_17_bracket_repair_truncation(self):
        engine = ContentEngine(MagicMock())
        truncated = '{"pages": {"/": {"seo": {"title": "T", ' \
                    '"description": "D"'
        payload = engine._extract_json_payload(truncated)
        self.assertEqual(payload.get('pages', {}).get('/', {})
                         .get('seo', {}).get('title'), 'T')

    def test_18_bracket_repair_never_loses_valid_json(self):
        engine = ContentEngine(MagicMock())
        valid = '{"pages": {"/": {"a": [1, 2], "b": "x]y}"}}}'
        self.assertEqual(engine._extract_json_payload(valid)
                         ['pages']['/']['a'], [1, 2])

    def test_19_page_key_remap_to_expected_routes(self):
        # Weak models ignore the page map keys ("/home" instead of "/").
        engine = ContentEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Restaurant'),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/',
                         'sections': ['Hero', 'Content']},
                'menu': {'type': 'page', 'path': '/menu',
                         'sections': ['Hero', 'Content']},
            }))
        raw = {"pages": {"/home": {
            "seo": {"title": "T", "description": "D"},
            "sections": [{"type": "Content", "semantic_heading": "C",
                          "body": "b"}]}}}
        normalized = engine._normalize_content_schema(raw, artifact)
        self.assertIn('/', normalized['pages'])
        self.assertNotIn('/home', normalized['pages'])
        # Case/slash drift on a named route remaps too.
        raw2 = {"pages": {"/Menu/": {
            "seo": {"title": "M", "description": "d"},
            "sections": [{"type": "Content", "semantic_heading": "C",
                          "body": "b"}]}}}
        normalized2 = engine._normalize_content_schema(raw2, artifact)
        self.assertIn('/menu', normalized2['pages'])
        # Unmatched keys: a single collapsed page lands on home; multiple
        # unmatched pages are preserved untouched (no guessing).
        raw3 = {"pages": {
            "/unknown-a": {"seo": {"title": "U", "description": "d"},
                           "sections": []},
            "/unknown-b": {"seo": {"title": "V", "description": "d"},
                           "sections": []}}}
        normalized3 = engine._normalize_content_schema(raw3, artifact)
        self.assertIn('/unknown-a', normalized3['pages'])
        self.assertIn('/unknown-b', normalized3['pages'])

    def test_15_structured_items_evidence_in_metadata(self):
        engine = ContentEngine(MagicMock())
        captured = {}

        def gen(op, payload):
            captured.update(payload)
            return {'analysis': json.dumps({"pages": {"/": {
                "seo": {"title": "T", "description": "D"},
                "sections": [
                    {"type": "Pricing", "semantic_heading": "P", "body": "b",
                     "items": [{"title": "A", "price": "$1"}]},
                    {"type": "FAQ", "semantic_heading": "F", "body": "b",
                     "items": [{"question": "Q?", "answer": "A"}]}]}}})}
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Test'),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/',
                         'sections': ['Hero', 'Pricing', 'FAQ']}}),
            component_tree=ComponentTree(nodes=[], dependencies=[]))
        runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen))
        result = engine.execute(artifact, runtime)
        self.assertTrue(result.success)
        self.assertEqual(result.metadata['content_structured_items'], 2)
        # The structured-item instructions reach the actual prompt.
        self.assertIn('REQUIRED', captured['prompt'])


# ---------------------------------------------------------------------------
# Image-to-section assignment
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


class TestImageSectionAssignment(unittest.TestCase):

    def _collect(self, sections, subject='restaurant'):
        engine = AssetEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(
                domain='Restaurant', business_category='restaurant'),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/', 'sections': sections}}),
            component_tree=ComponentTree(nodes=[], dependencies=[]),
            generation_metadata={'page_pattern': {
                'id': 'restaurant', 'home_sections': sections,
                'secondary_sections': ['Hero', 'Content']}})
        counter = {'n': 0}

        def fake_search(env, query, orientation='landscape', per_page=8):
            # Distinct photos per query so uniqueness is observable.
            base = counter['n'] * 10
            counter['n'] += 1
            return [_photo(base + i, '%s %s' % (query, i))
                    for i in range(per_page)], None

        from odoo.addons.nexora_studio.services.providers.asset import (
            pexels_provider)
        runtime = SimpleNamespace(env=None)
        with patch.object(pexels_provider, 'is_configured',
                          return_value=True), \
                patch.object(pexels_provider, 'search_photos', fake_search), \
                patch.object(pexels_provider, 'cache_hits', 0):
            return engine._collect_stock_photos(artifact, runtime)

    def test_20_per_section_entry_ids(self):
        entries, evidence = self._collect(
            ['Hero', 'About', 'MenuHighlights', 'Testimonial'])
        ids = {e['id'] for e in entries}
        self.assertIn('stock_hero', ids)
        self.assertIn('stock_section_about', ids)
        self.assertIn('stock_section_menuhighlights', ids)
        self.assertIn('stock_section_testimonial', ids)
        # Section evidence records the section type.
        section_ev = [p for p in evidence['photos'] if p['role'] == 'section']
        self.assertTrue(all(p.get('section_type') for p in section_ev))

    def test_21_unique_images_across_sections(self):
        entries, _ = self._collect(
            ['Hero', 'About', 'MenuHighlights', 'ServicesGrid',
             'Testimonial', 'ContactCTA'])
        urls = [e['remote_url'] for e in entries]
        self.assertEqual(len(urls), len(set(urls)),
                         'no image is assigned twice')
        # Every section type keeps its own (distinct) image.
        section_ids = [e['id'] for e in entries
                       if e['id'].startswith('stock_section_')]
        self.assertEqual(len(section_ids), 5)

    def test_22_subject_aware_section_queries(self):
        engine = AssetEngine(MagicMock())
        intents = engine._build_stock_intents(
            WebsiteGenerationArtifact(
                requirements=RequirementModel(domain='Restaurant')),
            ['Hero', 'About', 'MenuHighlights'], 'restaurant')
        menu = next(i for i in intents if i['role'] == 'section'
                    and i['context']['section_type'] == 'MenuHighlights')
        about = next(i for i in intents if i['role'] == 'section'
                     and i['context']['section_type'] == 'About')
        self.assertIn('restaurant food dishes', menu['query'])
        self.assertIn('restaurant', about['query'])

    def test_23_section_image_lookup_with_legacy_fallback(self):
        stock = {
            'stock_section_about': {'path': '/images/about.jpg',
                                    'alt': 'about'},
            'stock_section': {'path': '/images/generic.jpg', 'alt': 'g'},
        }
        self.assertEqual(
            CodeGenerationEngine._section_image(stock, 'About')['path'],
            '/images/about.jpg')
        self.assertEqual(
            CodeGenerationEngine._section_image(stock, 'ServicesGrid')['path'],
            '/images/generic.jpg')
        self.assertIsNone(CodeGenerationEngine._section_image({}, 'About'))

    def test_24_distinct_images_reach_distinct_sections(self):
        content = {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero.'},
                      {'type': 'About', 'semantic_heading': 'Our story',
                       'aria_label': 'a', 'body': 'Story.'},
                      {'type': 'ServicesGrid', 'semantic_heading': 'Work',
                       'aria_label': 's', 'body': 'Work.'},
                  ]},
            '/detail': {'seo': {'title': 'D', 'description': 'd'},
                        'metadata': {},
                        'sections': [
                            {'type': 'Hero', 'semantic_heading': 'DH',
                             'aria_label': 'h', 'body': 'DH.'},
                            {'type': 'Content', 'semantic_heading': 'C',
                             'aria_label': 'c', 'body': 'C.'}]},
        }
        artifact = _artifact('Agency', 'Studio',
                             ['Hero', 'About', 'ServicesGrid'], content)
        # Simulate materialized per-section stock images (AssetEngine path).
        from odoo.addons.nexora_studio.services.providers.asset import (
            pexels_provider)
        engine = CodeGenerationEngine(MagicMock())
        workspace = _ScaffoldWorkspace()
        artifact = artifact.evolve(assets=Assets(images=[
            {'id': 'stock_section_about', 'format': 'jpg', 'role': 'section',
             'section_type': 'About', 'remote_url': 'https://x/a.jpg',
             'content': None,
             'metadata': {'alt': 'team at table', 'ownership': 'pexels'}},
            {'id': 'stock_section_servicesgrid', 'format': 'jpg',
             'role': 'section', 'section_type': 'ServicesGrid',
             'remote_url': 'https://x/s.jpg', 'content': None,
             'metadata': {'alt': 'studio workspace', 'ownership': 'pexels'}},
        ], icons=[], fonts=[]))
        with patch.object(pexels_provider, 'download_photo',
                          return_value=b'\xff\xd8fakejpeg'):
            runtime = SimpleNamespace(
                ai=SimpleNamespace(generate=lambda op, p: {}),
                workspace=workspace)
            result = engine.execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        home = workspace.files['src/pages/index.tsx']
        self.assertIn('/images/stock_section_about.jpg', home)
        self.assertIn('/images/stock_section_servicesgrid.jpg', home)
        # Per-section assignment: no repeated identical src in About AND
        # ServicesGrid image blocks.
        self.assertNotEqual(
            home.count('/images/stock_section_about.jpg'), 0)
        self.assertIn('team at table', home)
        self.assertIn('studio workspace', home)


# ---------------------------------------------------------------------------
# Native Hero polish
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
                     'aria_label': 'c', 'body': "Alpha\n\nAlpha body."},
                ]},
}


class TestHeroPolish(unittest.TestCase):

    def _hero(self, artifact, hero_display, content=HOME_CONTENT):
        engine = CodeGenerationEngine(MagicMock())
        return engine._build_deterministic_home_hero(
            'HeroSection1', artifact, content['/']['sections'],
            hero_display, ['/', '/detail'], SimpleNamespace(
                workspace=_ScaffoldWorkspace()))

    def test_30_split_variant_with_image(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        code, imports, mode = self._hero(
            artifact, {'path': '/images/stock_hero.jpg', 'alt': 'workspace'})
        self.assertEqual(mode, 'deterministic')
        self.assertIn('variant="split"', code)
        self.assertIn('/images/stock_hero.jpg', code)

    def test_31_centered_variant_without_image(self):
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], dict(HOME_CONTENT))
        code, _, mode = self._hero(artifact, None)
        self.assertIn('variant="centered"', code)
        self.assertNotIn('variant="split"', code)

    def test_32_badge_from_business_category(self):
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights'], dict(HOME_CONTENT),
                             business_category='Restaurant business')
        code, _, _ = self._hero(artifact, None)
        self.assertIn("badge={'Restaurant'}", code)

    def test_33_badge_bounded_and_cleaned(self):
        self.assertEqual(CodeGenerationEngine._hero_badge(_artifact(
            'SaaS', 'M', ['Hero'], dict(HOME_CONTENT))), 'SaaS')
        self.assertEqual(CodeGenerationEngine._hero_badge(
            WebsiteGenerationArtifact(
                requirements=RequirementModel(
                    domain='X', business_category='a' * 60))), 'a' * 40)
        # Empty category falls back to the domain signal.
        self.assertEqual(CodeGenerationEngine._hero_badge(
            WebsiteGenerationArtifact(
                requirements=RequirementModel(domain='X',
                                              business_category=''))), 'X')
        self.assertEqual(CodeGenerationEngine._hero_badge(
            WebsiteGenerationArtifact(
                requirements=RequirementModel(domain='',
                                              business_category=''))), '')
        self.assertEqual(CodeGenerationEngine._hero_badge(None), '')

    def test_34_subtitle_bounded_200(self):
        content = dict(HOME_CONTENT)
        content['/'] = {'seo': {'title': 'T', 'description': 'D'},
                        'metadata': {},
                        'sections': [
                            {'type': 'Hero', 'semantic_heading': 'H',
                             'aria_label': 'h', 'body': 'x' * 500},
                            {'type': 'ServicesGrid', 'semantic_heading': 'S',
                             'aria_label': 's', 'body': 'S.'}]}
        artifact = _artifact('Agency', 'Test Studio',
                             ['Hero', 'ServicesGrid'], content)
        engine = CodeGenerationEngine(MagicMock())
        code, _, _ = engine._build_deterministic_home_hero(
            'HeroSection1', artifact, content['/']['sections'], None,
            ['/', '/detail'], SimpleNamespace(workspace=_ScaffoldWorkspace()))
        self.assertIn('x' * 200, code)
        self.assertNotIn('x' * 201, code)

    def test_35_secondary_hero_backward_compatible_call(self):
        # The pre-47.29 positional call signature still works (artifact
        # optional; no badge then).
        engine = CodeGenerationEngine(MagicMock())
        code, imports, mode = engine._build_secondary_hero(
            'Hero', 'HeroSection1', HOME_CONTENT['/detail']['sections'], 0,
            {'path': '/images/stock_hero.jpg', 'alt': 'a'},
            ['/', '/detail'], SimpleNamespace(workspace=_ScaffoldWorkspace()))
        self.assertEqual(mode, 'deterministic')
        self.assertIn('variant="split"', code)

    def test_36_secondary_hero_badge_with_artifact(self):
        engine = CodeGenerationEngine(MagicMock())
        artifact = _artifact('SaaS', 'Metricly', ['Hero'],
                             dict(HOME_CONTENT))
        code, _, _ = engine._build_secondary_hero(
            'Hero', 'HeroSection1', HOME_CONTENT['/detail']['sections'], 0,
            None, ['/', '/detail'],
            SimpleNamespace(workspace=_ScaffoldWorkspace()),
            artifact=artifact)
        self.assertIn("badge={'SaaS'}", code)
        self.assertIn('variant="centered"', code)


# ---------------------------------------------------------------------------
# MenuHighlights prose fallback (codegen-level robustness)
# ---------------------------------------------------------------------------

class TestMenuProseFallback(unittest.TestCase):

    def test_40_menu_body_blocks_compose_product_grid(self):
        content = {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero.'},
                      {'type': 'MenuHighlights',
                       'semantic_heading': 'Our menu',
                       'aria_label': 'm',
                       'body': ("Seasonal favourites.\n\n"
                                "Tagliatelle - €14\nHand-rolled pasta.\n\n"
                                "Margherita - €11\nWood-fired pizza.")}]},
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
        self.assertIn('Margherita', home)

    def test_41_menu_non_priced_body_stays_off_product_grid(self):
        content = {
            '/': {'seo': {'title': 'T', 'description': 'D'}, 'metadata': {},
                  'sections': [
                      {'type': 'Hero', 'semantic_heading': 'H',
                       'aria_label': 'h', 'body': 'Hero.'},
                      {'type': 'MenuHighlights',
                       'semantic_heading': 'Our menu',
                       'aria_label': 'm',
                       'body': 'Just a narrative paragraph about food.'}]},
            '/detail': HOME_CONTENT['/detail'],
        }
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights'], content)
        result, workspace, _ = _run_codegen(artifact)
        home = workspace.files['src/pages/index.tsx']
        self.assertNotIn('<ProductGrid', home)


# ---------------------------------------------------------------------------
# Composition manifest surfacing
# ---------------------------------------------------------------------------

class TestCompositionManifestSurfacing(unittest.TestCase):

    def test_50_bounded_event_metadata(self):
        from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import (
            _bounded_event_metadata)
        big = {
            'a': 'x' * 500,
            'b': [i for i in range(40)],
            'c': {'k%d' % i: i for i in range(40)},
            'd': {'deep': {'deeper': {'deepest': {'nope': 1}}}},
            'e': 5,
        }
        out = _bounded_event_metadata(big)
        self.assertEqual(len(out['a']), 240)
        self.assertEqual(len(out['b']), 12)
        self.assertEqual(len(out['c']), 24)
        self.assertEqual(out['e'], 5)
        # Depth 3: content beyond the cap resolves to None leaves.
        self.assertIsNone(out['d']['deep']['deeper']['deepest'])

    def test_51_engine_completed_event_carries_engine_result(self):
        from odoo.addons.nexora_studio.services.generation.core.generation_context import (
            GenerationContext, GenerationState)
        from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import (
            GenerationStateManager)
        from odoo.addons.nexora_studio.services.generation.pipeline.website_generation_pipeline import (
            WebsiteGenerationPipeline)
        from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import (
            PipelineEventBus)
        from odoo.addons.nexora_studio.services.generation.engines.base_engine import (
            EngineExecutionResult)

        captured = []

        class CaptureSubscriber:
            def handle(self, event):
                captured.append(event)

        class FakeEngine:
            def __init__(self, orchestrator):
                self.__class__.called = 0

            def execute(self, artifact, runtime):
                return EngineExecutionResult(
                    success=True, artifact=artifact,
                    metadata={'composition_manifest': {
                        'pattern': 'saas_product',
                        'pages': {'/': [{'type': 'Hero',
                                         'mode': 'deterministic',
                                         'component': 'native/Hero',
                                         'source': 'native_library'}]},
                    }, 'deterministic_composition_pct': 100},
                    error=None)

        bus = PipelineEventBus()
        bus.subscribe(CaptureSubscriber(), priority=99)
        pipeline = WebsiteGenerationPipeline(None, GenerationStateManager(), bus)
        pipeline.registry = {
            GenerationState.PENDING: (FakeEngine(None),
                                      GenerationState.DEPLOYMENT_READY),
        }
        context = GenerationContext(context_id='t4729')
        result = pipeline.run(context, runtime=None)
        self.assertEqual(result.state.name, 'COMPLETED')
        completed = [e for e in captured
                     if e.event_type == 'EngineCompleted']
        self.assertEqual(len(completed), 1)
        engine_result = completed[0].metadata.get('engine_result')
        self.assertIsNotNone(engine_result)
        self.assertEqual(engine_result['composition_manifest']['pattern'],
                         'saas_product')
        self.assertEqual(engine_result['deterministic_composition_pct'], 100)

    def test_52_composition_summary_text(self):
        from odoo.addons.nexora_studio.services.builder_session_service import (
            _composition_summary)
        metadata = {
            'composition_manifest': {
                'pattern': 'restaurant',
                'pages': {
                    '/': [{'type': 'Hero', 'mode': 'deterministic',
                           'component': 'native/Hero'},
                          {'type': 'MenuHighlights', 'mode': 'deterministic',
                           'component': 'native/ProductGrid'}],
                    '/menu': [{'type': 'Hero', 'mode': 'deterministic',
                               'component': 'native/Hero'}],
                },
            },
            'deterministic_composition_pct': 86,
            'llm_composition_pct': 14,
            'content_structured_items': 5,
            'stock_images': {'photos': [
                {'role': 'hero'}, {'role': 'section'},
                {'role': 'section'}, {'role': 'gallery'}]},
        }
        text = _composition_summary(metadata)
        self.assertIn('Page pattern: restaurant', text)
        self.assertIn('native/Hero(deterministic)', text)
        self.assertIn('Deterministic composition: 86%', text)
        self.assertIn('Llm composition: 14%', text)
        self.assertIn('Structured content items: 5', text)
        self.assertIn('Stock imagery: 4 photo(s)', text)
        # Degenerate metadata degrades gracefully.
        self.assertEqual(_composition_summary({}), 'Generation completed.')
        self.assertEqual(_composition_summary(None), 'Generation completed.')


# ---------------------------------------------------------------------------
# Service-level: the composition summary lands in the runtime-event
# timeline through the EXISTING evidence path (no new model/fields).
# ---------------------------------------------------------------------------

class TestCompositionSummaryEvent(unittest.TestCase):

    def test_60_run_generation_emits_composition_event(self):
        from odoo.modules.registry import Registry
        from odoo.addons.nexora_studio.services.generation.core.generation_context import (
            GenerationContext, GenerationState)

        reg = Registry.new('nexora_studio')
        cr = reg.cursor()
        try:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            workspace_path = tempfile.mkdtemp(prefix='p4729-manifest-')
            cr.execute('SAVEPOINT p4729')
            try:
                config_rec = env['nexora.builder_configuration'].create(
                    {'name': 'P4729 Manifest Surface'})
                session = env['nexora.builder_session'].create({
                    'name': 'P4729 Manifest Surface',
                    'builder_configuration_id': config_rec.id,
                    'project_name': 'P4729 Manifest Surface',
                    'target_workspace_path': workspace_path,
                })

                class FakeCoordinator:
                    def __init__(self, orchestrator):
                        pass

                    def start_generation(self, raw, session, context_id):
                        return GenerationContext(
                            context_id=context_id,
                            state=GenerationState.COMPLETED,
                            metadata={
                                'composition_manifest': {
                                    'pattern': 'saas_product',
                                    'pages': {'/': [
                                        {'type': 'Hero',
                                         'mode': 'deterministic',
                                         'component': 'native/Hero'}]},
                                },
                                'deterministic_composition_pct': 100,
                                'content_structured_items': 3,
                            })

                with patch(
                    'odoo.addons.nexora_studio.services.generation.core.'
                    'generation_coordinator.GenerationCoordinator',
                    FakeCoordinator):
                    env['nexora.builder_session_service'].run_generation(
                        session, requirements='SaaS dashboard')

                self.assertEqual(session.status, 'ai_reviewing')
                events = env['nexora.runtime_event'].search([
                    ('builder_session_id', '=', session.id),
                    ('event_type', '=', 'generation.completed')], limit=1)
                self.assertTrue(events,
                                'generation.completed event recorded')
                message = events[0].message
                self.assertIn('Page pattern: saas_product', message)
                self.assertIn('native/Hero(deterministic)', message)
                self.assertIn('Deterministic composition: 100%', message)
                self.assertIn('Structured content items: 3', message)
            finally:
                cr.execute('ROLLBACK TO SAVEPOINT p4729')
                cr.execute('RELEASE SAVEPOINT p4729')
                shutil.rmtree(workspace_path, ignore_errors=True)
        finally:
            cr.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
