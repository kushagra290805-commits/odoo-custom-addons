import threading
import unittest
from unittest.mock import patch, MagicMock

class TestLifecycleBootstrap(unittest.TestCase):

    def setUp(self):
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap, BootstrapState
        self.bootstrap = ConnectorPlatformBootstrap.get_instance()
        self.bootstrap._state = BootstrapState.UNINITIALIZED
        self.bootstrap._connector_runtime = None

        self.env = MagicMock()
        self.env.registry.db_name = 'test_db'
        self.env.cr.closed = False
        # The persistence adapter detects a live test environment via
        # threading.current_thread().testing (set by the odoo test runner).
        # Replicate it so the adapter uses the provided mock env directly
        # instead of trying to open a real Registry cursor.
        threading.current_thread().testing = True

    def tearDown(self):
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap, BootstrapState
        self.bootstrap = ConnectorPlatformBootstrap.get_instance()
        self.bootstrap._state = BootstrapState.UNINITIALIZED
        self.bootstrap._connector_runtime = None
        try:
            del threading.current_thread().testing
        except AttributeError:
            pass

    def test_1_bootstrap_creates_runtime(self):
        """1. bootstrap(env) creates persistent runtime."""
        self.bootstrap.bootstrap(self.env)
        self.assertIsNotNone(self.bootstrap.connector_runtime)
        self.assertTrue(self.bootstrap.is_bootstrapped)
        
    def test_2_bootstrap_is_idempotent(self):
        """2. bootstrap(env) is idempotent."""
        self.bootstrap.bootstrap(self.env)
        runtime1 = self.bootstrap.connector_runtime
        
        self.bootstrap.bootstrap(self.env)
        runtime2 = self.bootstrap.connector_runtime
        
        self.assertIs(runtime1, runtime2)

    def test_3_bootstrap_none_upgrades_safely(self):
        """3. bootstrap(None) -> bootstrap(env) upgrades correctly."""
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import BootstrapState
        
        # Initial memory bootstrap
        self.bootstrap.bootstrap(None)
        self.assertIsNotNone(self.bootstrap.connector_runtime)
        self.assertIsNone(getattr(self.bootstrap.connector_runtime.registry, '_persistence', None))
        self.assertEqual(self.bootstrap._state, BootstrapState.READY)
        
        # Upgrade to persistence
        with patch('threading.Thread') as mock_thread:
            self.bootstrap.bootstrap(self.env)
            self.assertIsNotNone(getattr(self.bootstrap.connector_runtime.registry, '_persistence', None))
            # It should spawn exactly one async thread
            mock_thread.assert_called_once()

    def test_4_duplicate_reconciliation_prevented(self):
        """5. Multiple bootstrap calls do not create duplicate reconciliation workers."""
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import BootstrapState
        
        self.bootstrap.bootstrap(self.env)
        
        # Manually force state to RECONCILING to simulate slow thread
        self.bootstrap._state = BootstrapState.RECONCILING
        
        with patch('threading.Thread') as mock_thread:
            self.bootstrap.bootstrap(self.env)
            mock_thread.assert_not_called()

    @patch('odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service.McpOnboardingService.register_connector')
    def test_startup_reconciliation_isolation(self, mock_register):
        """Test isolation: Context7 failure does not block GitHub."""
        from odoo.addons.nexora_studio.services.connector.domain.models import Connector, ConnectorLifecycleState
        
        # Mocking the registry to return 2 RUNNING connectors
        conn1 = MagicMock()
        conn1.connector_id = 'github_mcp'
        conn1.lifecycle_state = ConnectorLifecycleState.RUNNING
        
        conn2 = MagicMock()
        conn2.connector_id = 'context7_mcp'
        conn2.lifecycle_state = ConnectorLifecycleState.RUNNING
        
        self.bootstrap.bootstrap(None) # Setup runtime
        self.bootstrap._connector_runtime.registry.register(conn1)
        self.bootstrap._connector_runtime.registry.register(conn2)
        
        # Mock Odoo Environment for searching connectors
        record1 = MagicMock()
        record1.connector_id = 'github_mcp'
        record1.connector_type_id.type_code = 'mcp'
        
        record2 = MagicMock()
        record2.connector_id = 'context7_mcp'
        record2.connector_type_id.type_code = 'mcp'
        
        def mock_search(args, **kwargs):
            cid = args[0][2]
            return record1 if cid == 'github_mcp' else record2
            
        self.env['nexora.connector'].search.side_effect = mock_search
        
        # Make context7_mcp fail, but github_mcp succeed
        def side_effect(record):
            if record.connector_id == 'context7_mcp':
                raise Exception("Network timeout")
        mock_register.side_effect = side_effect
        
        self.bootstrap._startup_reconciliation(self.env)
        
        # Assertions
        # Both records should have been processed
        self.assertEqual(mock_register.call_count, 2)

        # Context7 should be written as failed. Phase 44.2 (W5): the
        # persisted error_message carries only the exception type name —
        # never raw exception text (which may leak paths or details).
        record2.write.assert_called_once_with({
            'state': 'failed',
            'health_status': 'failed',
            'error_message': 'Startup reconciliation failed: Exception'
        })

        # GitHub succeeded: stale error cleared, but health stays 'unknown'
        # until a real probe succeeds (Phase 44.2 W5 / G-05 truthful health).
        record1.write.assert_called_once_with({
            'error_message': False,
            'health_status': 'unknown'
        })

if __name__ == '__main__':
    import sys
    unittest.main(argv=['first-arg-is-ignored'])
