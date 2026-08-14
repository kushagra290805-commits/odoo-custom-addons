import unittest
import os
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError


class TestEncryptionKeyConfig(unittest.TestCase):
    def setUp(self):
        self.provider = OdooSecretsProvider(env=MagicMock())
        # Clean environment before tests
        if 'NEXORA_CONNECTOR_SECRET_KEY' in os.environ:
            del os.environ['NEXORA_CONNECTOR_SECRET_KEY']

    def test_missing_key_fails_safely(self):
        """Test that missing key throws safe ConnectorConfigurationError."""
        from odoo.tools import config
        old_val = config.options.get('nexora_connector_secret_key')
        config.options['nexora_connector_secret_key'] = None
        try:
            with self.assertRaises(ConnectorConfigurationError) as cm:
                self.provider.set_secret("test:key", "value")
                
            self.assertEqual(cm.exception.error_code, 'SECRET_KEY_MISSING')
            self.assertIn('Secret key missing', cm.exception.technical_message)
        finally:
            config.options['nexora_connector_secret_key'] = old_val

    def test_key_from_odoo_config(self):
        """Test that Odoo correctly resolves the key from odoo.tools.config."""
        import cryptography.fernet
        from odoo.tools import config
        key = cryptography.fernet.Fernet.generate_key().decode()
        
        old_val = config.options.get('nexora_connector_secret_key')
        config.options['nexora_connector_secret_key'] = key
        try:
            # Should not raise exception
            encrypted = self.provider._encrypt("test_value")
            self.assertTrue(encrypted.startswith("gAAAAA"))
            
            decrypted = self.provider._decrypt(encrypted)
            self.assertEqual(decrypted, "test_value")
        finally:
            config.options['nexora_connector_secret_key'] = old_val

    def test_key_from_env_fallback(self):
        """Test fallback to environment variable."""
        import cryptography.fernet
        from odoo.tools import config
        
        old_val = config.options.get('nexora_connector_secret_key')
        config.options['nexora_connector_secret_key'] = None
        
        key = cryptography.fernet.Fernet.generate_key().decode()
        os.environ['NEXORA_CONNECTOR_SECRET_KEY'] = key
        try:
            encrypted = self.provider._encrypt("test_fallback")
            self.assertTrue(encrypted.startswith("gAAAAA"))
        finally:
            del os.environ['NEXORA_CONNECTOR_SECRET_KEY']
            config.options['nexora_connector_secret_key'] = old_val

    def test_plaintext_fails_decryption(self):
        """Test that plaintext legacy values throw RuntimeError (no plaintext fallback allowed)."""
        import cryptography.fernet
        from odoo.tools import config
        key = cryptography.fernet.Fernet.generate_key().decode()
        
        old_val = config.options.get('nexora_connector_secret_key')
        config.options['nexora_connector_secret_key'] = key
        try:
            # No plaintext fallback is allowed per user request, it raises RuntimeError
            with self.assertRaises(RuntimeError) as cm:
                self.provider._decrypt("github_pat_11BWLR26I...")
            self.assertIn('Failed to decrypt credential', str(cm.exception))
        finally:
            config.options['nexora_connector_secret_key'] = old_val

if __name__ == '__main__':
    unittest.main()
