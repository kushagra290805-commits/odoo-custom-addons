# -*- coding: utf-8 -*-
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
import json

from odoo.tests.common import TransactionCase
from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
from odoo.addons.nexora_studio.services.connector.credentials.odoo_credential_resolver import OdooCredentialResolver
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorCredentialReference
from odoo.exceptions import ValidationError

class TestMcpCredentials(TransactionCase):
    test_tags = {'standard', 'at_install'}

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))
        
        # We need a master key
        self.master_key = Fernet.generate_key().decode()
        
        # Patch the secrets provider to use our test key
        patcher = patch('os.environ.get')
        self.mock_env_get = patcher.start()
        self.addCleanup(patcher.stop)
        
        def mock_getenv(key, default=None):
            if key == 'NEXORA_CONNECTOR_SECRET_KEY':
                return self.master_key
            return default
            
        self.mock_env_get.side_effect = mock_getenv
        
        # Set up a connector type and connector
        self.connector_type = self.env['nexora.connector_type'].create({
            'name': 'Test MCP Type',
            'type_code': 'mcp'
        })
        self.connector = self.env['nexora.connector'].create({
            'name': 'Test Credential Connector',
            'connector_id': 'test_cred_conn',
            'connector_type_id': self.connector_type.id,
            'state': 'registered'
        })
        
        # Configure MCP server to satisfy _get_mcp_config validations
        self.mcp_config = self.env['nexora.mcp_server_config'].create({
            'connector_id': self.connector.id,
            'command': 'test_cmd',
            'args_json': '[]',
        })

    def test_plaintext_create_persists_ciphertext(self):
        """1 & 2. Plaintext create persists ciphertext, DB differs from plaintext"""
        secret_value = "synthetic-secret-value-123"
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.connector.id,
            'credential_key': 'TEST_TOKEN',
            'encrypted_value': secret_value
        })
        
        # Assert database value is NOT the plaintext
        self.assertNotEqual(cred.encrypted_value, secret_value)
        # Assert it IS Fernet ciphertext
        self.assertTrue(cred.encrypted_value.startswith('gAAAAA'))

    def test_stored_ciphertext_can_be_decrypted(self):
        """3 & 4. Stored ciphertext can be decrypted by provider and resolver returns plaintext"""
        secret_value = "synthetic-secret-value-456"
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.connector.id,
            'credential_key': 'TEST_TOKEN_2',
            'encrypted_value': secret_value
        })
        
        provider = OdooSecretsProvider(env=self.env)
        composite_key = f"{self.connector.connector_id}:TEST_TOKEN_2"
        
        # Test Provider
        decrypted = provider.get_secret(composite_key)
        self.assertEqual(decrypted, secret_value)
        
        # Test Resolver
        resolver = OdooCredentialResolver(env=self.env)
        resolved_dict = resolver.resolve_all_for_connector(self.connector.connector_id)
        self.assertEqual(resolved_dict.get('TEST_TOKEN_2'), secret_value)

    def test_credential_update_rotates_correctly(self):
        """5. Credential update rotates correctly"""
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.connector.id,
            'credential_key': 'TEST_TOKEN_3',
            'encrypted_value': 'initial-value'
        })
        
        initial_encrypted = cred.encrypted_value
        
        # Rotate
        new_secret = "new-rotated-value"
        cred.write({'encrypted_value': new_secret})
        
        self.assertNotEqual(cred.encrypted_value, initial_encrypted)
        self.assertTrue(cred.encrypted_value.startswith('gAAAAA'))
        
        provider = OdooSecretsProvider(env=self.env)
        composite_key = f"{self.connector.connector_id}:TEST_TOKEN_3"
        self.assertEqual(provider.get_secret(composite_key), new_secret)

    def test_already_encrypted_not_double_encrypted(self):
        """6. Already-encrypted internal value is not double-encrypted"""
        provider = OdooSecretsProvider(env=self.env)
        secret_value = "synthetic-secret-value-789"
        manually_encrypted = provider._encrypt(secret_value)
        
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.connector.id,
            'credential_key': 'TEST_TOKEN_4',
            'encrypted_value': manually_encrypted
        })
        
        # Should be exactly equal, not double encrypted
        self.assertEqual(cred.encrypted_value, manually_encrypted)
        
        composite_key = f"{self.connector.connector_id}:TEST_TOKEN_4"
        self.assertEqual(provider.get_secret(composite_key), secret_value)

    def test_missing_key_fails_safely(self):
        """7. Missing encryption key fails safely"""
        # Create valid credential first
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.connector.id,
            'credential_key': 'TEST_TOKEN_5',
            'encrypted_value': 'secret'
        })
        
        # Now mock the key as missing
        self.mock_env_get.side_effect = lambda k, d=None: None
        
        provider = OdooSecretsProvider(env=self.env)
        composite_key = f"{self.connector.connector_id}:TEST_TOKEN_5"
        
        # Should raise an error, but not leak the value
        with self.assertRaises(Exception) as cm:
            provider.get_secret(composite_key)
            
        self.assertNotIn('secret', str(cm.exception))

    def test_invalid_ciphertext_fails_safely(self):
        """8. Invalid ciphertext fails safely"""
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.connector.id,
            'credential_key': 'TEST_TOKEN_6',
            'encrypted_value': 'secret'
        })
        
        # Manually corrupt the ciphertext in DB
        self.env.cr.execute(
            "UPDATE nexora_mcp_credential SET encrypted_value = 'gAAAAA_invalid_garbage' WHERE id = %s",
            [cred.id]
        )
        self.env.invalidate_all()
        
        provider = OdooSecretsProvider(env=self.env)
        composite_key = f"{self.connector.connector_id}:TEST_TOKEN_6"
        
        with self.assertRaises(Exception) as cm:
            provider.get_secret(composite_key)
            
        self.assertNotIn('secret', str(cm.exception))

    def test_enable_lifecycle_triggers_runtime(self):
        """Action enable transitions to running and invokes runtime sync."""
        self.assertEqual(self.connector.state, 'registered')
        
        with patch('odoo.addons.nexora_studio.models.connector.nexora_connector.NexoraConnector._trigger_runtime_sync') as mock_sync:
            self.connector.action_enable()
            self.assertEqual(self.connector.state, 'running')
            mock_sync.assert_called_once()
