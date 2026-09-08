# -*- coding: utf-8 -*-
"""Phase 47.20C — REAL LLM JSON contract repair tests for ContentEngine.

Covers the evidence-backed repairs from the real OpenRouter E2E probe:
  * Valid LLM JSON matching the canonical schema -> accepted (no fallback).
  * Realistic LLM JSON with normal whitespace -> accepted.
  * JSON wrapped in a markdown fence -> normalized and accepted.
  * The natural "site + pages[]" LLM shape observed from the real model
    (slug-keyed array, "editable" bundles) -> normalized and accepted.
  * Invalid JSON -> deterministic fallback with observable reason.
  * Valid JSON with a schema violation -> deterministic fallback with reason.
  * Real provider response extraction -> correct content payload
    (choices[0].message.content through the OpenRouter adapter).
  * Deterministic fallback content unchanged (regression).
"""
import json
import os
import sys
import unittest
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
    ArchitectureModel, RequirementModel, WebsiteGenerationArtifact)
from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
    ContentEngine)


def _artifact():
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(
            domain='Agency',
            raw_input='Business: Atelier Meridian - premium architecture and '
                      'interior design studio, Copenhagen.',
            business_name='Atelier Meridian',
            business_category='premium architecture and interior design studio',
            location='Copenhagen, Denmark',
            target_audience='affluent homeowners aged 35-60',
        ),
        architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/', 'sections': ['Hero', 'Content']},
            'services': {'type': 'page', 'path': '/services', 'sections': ['Hero', 'Content']},
        }),
    )


_CANONICAL = {
    "pages": {
        "/": {
            "seo": {"title": "Atelier Meridian | Copenhagen",
                    "description": "Considered homes for discerning homeowners."},
            "metadata": {"status": "draft"},
            "sections": [
                {"type": "Hero", "semantic_heading": "h1", "aria_label": "intro",
                 "body": "Architecture and Interiors Crafted for the Way You Live"},
                {"type": "Content", "semantic_heading": "h2", "aria_label": "studio",
                 "body": "We work with a small number of clients each year."},
            ],
        },
    }
}

# The natural shape the REAL model returned (evidence: Phase 47.20C probe).
_REAL_LLM_NATURAL = {
    "site": {
        "business_name": "Atelier Meridian",
        "category": "Premium Architecture and Interior Design Studio",
        "location": "Copenhagen, Denmark",
    },
    "pages": [
        {
            "slug": "/",
            "sections": [
                {
                    "type": "Hero",
                    "editable": {
                        "headline": {"value": "Architecture and Interiors Crafted for the Way You Live",
                                     "max_chars": 80, "notes": "Primary value proposition."},
                        "subheadline": {"value": "A Copenhagen studio designing considered homes.",
                                        "max_chars": 220},
                        "cta_primary": {"label": "Begin a Project", "href": "/contact"},
                    },
                },
                {
                    "type": "Content",
                    "editable": {
                        "heading": {"value": "A Studio for Considered Living", "max_chars": 60},
                        "body": {"value": "We work with a small number of clients each year.",
                                 "max_chars": 900},
                        "list": [
                            {"label": "Residential Architecture",
                             "value": "New homes, extensions, and renovations."},
                        ],
                    },
                },
            ],
        },
    ],
}


def _run(ai_response):
    artifact = _artifact()
    engine = ContentEngine(MagicMock())
    runtime = MagicMock()
    runtime.ai.generate.return_value = ai_response
    result = engine.execute(artifact, runtime)
    return result, runtime


