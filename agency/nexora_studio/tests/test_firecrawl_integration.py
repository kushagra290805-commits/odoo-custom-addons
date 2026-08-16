# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService

class TestFirecrawlIntegration(unittest.TestCase):

    def setUp(self):
        self.mock_env = MagicMock()
        
        self.mock_connector = MagicMock()
        self.mock_connector.id = 1
        self.mock_connector.connector_id = "firecrawl_mcp"
        self.mock_connector.name = "Firecrawl Extraction MCP"
        self.mock_connector.version = "1.0.0"
        
        self.mock_config = MagicMock()
        self.mock_config.transport_type = "stdio"
        self.mock_config.command = "npx"
        self.mock_config.get_args_list.return_value = ["-y", "firecrawl-mcp"]
        self.mock_config.get_env_vars_dict.return_value = {}
        self.mock_config.authentication_location = "none"
        self.mock_config.authentication_name = ""
        self.mock_config.authentication_scheme = "none"
        self.mock_config.credential_key = ""
        
        def search_side_effect(domain, **kwargs):
            if domain[0][2] == 1:
                return self.mock_config
            return None
            
        self.mock_env['nexora.mcp_server_config'].search.side_effect = search_side_effect
        
        self.mock_runtime = MagicMock()
        self.mock_pipeline = MagicMock()
        
        self.service = McpOnboardingService(self.mock_runtime, self.mock_pipeline, self.mock_env)
        # Mock the resolver to simulate having FIRECRAWL_API_KEY set
        self.service._resolver = MagicMock()
        self.service._resolver.resolve_all_for_connector.return_value = {
            "FIRECRAWL_API_KEY": "fc-secret-12345"
        }

    def test_firecrawl_mcp_configuration_builder(self):
        """
        Verify that the Firecrawl generic XML data translates perfectly into a
        stdio McpConfiguration with the FIRECRAWL_API_KEY injected into the environment.
        """
        config = self.service._build_mcp_configuration(self.mock_connector, self.mock_config)
        
        self.assertEqual(config.transport, "stdio")
        self.assertEqual(config.command, "npx")
        self.assertEqual(config.args, ["-y", "firecrawl-mcp"])
        
        # Verify credential injection
        self.assertIn("FIRECRAWL_API_KEY", config.env)
        self.assertEqual(config.env["FIRECRAWL_API_KEY"], "fc-secret-12345")

    def test_firecrawl_manifest_builder(self):
        """
        Verify that Firecrawl manifest exposes the generic MCP capabilities,
        and is NOT hardcoded to web_search or scrape natively.
        """
        manifest = self.service._build_manifest(self.mock_connector)
        
        self.assertEqual(manifest.connector_id, "firecrawl_mcp")
        self.assertEqual(manifest.display_name, "Firecrawl Extraction MCP")
        self.assertEqual(manifest.connector_type_id, "mcp")
        self.assertIn("tools.call", manifest.capabilities)
        self.assertIn("prompts.get", manifest.capabilities)
