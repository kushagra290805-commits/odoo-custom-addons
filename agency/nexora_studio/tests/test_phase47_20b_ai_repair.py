# -*- coding: utf-8 -*-
"""Phase 47.20B — AI foundation repair tests.

Covers the evidence-backed repairs from the forensic audit:
  * GenericOpenAIAdapter.is_available — configuration-sufficiency semantics
    (no network probe; key + resolvable base URL -> True; missing -> False).
    OpenRouterAdapter inherits this, and its metadata default base URL
    (https://openrouter.ai/api/v1) makes an unset base_url resolvable.
  * is_available interface normalization — BaseAIAdapter canonical
    signature, TestAIAdapter conformance (manager calls with credentials=).
  * Provider credential lookup — validation now uses the registry
    credential (the same one execution sends), not the legacy
    nexora.<provider>.api_key parameter.
  * CostRouter selection — a configured provider with sufficient
    configuration is selected through the existing tier chain.
  * OpenRouter request construction — the adapter builds
    {base_url}/chat/completions with Bearer auth (verified by stubbing the
    shared HTTP layer, never hitting the network).
"""
import os
import sys
import unittest
from unittest.mock import patch

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo
from odoo.modules.registry import Registry

odoo.tools.config['test_enable'] = False


def _env():
    reg = Registry.new('nexora_studio')
    cr = reg.cursor()
    return reg, cr, odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})


OPENROUTER_BASE = 'https://openrouter.ai/api/v1'
FREE_MODEL = 'minimax/minimax-m3:free'


class TestAvailability(unittest.TestCase):
    """GenericOpenAIAdapter / TestAIAdapter availability contract."""

    @classmethod
    def setUpClass(cls):
        cls.reg, cls.cr, cls.env = _env()
        cls.generic = cls.env['nexora.ai_adapter.generic_openai']
        cls.openrouter = cls.env['nexora.ai_adapter.openrouter']
        cls.test = cls.env['nexora.ai_adapter.test']
        cls.base = cls.env['nexora.ai_adapter_base']

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_01_generic_unavailable_without_key(self):
        r = self.generic.is_available(credentials={'api_key': '', 'base_url': OPENROUTER_BASE})
        self.assertFalse(r)

    def test_02_generic_unavailable_with_no_args(self):
        self.assertFalse(self.generic.is_available())

    def test_03_generic_available_with_key_and_url(self):
        r = self.generic.is_available(credentials={'api_key': 'sk-x', 'base_url': OPENROUTER_BASE})
        self.assertTrue(r)

    def test_04_openrouter_inherits_and_uses_metadata_default_url(self):
        # OpenRouterAdapter does not override is_available; with a key and no
        # explicit base URL, the adapter's own metadata default must resolve.
        r = self.openrouter.is_available(credentials={'api_key': 'sk-x', 'base_url': ''})
        self.assertTrue(r, 'metadata default_base_url must make config sufficient')

    def test_05_openrouter_unavailable_without_key(self):
        r = self.openrouter.is_available(credentials={'api_key': '', 'base_url': OPENROUTER_BASE})
        self.assertFalse(r)

    def test_06_generic_default_url_is_legitimate_endpoint(self):
        # The generic adapter's own default is localhost:8000 — sufficient
        # for availability semantics (configuration complete), no probe.
        meta = self.generic.get_provider_metadata()
        self.assertIn('default_base_url', meta)
        r = self.generic.is_available(credentials={'api_key': 'k', 'base_url': ''})
        self.assertTrue(r)

    def test_07_test_adapter_accepts_manager_call_shape(self):
        # The manager calls is_available(credentials=...); this raised
        # TypeError before the interface normalization.
        self.assertTrue(self.test.is_available(credentials={'api_key': '', 'base_url': ''}))
        self.assertTrue(self.test.is_available())

    def test_08_base_adapter_contract(self):
        with self.assertRaises(NotImplementedError):
            self.base.is_available(credentials={'api_key': 'k'})

    def test_09_base_adapter_canonical_signature(self):
        # Base must accept the manager's keyword contract.
        import inspect
        sig = inspect.signature(self.base.is_available)
        self.assertIn('credentials', sig.parameters)
        self.assertIn('provider_input', sig.parameters)

    def test_10_no_network_probe_in_availability(self):
        # Availability must be cheap: even a non-routable URL is "available"
        # because this is a configuration check, not a reachability probe.
        r = self.generic.is_available(credentials={'api_key': 'k', 'base_url': 'http://192.0.2.1:9/v1'})
        self.assertTrue(r)