class TestCanonicalContract(unittest.TestCase):

    def test_01_valid_llm_json_accepted(self):
        result, _ = _run({'analysis': json.dumps(_CANONICAL)})
        self.assertTrue(result.success)
        pages = result.artifact.content.pages
        self.assertIn('/', pages)
        self.assertNotIn('content_fallback_reason', result.metadata)
        self.assertEqual(pages['/']['seo']['title'], 'Atelier Meridian | Copenhagen')
        self.assertEqual(pages['/']['sections'][0]['body'],
                         'Architecture and Interiors Crafted for the Way You Live')

    def test_02_realistic_whitespace_accepted(self):
        text = "\n\n  " + json.dumps(_CANONICAL, indent=4) + "  \n"
        result, _ = _run({'analysis': text})
        self.assertNotIn('content_fallback_reason', result.metadata)
        self.assertIn('/', result.artifact.content.pages)

    def test_03_markdown_fence_normalized_then_accepted(self):
        fenced = "```json\n" + json.dumps(_CANONICAL) + "\n```"
        result, _ = _run({'analysis': fenced})
        self.assertNotIn('content_fallback_reason', result.metadata)
        pages = result.artifact.content.pages
        self.assertEqual(pages['/']['seo']['title'], 'Atelier Meridian | Copenhagen')

    def test_03b_unlabelled_fence_normalized(self):
        fenced = "```\n" + json.dumps(_CANONICAL) + "\n```"
        result, _ = _run({'analysis': fenced})
        self.assertNotIn('content_fallback_reason', result.metadata)

    def test_04_invalid_json_deterministic_fallback(self):
        result, _ = _run({'analysis': 'not json at all {{{'})
        self.assertTrue(result.success)
        self.assertEqual(result.metadata.get('content_fallback_reason'),
                         'ai_content_schema_validation_failed')
        pages = result.artifact.content.pages
        # Deterministic fallback content (regression: unchanged shape).
        self.assertIn('/', pages)
        self.assertIn('/services', pages)
        self.assertEqual(pages['/']['seo']['title'], 'Agency - /')
        self.assertEqual(pages['/']['sections'][0]['type'], 'Hero')
        self.assertEqual(pages['/']['sections'][0]['body'], 'Editable content for Hero')

    def test_04b_provider_error_falls_back(self):
        # A provider-level error dict (error set, empty response) must fall
        # back deterministically, never crash the pipeline.
        result, _ = _run({'analysis': '', 'response': '', 'error': 'rate limited'})
        self.assertEqual(result.metadata.get('content_fallback_reason'),
                         'ai_content_schema_validation_failed')
        self.assertIn('/', result.artifact.content.pages)

    def test_05_schema_violation_deterministic_fallback(self):
        # Valid JSON but missing required seo.title on the page -> fallback.
        bad = {"pages": {"/": {"metadata": {}, "sections": []}}}
        result, _ = _run({'analysis': json.dumps(bad)})
        self.assertEqual(result.metadata.get('content_fallback_reason'),
                         'ai_content_schema_validation_failed')
        # Fallback produced full deterministic pages.
        self.assertEqual(result.artifact.content.pages['/']['seo']['title'], 'Agency - /')

    def test_05b_pages_array_without_usable_data_falls_back(self):
        # pages is an array of non-dicts -> unusable -> fallback.
        result, _ = _run({'analysis': json.dumps({"pages": ["junk"]})})
        self.assertEqual(result.metadata.get('content_fallback_reason'),
                         'ai_content_schema_validation_failed')


class TestRealLlmNaturalShape(unittest.TestCase):
    """The exact shape the real OpenRouter model returned in the probe."""

    def test_06_natural_shape_normalized_and_accepted(self):
        result, _ = _run({'analysis': json.dumps(_REAL_LLM_NATURAL)})
        self.assertNotIn('content_fallback_reason', result.metadata)
        pages = result.artifact.content.pages
        self.assertIn('/', pages)
        page = pages['/']
        # SEO derived from hero headline (real LLM copy).
        self.assertEqual(page['seo']['title'],
                         'Architecture and Interiors Crafted for the Way You Live')
        # Sections canonicalized from editable bundles: headline is the
        # semantic heading; subheadline is the hero body copy.
        types = [s['type'] for s in page['sections']]
        self.assertEqual(types, ['Hero', 'Content'])
        hero = page['sections'][0]
        self.assertIn('A Copenhagen studio designing considered homes', hero['body'])
        content_sec = page['sections'][1]
        self.assertEqual(content_sec['semantic_heading'], 'A Studio for Considered Living')
        self.assertIn('small number of clients', content_sec['body'])
        # Real list content survives into the body.
        self.assertIn('Residential Architecture: New homes', content_sec['body'])

    def test_06b_fenced_natural_shape_accepted(self):
        fenced = "```json\n" + json.dumps(_REAL_LLM_NATURAL) + "\n```"
        result, _ = _run({'analysis': fenced})
        self.assertNotIn('content_fallback_reason', result.metadata)
        self.assertIn('/', result.artifact.content.pages)

    def test_06c_slug_without_leading_slash_normalized(self):
        variant = json.loads(json.dumps(_REAL_LLM_NATURAL))
        variant['pages'][0]['slug'] = 'home'
        result, _ = _run({'analysis': json.dumps(variant)})
        self.assertNotIn('content_fallback_reason', result.metadata)
        # Phase 47.29: a 'home' slug resolves onto the architecture's
        # authoritative home route ('/'), not an orphan '/home' key.
        self.assertIn('/', result.artifact.content.pages)
        self.assertNotIn('/home', result.artifact.content.pages)

    def test_06d_analysis_key_missing_falls_back_to_response_key(self):
        # Real provider path: engine-boundary normalization sets both
        # 'analysis' and 'response' from the same payload; if a caller only
        # supplies 'response', it must still be used.
        result, _ = _run({'response': json.dumps(_REAL_LLM_NATURAL)})
        self.assertNotIn('content_fallback_reason', result.metadata)

    def test_06e_prompt_contains_schema_contract(self):
        # The schema must reach the LLM: the AIRuntimeAdapter excludes
        # response_format from the prompt, so the canonical shape must be
        # stated in the prompt text itself.
        artifact = _artifact()
        engine = ContentEngine(MagicMock())
        runtime = MagicMock()
        runtime.ai.generate.return_value = {'analysis': ''}
        engine.execute(artifact, runtime)
        prompt = runtime.ai.generate.call_args[0][1]['prompt']
        self.assertIn('"pages"', prompt)
        self.assertIn('OBJECT keyed by page path', prompt)
        self.assertIn('markdown fence', prompt)


