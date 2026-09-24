# -*- coding: utf-8 -*-
"""AIcredits provider configuration tests (focused, configuration-only).

Verifies the ai_credits provider was added through the EXISTING canonical
configuration pattern (experiential_labs precedent) and that it is safe to
leave unkeyed:

  * provider Selection/catalog includes ai_credits
  * nexora.provider.registry record: openai_compatible profile, canonical
    base URL, 120s timeout, active, EMPTY api_key (missing_key state)
  * glm-5.3-flash registered in nexora.ai_model_catalog for ai_credits and
    linked as the registry default model
  * AIConfigurationService.validate_configuration reports missing_api_key
    (no live call — validation is configuration-sufficiency only)
  * generic_openai adapter is_available is False without a key, so the
    CostRouter cannot select ai_credits until the operator enters one
  * guard: openrouter and experiential_labs registry rows unchanged

No network request is performed anywhere in this module.
"""
import os
import sys
import unittest

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo
from odoo.modules.registry import Registry

odoo.tools.config['test_enable'] = False

PROVIDER_ID = 'ai_credits'
BASE_URL = 'https://api.aicredits.in/v1'
MODEL_ID = 'z-ai/glm-5.3-flash'


def _env():
    reg = Registry.new('nexora_studio')
    cr = reg.cursor()
    return reg, cr, odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})


class TestAICreditsProviderConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg, cls.cr, cls.env = _env()
        cls.registry_model = cls.env['nexora.provider.registry'].sudo()
        cls.catalog = cls.env['nexora.ai_model_catalog'].sudo()
        cls.config_service = cls.env['nexora.ai_configuration_service'].sudo()
        cls.generic_adapter = cls.env['nexora.ai_adapter.generic_openai']

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_01_provider_selection_includes_ai_credits(self):
        # Model fields live on the registry model class, not the imported
        # Python class.
        catalog_cls = self.env['nexora.ai_model_catalog']
        choices = dict(catalog_cls._fields['provider'].selection)
        self.assertIn(PROVIDER_ID, choices)
        self.assertEqual(choices[PROVIDER_ID], 'AIcredits')

    def test_02_registry_record_canonical_fields(self):
        rec = self.registry_model.search([('provider_id', '=', PROVIDER_ID)], limit=1)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.name, 'AIcredits')
        self.assertEqual(rec.category, 'ai')
        self.assertEqual(rec.provider_type, 'cloud')
        self.assertEqual(rec.compatibility_profile, 'openai_compatible')
        self.assertEqual(rec.base_url, BASE_URL)
        self.assertEqual(rec.timeout, 120)
        self.assertTrue(rec.is_active)

    def test_03_api_key_not_set(self):
        rec = self.registry_model.search([('provider_id', '=', PROVIDER_ID)], limit=1)
        self.assertFalse(rec.api_key)
        # The legacy config parameter stays empty too (operator enters the
        # key manually; nothing is committed to source).
        self.assertFalse(self.config_service.get_config(PROVIDER_ID, 'api_key', False))

    def test_04_model_registered_and_default(self):
        model_rec = self.catalog.search(
            [('provider', '=', PROVIDER_ID), ('model_id', '=', MODEL_ID)], limit=1)
        self.assertEqual(len(model_rec), 1)
        self.assertEqual(model_rec.status, 'active')
        rec = self.registry_model.search([('provider_id', '=', PROVIDER_ID)], limit=1)
        self.assertEqual(rec.default_model_id.id, model_rec.id)

    def test_05_validation_reports_missing_api_key(self):
        result = self.config_service.validate_configuration(PROVIDER_ID, MODEL_ID)
        self.assertFalse(result['valid'])
        error_types = {e['type'] for e in result['errors']}
        self.assertIn('missing_api_key', error_types)
        self.assertNotIn('missing_model', error_types)
        self.assertNotIn('invalid_catalog', error_types)

    def test_06_adapter_unavailable_without_key(self):
        """CostRouter cannot select ai_credits until a key is entered."""
        credentials = self.config_service.get_provider_credentials(PROVIDER_ID)
        self.assertEqual(credentials['base_url'], BASE_URL)
        self.assertEqual(credentials['api_key'], '')
        self.assertFalse(self.generic_adapter.is_available(credentials=credentials))

    def test_07_openrouter_and_experiential_unchanged(self):
        openrouter = self.registry_model.search([('provider_id', '=', 'openrouter')], limit=1)
        exp = self.registry_model.search([('provider_id', '=', 'experiential_labs')], limit=1)
        self.assertEqual(len(openrouter), 1)
        self.assertTrue(openrouter.is_active)
        self.assertEqual(len(exp), 1)
        self.assertTrue(exp.is_active)
        self.assertEqual(exp.base_url, 'https://api.experientiallabs.ai/v1')
        self.assertEqual(exp.timeout, 120)
        self.assertTrue(exp.api_key)  # operator-managed key remains in place

    def test_08_not_the_active_default_provider(self):
        active = self.env['ir.config_parameter'].sudo().get_param(
            'nexora.active_ai_provider', '')
        self.assertNotEqual(active, PROVIDER_ID)


if __name__ == '__main__':
    unittest.main(verbosity=2)
