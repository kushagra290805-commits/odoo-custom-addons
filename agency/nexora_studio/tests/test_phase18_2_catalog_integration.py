# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from unittest.mock import patch, MagicMock

class TestPhase182CatalogIntegration(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Registry = self.env['nexora.provider.registry']
        self.CatalogService = self.env['nexora.ai_catalog_service']
        self.Catalog = self.env['nexora.ai_model_catalog']
        self.ModelResolutionService = self.env['nexora.model_resolution_service']
        
        self.test_provider = self.Registry.create({
            'provider_id': 'test_catalog_provider',
            'name': 'Test Catalog Provider',
            'category': 'ai',
            'compatibility_profile': 'openai_compatible',
            'base_url': 'https://api.test.in/v1',
            'lifecycle_state': 'CONFIGURED',
            'is_active': True
        })

        # Set this as the active AI provider in ir.config_parameter
        self.env['ir.config_parameter'].sudo().set_param('nexora.active_ai_provider', 'test_catalog_provider')

    @patch('odoo.addons.nexora_studio.services.ai.generic_openai_adapter.GenericOpenAIAdapter.fetch_catalog')
    def test_sync_catalog_creates_models(self, mock_fetch):
        mock_fetch.return_value = [
            {'id': 'model-chat-1', 'name': 'Chat Model 1', 'context_length': 4096, 'supports_chat': True},
            {'id': 'model-code-1', 'name': 'Code Model 1', 'context_length': 8192, 'supports_chat': True}
        ]
        
        self.CatalogService.sync_catalog('test_catalog_provider')
        
        models = self.Catalog.search([('provider', '=', 'test_catalog_provider')])
        self.assertEqual(len(models), 2)
        self.assertTrue(any(m.model_id == 'model-chat-1' for m in models))
        
        # Verify provider registry updated counts
        self.assertEqual(self.test_provider.catalog_model_count, 2)
        self.assertEqual(self.test_provider.catalog_sync_status, 'success')

    @patch('odoo.addons.nexora_studio.services.ai.generic_openai_adapter.GenericOpenAIAdapter.fetch_catalog')
    def test_sync_catalog_updates_status(self, mock_fetch):
        # Create an existing model
        self.Catalog.create({
            'provider': 'test_catalog_provider',
            'model_id': 'model-old-1',
            'name': 'Old Model',
            'status': 'active'
        })
        
        # Mock returns a DIFFERENT model
        mock_fetch.return_value = [
            {'id': 'model-new-1', 'name': 'New Model', 'context_length': 4096}
        ]
        
        self.CatalogService.sync_catalog('test_catalog_provider')
        
        old_model = self.Catalog.search([('provider', '=', 'test_catalog_provider'), ('model_id', '=', 'model-old-1')])
        self.assertEqual(old_model.status, 'unavailable')
        
        new_model = self.Catalog.search([('provider', '=', 'test_catalog_provider'), ('model_id', '=', 'model-new-1')])
        self.assertEqual(new_model.status, 'active')

    def test_workload_resolution(self):
        m1 = self.Catalog.create({'provider': 'test_catalog_provider', 'model_id': 'model-default', 'name': 'Default'})
        m2 = self.Catalog.create({'provider': 'test_catalog_provider', 'model_id': 'model-code', 'name': 'Code'})
        
        self.test_provider.write({
            'default_model_id': m1.id,
            'default_code_model_id': m2.id
        })
        
        # Create mock generation job
        job = self.env['nexora.generation_job'].create({
            'name': 'Test Job',
            'status': 'pending'
        })
        
        # Resolve without workload (should get default)
        res1 = self.ModelResolutionService.resolve_model(job.id)
        self.assertEqual(res1.model_id, 'model-default')
        
        # Resolve with code workload
        res2 = self.ModelResolutionService.resolve_model(job.id, workload='code')
        self.assertEqual(res2.model_id, 'model-code')
        
        # Resolve with chat workload (no specific default, should fallback to default)
        res3 = self.ModelResolutionService.resolve_model(job.id, workload='chat')
        self.assertEqual(res3.model_id, 'model-default')