class TestProviderResponseExtraction(unittest.TestCase):
    """The OpenRouter adapter must extract choices[0].message.content and
    the manager must surface it as 'analysis' for generate_content."""

    @classmethod
    def setUpClass(cls):
        cls.reg = Registry.new('nexora_studio')
        cls.cr = cls.reg.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.adapter = cls.env['nexora.ai_adapter.openrouter']

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def _fake_post(self, captured, content):
        def _post(ado, url, provider_input, **kwargs):
            captured['url'] = url
            captured['json'] = kwargs.get('json')

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    # Real OpenRouter shape: content in
                    # choices[0].message.content; reasoning models may add
                    # reasoning_content which must NOT pollute the payload.
                    return {
                        'choices': [{
                            'message': {
                                'role': 'assistant',
                                'content': content,
                                'reasoning_content': 'internal chain of thought {not json}',
                            }
                        }],
                        'usage': {'total_tokens': 10, 'prompt_tokens': 5,
                                  'completion_tokens': 5},
                    }
            return R()
        return _post

    def test_07_openrouter_extracts_message_content_and_excludes_reasoning(self):
        captured = {}
        content = json.dumps(_CANONICAL)
        with patch.object(type(self.adapter), '_http_post',
                          self._fake_post(captured, content)):
            result = self.adapter.chat_completion(
                [{'role': 'user', 'content': 'generate content'}],
                credentials={'api_key': 'sk-test',
                             'base_url': 'https://openrouter.ai/api/v1'},
                model='minimax/minimax-m3:free',
            )
        self.assertIsNone(result.get('error'))
        self.assertEqual(result['response'], content)
        self.assertNotIn('reasoning', result['response'])

    def test_08_fenced_real_response_survives_engine_boundary(self):
        # Full chain: fenced content through adapter extraction, through the
        # manager's engine-boundary 'analysis' normalization, into
        # ContentEngine. (Manager route is exercised with the test provider
        # disabled; here we verify the engine consumes a real-shaped result.)
        fenced = "```json\n" + json.dumps(_REAL_LLM_NATURAL) + "\n```"
        captured = {}
        with patch.object(type(self.adapter), '_http_post',
                          self._fake_post(captured, fenced)):
            result = self.adapter.chat_completion(
                [{'role': 'user', 'content': 'generate content'}],
                credentials={'api_key': 'sk-test',
                             'base_url': 'https://openrouter.ai/api/v1'},
                model='minimax/minimax-m3:free',
            )
        # The manager's setdefault('analysis', response) contract:
        result.setdefault('analysis', result.get('response', ''))
        engine_result, _ = _run({'analysis': result['analysis']})
        self.assertNotIn('content_fallback_reason', engine_result.metadata)
        self.assertIn('/', engine_result.artifact.content.pages)


class TestFallbackRegression(unittest.TestCase):
    """Deterministic fallback architecture remains intact."""

    def test_09_deterministic_fallback_complete_for_all_pages(self):
        result, _ = _run({'analysis': {}})
        pages = result.artifact.content.pages
        self.assertEqual(sorted(pages.keys()), ['/', '/services'])
        for path, page in pages.items():
            self.assertIn('title', page['seo'])
            self.assertEqual(page['metadata']['status'], 'draft')
            self.assertEqual([s['type'] for s in page['sections']], ['Hero', 'Content'])

    def test_10_no_llm_exception_leaks_to_pipeline(self):
        # Unparseable garbage of every kind still yields success=True with
        # fallback (the pipeline retries engine exceptions twice; fallback
        # avoids that for content contract violations).
        for bad in (None, '', 'null', '[1,2,3]', '"string"', '{"pages": 3}'):
            result, _ = _run({'analysis': bad})
            self.assertTrue(result.success)
            self.assertIn('content_fallback_reason', result.metadata)


if __name__ == '__main__':
    unittest.main(verbosity=2)