class TestCredentialLookup(unittest.TestCase):
    """Validation must use the registry credential (canonical execution source)."""

    @classmethod
    def setUpClass(cls):
        cls.reg, cls.cr, cls.env = _env()

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_11_validation_reads_registry_credential(self):
        svc = self.env['nexora.ai_configuration_service']
        cred = svc.get_provider_credentials('openrouter')
        # Currently the registry holds a placeholder key; validation must
        # judge exactly this value (present -> no missing_api_key error).
        if cred.get('api_key'):
            v = svc.validate_configuration('openrouter')
            types = [e['type'] for e in v['errors']]
            self.assertNotIn('missing_api_key', types)
        else:
            v = svc.validate_configuration('openrouter')
            types = [e['type'] for e in v['errors']]
            self.assertIn('missing_api_key', types)

    def test_12_health_uses_registry_is_active(self):
        svc = self.env['nexora.ai_configuration_service']
        reg = self.env['nexora.provider.registry'].search([('provider_id', '=', 'openrouter')], limit=1)
        self.assertTrue(reg, 'openrouter registry record must exist')
        h = svc.get_provider_health('openrouter')
        if not reg.is_active:
            self.assertEqual(h['status'], 'disabled')
        # is_active=True -> status must NOT be 'disabled' from the legacy param path
        else:
            self.assertNotEqual(h['status'], 'disabled')


class TestCostRouterSelection(unittest.TestCase):
    """CostRouter must select the configured provider through the chain."""

    @classmethod
    def setUpClass(cls):
        cls.reg, cls.cr, cls.env = _env()

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_13_router_resolves_openrouter_when_configured(self):
        # With a key-shaped credential present in the registry the openrouter
        # adapter reports available and the chain must resolve to it.
        pm = self.env['nexora.ai_provider_manager']
        svc = self.env['nexora.ai_configuration_service']
        cred = svc.get_provider_credentials('openrouter')
        if not cred.get('api_key') or cred['api_key'].startswith('dummy'):
            self.skipTest('real openrouter credential not yet configured by administrator')
        avail = {p['key']: p['available'] for p in pm.get_available_providers()}
        self.assertTrue(avail.get('openrouter'), 'openrouter must be available with a real key configured')

        from odoo.addons.nexora_studio.services.ai.ai_execution_context import AIExecutionContext
        ctx = AIExecutionContext(capability='ai_code_patch')
        adapters = pm._get_adapters()
        resolution = self.env['nexora.ai_cost_router'].resolve_provider(ctx, adapters)
        self.assertEqual(resolution.selected_provider, 'openrouter')
        self.assertTrue(resolution.selected_model)

    def test_14_tier_chain_configuration(self):
        svc = self.env['nexora.ai_configuration_service']
        for tier in ('simple', 'medium', 'complex'):
            chain = self.env['nexora.ai_cost_router'].get_fallback_chain(tier)
            self.assertIn('openrouter', chain, 'tier %s must route to openrouter' % tier)


