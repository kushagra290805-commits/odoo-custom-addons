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
            'provider_id': 'test_airouter',
            'name': 'Test AIRouter',
            'category': 'ai',
            'compatibility_profile': 'openai_compatible',
            'base_url': 'https://api.airouter.in/v1',
            'lifecycle_state': 'CONFIGURED'
        })

    def test_adapter_resolution_by_profile(self):
        adapters = self.ProviderManager._get_adapters()
        self.assertIn('test_airouter', adapters)
        self.assertEqual(adapters['test_airouter']._name, 'nexora.ai_adapter.generic_openai')

    def test_invalid_lifecycle_transition_raises_error(self):
        """Test that invalid lifecycle transition raises UserError."""
        # Valid: CONFIGURED -> VALIDATING
        self.test_provider.transition_lifecycle('VALIDATING')
        self.assertEqual(self.test_provider.lifecycle_state, 'VALIDATING')
        
        # Invalid: VALIDATING -> CONFIGURED
        with self.assertRaises(UserError):
            self.test_provider.transition_lifecycle('CONFIGURED')

    @patch('requests.get')
    def test_connection_diagnostics_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'x-ratelimit-remaining': '99'}
        mock_get.return_value = mock_resp
        
        with patch.object(self.ProviderManager, 'sync_catalog'):
            diagnostics = self.ProviderManager.test_connection('test_airouter')
            self.assertEqual(diagnostics['auth_status'], 'SUCCESS')
            self.assertEqual(self.test_provider.lifecycle_state, 'HEALTHY')

    @patch('requests.get')
    def test_connection_diagnostics_auth_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp
        
        diagnostics = self.ProviderManager.test_connection('test_airouter')
        self.assertEqual(diagnostics['auth_status'], 'FAILED')
        self.assertEqual(self.test_provider.lifecycle_state, 'DEGRADED')

    @patch('requests.get')
    def test_connection_diagnostics_rate_limit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp
        
        diagnostics = self.ProviderManager.test_connection('test_airouter')
        self.assertEqual(diagnostics['auth_status'], 'RATE_LIMITED')
        self.assertEqual(self.test_provider.lifecycle_state, 'DEGRADED')

    @patch('requests.get')
    def test_connection_diagnostics_server_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp
        
        diagnostics = self.ProviderManager.test_connection('test_airouter')
        self.assertEqual(diagnostics['auth_status'], 'SERVER_ERROR_500')
        self.assertEqual(self.test_provider.lifecycle_state, 'DEGRADED')

    @patch('requests.get')
    def test_connection_diagnostics_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        
        diagnostics = self.ProviderManager.test_connection('test_airouter')
        self.assertEqual(self.test_provider.health_status, 'TIMEOUT')
        self.assertEqual(self.test_provider.lifecycle_state, 'DEGRADED')

    @patch('requests.get')
    def test_connection_diagnostics_dns_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed to resolve")
        
        diagnostics = self.ProviderManager.test_connection('test_airouter')
        self.assertEqual(self.test_provider.health_status, 'DNS/CONNECTION_ERROR')
        self.assertEqual(self.test_provider.lifecycle_state, 'UNAVAILABLE')

    @patch('requests.get')
    def test_connection_diagnostics_ssl_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.SSLError("SSL Certificate verify failed")
        
        diagnostics = self.ProviderManager.test_connection('test_airouter')
        self.assertEqual(self.test_provider.health_status, 'SSL_ERROR')
        self.assertEqual(self.test_provider.lifecycle_state, 'UNAVAILABLE')

    def test_provider_audit_log(self):
        self.test_provider.write({'base_url': 'https://api.new.airouter.in/v1'})
        audit_log = self.env['nexora.provider.audit.log'].search([
            ('provider_id', '=', self.test_provider.id)
        ], limit=1)
        self.assertTrue(audit_log)
        self.assertIn("https://api.new.airouter.in/v1", audit_log.details)

    def test_api_key_masking_in_audit_log(self):
        self.test_provider.write({'api_key': 'sk-secret-key-1234'})
        audit_log = self.env['nexora.provider.audit.log'].search([
            ('provider_id', '=', self.test_provider.id)
        ], limit=1, order='create_date desc')
        self.assertNotIn("sk-secret-key-1234", audit_log.details)
        self.assertIn("Updated API Key", audit_log.details)
