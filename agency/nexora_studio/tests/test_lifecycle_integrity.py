from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap, get_connector_runtime
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState

@tagged('-at_install', 'post_install', 'nexora_lifecycle')
class TestLifecycleIntegrity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.bootstrap = ConnectorPlatformBootstrap.get_instance()
        # Force a fresh bootstrap for the test environment
        self.bootstrap.reset()
        self.bootstrap.bootstrap(self.env)
        self.runtime = get_connector_runtime()
        
        # Setup test data
        self.type_mcp = self.env['nexora.connector_type'].create({
            'name': 'MCP Protocol',
            'type_code': 'mcp'
        })
        
        self.test_connector = self.env['nexora.connector'].create({
            'connector_id': 'test_mcp_1',
            'name': 'Test MCP Connector',
            'connector_type_id': self.type_mcp.id,
            'state': 'registered'
        })
        
        self.test_config = self.env['nexora.mcp_server_config'].create({
            'connector_id': self.test_connector.id,
            'command': 'node',
            'args_json': '["-v"]',
            'env_vars_json': '{}'
        })

    def tearDown(self):
        self.bootstrap.reset()
        super().tearDown()

    def test_01_persistence_service_loads_connectors(self):
        """1. Persistence service correctly loads connectors."""
        # Ensure it's in the registry
        self.runtime.registry.sync_from_odoo()
        conn = self.runtime.registry.get('test_mcp_1')
        self.assertIsNotNone(conn)
        self.assertEqual(conn.lifecycle_state, ConnectorLifecycleState.REGISTERED)

    def test_02_persisted_running_missing_credentials_fails(self):
        """3. Persisted RUNNING + missing credentials -> FAILED."""
        # We manually set state to running in the DB bypassing the ORM hook (simulating a crash or bad state)
        self.test_connector.write({'state': 'running'})
        
        # Run startup reconciliation
        self.bootstrap._startup_reconciliation(self.env)
        
        # Should be downgraded to failed because node -v as a handshake will fail without valid MCP
        # Wait, the node -v will exit immediately and the session will be closed, making the handshake fail.
        self.test_connector.invalidate_recordset(['state'])
        self.assertEqual(self.test_connector.state, 'failed')

    def test_03_action_enable_failure_cannot_leave_state_running(self):
        """12. action_enable() failure cannot leave state RUNNING."""
        self.test_connector.action_enable()
        
        # It should fail the handshake and be 'failed'
        self.assertEqual(self.test_connector.state, 'failed')
        
    def test_04_credential_deletion_invalidates_runtime(self):
        """9. Credential deletion from active connector invalidates the runtime."""
        # First, mock register_connector so we can force it running
        from unittest.mock import patch
        with patch('odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service.McpOnboardingService.register_connector') as mock_reg:
            self.test_connector.action_enable()
            self.assertEqual(self.test_connector.state, 'running')
            
        cred = self.env['nexora.mcp_credential'].create({
            'connector_id': self.test_connector.id,
            'credential_key': 'test_pat',
            'encrypted_value': 'dummy'
        })
        
        with patch('odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service.McpOnboardingService.register_connector') as mock_reg:
            cred.unlink()
            # sync_credential_rotation should be called, which evicts and re-registers
            mock_reg.assert_called()

    def test_05_register_connector_handshake_verification(self):
        """13. register_connector() handshake handles SUCCESS and FAILURE."""
        from unittest.mock import patch, MagicMock
        from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionResult, ConnectorExecutionStatus
        from odoo.addons.nexora_studio.services.connector.sdk.exceptions import ConnectorConfigurationError
        
        # Test 1: Handshake SUCCESS
        success_result = ConnectorExecutionResult(
            request_id="test", 
            status=ConnectorExecutionStatus.SUCCESS,
            data={"tools": []}
        )
        with patch('odoo.addons.nexora_studio.services.connector.runtime.dispatcher.ConnectorDispatcher._execute_on_connector', return_value=success_result):
            # register_connector shouldn't raise exception
            self.test_connector.action_enable()
            self.assertEqual(self.test_connector.state, 'running')
            
        # Test 2: Handshake FAILURE
        self.test_connector.write({'state': 'registered'})
        failure_result = ConnectorExecutionResult(
            request_id="test", 
            status=ConnectorExecutionStatus.FAILURE,
            error="Simulated MCP Failure"
        )
        with patch('odoo.addons.nexora_studio.services.connector.runtime.dispatcher.ConnectorDispatcher._execute_on_connector', return_value=failure_result):
            # action_enable catches the exception and sets state to failed
            self.test_connector.action_enable()
            self.assertEqual(self.test_connector.state, 'failed')
            self.assertIn("failed to initialize or handshake", self.test_connector.error_message)
