# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import requests
from unittest.mock import patch, MagicMock

class TestPhase18ProviderIntegration(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Registry = self.env['nexora.provider.registry']
        self.ProviderManager = self.env['nexora.ai_provider_manager']

        self.test_provider = self.Registry.create({
            'provider_id': 'test_provider_fixture',
            'name': 'Test Provider Fixture',
            'category': 'ai',
            'compatibility_profile': 'openai_compatible',
            'base_url': 'https://api.test-provider.invalid',
            'api_key': 'test-key',
            'lifecycle_state': 'CONFIGURED'
        })

    def test_adapter_resolution_by_profile(self):
        adapters = self.ProviderManager._get_adapters()
        self.assertIn('test_provider_fixture', adapters)
        self.assertEqual(adapters['test_provider_fixture']._name, 'nexora.ai_adapter.generic_openai')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_success(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'x-ratelimit-remaining': '99'}
        mock_get.return_value = mock_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 404
        mock_post.return_value = mock_post_resp

        with patch.object(self.ProviderManager, 'sync_catalog'):
            diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
            self.assertEqual(diagnostics['authentication_state'], 'authenticated')
            self.assertEqual(diagnostics['connectivity_state'], 'reachable')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_auth_failure(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
        self.assertEqual(diagnostics['authentication_state'], 'failed')
        self.assertEqual(self.test_provider.lifecycle_state, 'DEGRADED')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_rate_limit(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 429
        mock_post.return_value = mock_post_resp

        diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
        self.assertEqual(diagnostics['connectivity_state'], 'reachable')
        self.assertEqual(diagnostics['authentication_state'], 'authenticated')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_server_error(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 500
        mock_post.return_value = mock_post_resp

        diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
        self.assertEqual(diagnostics['connectivity_state'], 'reachable')
        self.assertEqual(diagnostics['authentication_state'], 'authenticated')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_timeout(self, mock_get, mock_post):
        mock_get.side_effect = requests.exceptions.Timeout()

        diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
        self.assertEqual(diagnostics['connectivity_state'], 'unreachable')
        self.assertEqual(self.test_provider.lifecycle_state, 'UNAVAILABLE')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_dns_failure(self, mock_get, mock_post):
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed to resolve")

        diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
        self.assertEqual(diagnostics['connectivity_state'], 'unreachable')
        self.assertEqual(self.test_provider.lifecycle_state, 'UNAVAILABLE')

    @patch('requests.post')
    @patch('requests.get')
    def test_connection_diagnostics_ssl_failure(self, mock_get, mock_post):
        mock_get.side_effect = requests.exceptions.SSLError("SSL Certificate verify failed")

        diagnostics = self.ProviderManager.test_connection('test_provider_fixture')
        self.assertEqual(diagnostics['connectivity_state'], 'unreachable')
        self.assertEqual(self.test_provider.lifecycle_state, 'UNAVAILABLE')

    def test_provider_audit_log(self):
        self.test_provider.write({'base_url': 'https://api.new.test-provider.invalid'})
        audit_log = self.env['nexora.provider.audit.log'].search([
            ('provider_id', '=', self.test_provider.id)
        ], limit=1)
        self.assertTrue(audit_log)
        self.assertIn("https://api.new.test-provider.invalid", audit_log.details)

    def test_api_key_masking_in_audit_log(self):
        self.test_provider.write({'api_key': 'sk-secret-key-1234'})
        audit_log = self.env['nexora.provider.audit.log'].search([
            ('provider_id', '=', self.test_provider.id)
        ], limit=1, order='create_date desc')
        self.assertNotIn("sk-secret-key-1234", audit_log.details)
        self.assertIn("Updated API Key", audit_log.details)
