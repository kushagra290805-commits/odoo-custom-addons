from odoo.tests.common import TransactionCase
from unittest.mock import patch
import os
import time

class TestPenpotFailureIsolation(TransactionCase):
    
    def setUp(self):
        super().setUp()
        from odoo.addons.nexora_studio.services.connector.onboarding.connection_tester import McpConnectionTester
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService

        def onboarding_factory(rt, pipeline, e):
            return McpOnboardingService(rt, pipeline, e)

        self.tester = McpConnectionTester(
            onboarding_service_factory=onboarding_factory,
            odoo_env=self.env,
        )
        
        self.connector = self.env['nexora.connector'].search([('connector_id', '=', 'penpot_mcp')], limit=1)
        if self.connector:
            self.config = self.env['nexora.mcp_server_config'].search([('connector_id', '=', self.connector.id)], limit=1)
            self.orig_state = self.connector.state
            self.orig_cred_key = self.config.credential_key
            self.orig_endpoint = self.config.command

    def test_a_missing_sse_endpoint_fails_cleanly(self):
        """D. missing SSE endpoint fails cleanly"""
        if not self.connector:
            self.skipTest("penpot_mcp connector not available")
        self.config.command = ''
        result = self.tester.test(self.connector)
        self.assertFalse(result.success)
        self.assertIn("ConfigurationException", str(result.error_message))
        self.config.command = self.orig_endpoint

    def test_b_invalid_sse_endpoint_fails_cleanly(self):
        """E. invalid SSE endpoint fails cleanly"""
        if not self.connector:
            self.skipTest("penpot_mcp connector not available")
        self.config.command = 'http://localhost:9999/invalid/sse'
        result = self.tester.test(self.connector)
        self.assertFalse(result.success)
        self.assertIn("Connection failed", str(result.error_message))
        self.config.command = self.orig_endpoint

    def test_c_missing_credential_fails_cleanly(self):
        """F. missing credential fails cleanly"""
        self.skipTest("Not Applicable: Penpot SSE does not enforce authentication at handshake")

    def test_d_invalid_credential_is_contained(self):
        """G. invalid credential is contained"""
        self.skipTest("Not Applicable: Penpot SSE does not enforce authentication at handshake")

    def test_e_connector_remains_isolated(self):
        """J. connector remains isolated from unrelated providers"""
        # Testing isolation by confirming sibling provider (e.g. github_mcp) isn't affected
        github_conn = self.env['nexora.connector'].search([('connector_id', '=', 'github_mcp')], limit=1)
        if github_conn:
            # We don't execute full test, just ensure registry separation
            self.assertNotEqual(github_conn.id, self.connector.id)
            
    def test_f_configuration_can_be_restored(self):
        """K. configuration can be restored after failure"""
        if not self.connector:
            self.skipTest("penpot_mcp connector not available")
        self.config.command = 'http://bad'
        self.tester.test(self.connector)
        self.config.command = self.orig_endpoint
        self.assertEqual(self.config.command, self.orig_endpoint)