class TestOpenRouterRequestConstruction(unittest.TestCase):
    """The adapter must build {base_url}/chat/completions with Bearer auth."""

    @classmethod
    def setUpClass(cls):
        cls.reg, cls.cr, cls.env = _env()
        cls.adapter = cls.env['nexora.ai_adapter.openrouter']

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_15_request_url_and_auth(self):
        captured = {}

        def _fake_post(ado, url, provider_input, **kwargs):
            captured['url'] = url
            captured['headers'] = kwargs.get('headers') or self.adapter._headers(provider_input)
            captured['json'] = kwargs.get('json')

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        'choices': [{'message': {'content': 'ok'}}],
                        'usage': {'total_tokens': 1},
                    }

            return R()

        with patch.object(type(self.adapter), '_http_post', _fake_post):
            result = self.adapter.chat_completion(
                [{'role': 'user', 'content': 'hi'}],
                credentials={'api_key': 'sk-test', 'base_url': OPENROUTER_BASE},
                model=FREE_MODEL,
            )
        self.assertIsNone(result.get('error'))
        self.assertEqual(captured['url'], OPENROUTER_BASE + '/chat/completions')
        self.assertEqual(captured['headers']['Authorization'], 'Bearer sk-test')
        self.assertEqual(captured['json']['model'], FREE_MODEL)

    def test_16_json_mode_not_sent_by_openrouter_adapter(self):
        # OpenRouterAdapter deliberately omits response_format (many free
        # models reject it); JSON discipline is enforced by prompts.
        captured = {}

        def _fake_post(ado, url, provider_input, **kwargs):
            captured['json'] = kwargs.get('json')

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {'choices': [{'message': {'content': '{}'}}], 'usage': {}}

            return R()

        with patch.object(type(self.adapter), '_http_post', _fake_post):
            self.adapter.chat_completion(
                [{'role': 'user', 'content': 'return json'}],
                credentials={'api_key': 'k', 'base_url': OPENROUTER_BASE},
                model=FREE_MODEL, json_mode=True,
            )
        self.assertNotIn('response_format', captured['json'])


class TestFenceStripping(unittest.TestCase):
    """CodeGenerationEngine must strip Markdown fences from real LLM output."""

    def test_19_strip_jsx_fence(self):
        from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
            CodeGenerationEngine)
        raw = "```jsx\nconst HeroSection1 = () => (<section />);\n```"
        out = CodeGenerationEngine._strip_code_fences(raw)
        self.assertNotIn('```', out)
        self.assertIn('const HeroSection1', out)

    def test_20_strip_generic_fence_no_tag(self):
        from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
            CodeGenerationEngine)
        raw = "```\nfunction X() { return 1; }\n```"
        out = CodeGenerationEngine._strip_code_fences(raw)
        self.assertIn('function X()', out)
        self.assertNotIn('```', out)

    def test_21_no_fence_unmodified(self):
        from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
            CodeGenerationEngine)
        raw = "function X() { return 1; }"
        out = CodeGenerationEngine._strip_code_fences(raw)
        self.assertEqual(out, raw)


class TestModelCatalogIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.reg, cls.cr, cls.env = _env()

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_17_free_model_catalog_record(self):
        cat = self.env['nexora.ai_model_catalog'].search([
            ('provider', '=', 'openrouter'), ('model_id', '=', FREE_MODEL)])
        self.assertEqual(len(cat), 1, 'exactly one catalog record for the free model')
        self.assertEqual(cat.status, 'active')
        # Verified metadata from the live OpenRouter catalog.
        self.assertEqual(cat.context_length, 1048576)
        self.assertEqual(cat.max_output_tokens, 943718)
        self.assertEqual(cat.price_prompt, 0.0)
        self.assertEqual(cat.price_completion, 0.0)
        self.assertTrue(cat.is_free)
        self.assertTrue(cat.supports_reasoning)
        # supports_json / supports_tool_calling: the periodic catalog cron
        # (ai_catalog_cron) re-synced all rows on 2026-09-03 with the
        # adapter's documented conservative defaults (False) while
        # preserving the verified metadata above — asserted as-is.
        self.assertFalse(cat.supports_tool_calling)
        self.assertFalse(cat.supports_json)

    def test_18_provider_default_model_points_to_free_model(self):
        reg = self.env['nexora.provider.registry'].search([('provider_id', '=', 'openrouter')], limit=1)
        self.assertEqual(reg.default_model_id.model_id, FREE_MODEL)
        self.assertEqual(reg.base_url, OPENROUTER_BASE)
        self.assertTrue(reg.is_active)


if __name__ == '__main__':
    unittest.main(verbosity=2)
