# -*- coding: utf-8 -*-
import json
import unittest
from typing import Any, Dict

from odoo.tests.common import TransactionCase
from odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter import McpSourceAdapter
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionResult


class MockConnectorRuntime:
    def __init__(self, expected_result):
        self.expected_result = expected_result
        self.last_request = None

    def dispatch(self, request):
        self.last_request = request
        return self.expected_result


class TestMcpSourceAdapter(TransactionCase):

    def setUp(self):
        super().setUp()
        self.connector = self.env['nexora.connector'].create({
            'name': 'Test MCP',
            'technical_name': 'test_mcp',
            'connector_type': 'mcp'
        })
        
        self.source = self.env['nexora.source_registry'].create({
            'name': 'Test Source',
            'technical_name': 'test_source',
            'adapter_class': 'McpSourceAdapter',
            'connector_id': self.connector.id
        })
        
        # Add a mock discovered tool so the capability check passes
        self.env['nexora.mcp_discovered_tool'].create({
            'connector_id': self.connector.id,
            'tool_name': 'test_tool',
            'schema_json': '{}'
        })
        self.env['nexora.mcp_discovered_tool'].create({
            'connector_id': self.connector.id,
            'tool_name': 'search',
            'schema_json': '{}'
        })

    def test_a_existing_behavior_no_default_payload(self):
        """TEST A - Existing behavior: No default_payload."""
        self.source.config_json = json.dumps({"capability_map": {"search": "test_tool"}})
        
        adapter = McpSourceAdapter(self.connector.id, self.env)
        mock_result = ConnectorExecutionResult(success=True, data={"result": "ok"})
        adapter._runtime = MockConnectorRuntime(mock_result)
        
        params = {"query": "test query"}
        res = adapter.search("test query")
        
        # Verify params are wrapped correctly in the dispatch
        expected_payload = {"name": "test_tool", "arguments": params}
        self.assertEqual(adapter._runtime.last_request.payload, expected_payload)
        self.assertEqual(res, {"result": "ok"})

    def test_b_default_payload_merge(self):
        """TEST B - Default payload merges correctly."""
        self.source.config_json = json.dumps({
            "capability_map": {"search": "test_tool"},
            "default_payload": {"repo": "DavidHDev/react-bits"}
        })
        
        adapter = McpSourceAdapter(self.connector.id, self.env)
        adapter._runtime = MockConnectorRuntime(ConnectorExecutionResult(success=True, data=[]))
        
        adapter.search("animated text")
        
        expected_payload = {
            "name": "test_tool",
            "arguments": {
                "query": "animated text",
                "repo": "DavidHDev/react-bits"
            }
        }
        self.assertEqual(adapter._runtime.last_request.payload, expected_payload)

    def test_c_no_mutation(self):
        """TEST C - Verify neither default_payload nor caller params are mutated."""
        default_payload = {"repo": "DavidHDev/react-bits"}
        self.source.config_json = json.dumps({
            "capability_map": {"search": "test_tool"},
            "default_payload": default_payload
        })
        
        adapter = McpSourceAdapter(self.connector.id, self.env)
        adapter._runtime = MockConnectorRuntime(ConnectorExecutionResult(success=True, data=[]))
        
        original_params = {"query": "animated text", "extra": {"a": 1}}
        
        adapter._execute("search", original_params)
        
        # Verify params is unchanged
        self.assertEqual(original_params, {"query": "animated text", "extra": {"a": 1}})
        # Verify internal default payload is unchanged
        self.assertEqual(adapter._default_payload, {"repo": "DavidHDev/react-bits"})

    def test_d_invalid_configuration(self):
        """TEST D - Invalid configuration fails safely."""
        self.source.config_json = json.dumps({
            "capability_map": {"search": "test_tool"},
            "default_payload": "this is not a dictionary"
        })
        
        adapter = McpSourceAdapter(self.connector.id, self.env)
        adapter._runtime = MockConnectorRuntime(ConnectorExecutionResult(success=True, data=[]))
        
        adapter.search("test")
        
        self.assertEqual(adapter._default_payload, {})
        expected_payload = {"name": "test_tool", "arguments": {"query": "test"}}
        self.assertEqual(adapter._runtime.last_request.payload, expected_payload)

    def test_e_existing_capability_mapping(self):
        """TEST E - Verify capability_map continues to work exactly as before."""
        self.source.config_json = json.dumps({
            "capability_map": {"search": "test_tool"}
        })
        
        adapter = McpSourceAdapter(self.connector.id, self.env)
        adapter._runtime = MockConnectorRuntime(ConnectorExecutionResult(success=True, data=[]))
        
        adapter.search("test")
        self.assertEqual(adapter._runtime.last_request.capability_namespace, "tools.call")
        self.assertEqual(adapter._runtime.last_request.payload["name"], "test_tool")

    def test_f_source_isolation_precedence(self):
        """TEST F - Verify that source configuration determines repository scope (precedence)."""
        self.source.config_json = json.dumps({
            "capability_map": {"search": "test_tool"},
            "default_payload": {"repo": "DavidHDev/react-bits"}
        })
        
        adapter = McpSourceAdapter(self.connector.id, self.env)
        adapter._runtime = MockConnectorRuntime(ConnectorExecutionResult(success=True, data=[]))
        
        malicious_params = {"query": "test", "repo": "SomeOther/Repo"}
        adapter._execute("search", malicious_params)
        
        # The default_payload should override the runtime param to ensure source isolation
        expected_payload = {
            "name": "test_tool",
            "arguments": {
                "query": "test",
                "repo": "DavidHDev/react-bits"
            }
        }
        self.assertEqual(adapter._runtime.last_request.payload, expected_payload)
