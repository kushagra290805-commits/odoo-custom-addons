import unittest
from unittest.mock import MagicMock, PropertyMock, patch
from odoo.tests.common import TransactionCase
from odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter import McpSourceAdapter

class TestMcpSourceAdapterMappings(TransactionCase):
    def setUp(self):
        super().setUp()
        self.mock_env = MagicMock()
        self.adapter = McpSourceAdapter(connector_id=1, env=self.mock_env)
        self.adapter._runtime = MagicMock()

        # Override ensure_config to mock config parsing easily
        self.adapter._capability_map = {}
        self.adapter._default_payload = {}
        self.adapter._payload_mapping = {}
        self.adapter._normalization_map = {}
        self.adapter._ensure_config_loaded = lambda: None

    @patch('odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter.McpSourceAdapter.capabilities', new_callable=PropertyMock)
    def test_a_existing_behavior_unchanged(self, mock_caps):
        mock_caps.return_value = ['test_tool']
        self.adapter._runtime.dispatch.return_value = MagicMock(success=True, data="result")
        res = self.adapter._execute('test_tool', {'id': '123'})
        args = self.adapter._runtime.dispatch.call_args[0][0].payload['arguments']
        self.assertEqual(args, {'id': '123'})

    @patch('odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter.McpSourceAdapter.capabilities', new_callable=PropertyMock)
    def test_b_generic_payload_mapping(self, mock_caps):
        mock_caps.return_value = ['test_tool']
        self.adapter._payload_mapping = {'test_tool': {'path': 'id'}}
        self.adapter._runtime.dispatch.return_value = MagicMock(success=True, data="result")
        res = self.adapter._execute('test_tool', {'id': 'components/button.tsx'})
        args = self.adapter._runtime.dispatch.call_args[0][0].payload['arguments']
        self.assertEqual(args, {'id': 'components/button.tsx', 'path': 'components/button.tsx'})

    @patch('odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter.McpSourceAdapter.capabilities', new_callable=PropertyMock)
    def test_c_missing_source_key(self, mock_caps):
        mock_caps.return_value = ['test_tool']
        self.adapter._payload_mapping = {'test_tool': {'path': 'id'}}
        self.adapter._runtime.dispatch.return_value = MagicMock(success=True, data="result")
        res = self.adapter._execute('test_tool', {'other': 'value'})
        args = self.adapter._runtime.dispatch.call_args[0][0].payload['arguments']
        self.assertEqual(args, {'other': 'value'})

    @patch('odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter.McpSourceAdapter.capabilities', new_callable=PropertyMock)
    def test_d_default_payload_intact(self, mock_caps):
        mock_caps.return_value = ['test_tool']
        self.adapter._default_payload = {'repo': 'shadcn-ui/ui'}
        self.adapter._runtime.dispatch.return_value = MagicMock(success=True, data="result")
        res = self.adapter._execute('test_tool', {'id': '123'})
        args = self.adapter._runtime.dispatch.call_args[0][0].payload['arguments']
        self.assertEqual(args, {'id': '123', 'repo': 'shadcn-ui/ui'})

    def test_f_standard_mcp_envelope_json_object(self):
        raw_mcp = {
            "content": [{"type": "text", "text": "{\"component_id\": \"btn1\", \"name\": \"Button\"}"}]
        }
        res = self.adapter._normalize(raw_mcp)
        from odoo.addons.nexora_studio.services.source_framework.domain_models import ComponentPackage
        self.assertIsInstance(res, ComponentPackage)
        self.assertEqual(res.component_id, "btn1")
        self.assertEqual(res.name, "Button")

    def test_g_standard_mcp_envelope_json_list(self):
        raw_mcp = {
            "content": [{"type": "text", "text": "{\"items\": [{\"component_id\": \"btn1\", \"name\": \"Button\"}]}"}]
        }
        res = self.adapter._normalize(raw_mcp)
        self.assertTrue(isinstance(res, list))
        self.assertEqual(len(res), 1)
        from odoo.addons.nexora_studio.services.source_framework.domain_models import ComponentPackage
        self.assertIsInstance(res[0], ComponentPackage)

    def test_h_non_json_text_preserved(self):
        raw_mcp = {
            "content": [{"type": "text", "text": "Some raw text"}]
        }
        res = self.adapter._normalize(raw_mcp)
        self.assertEqual(res, raw_mcp)

    def test_i_already_decoded_list(self):
        raw_list = [{"component_id": "btn1", "name": "Button"}]
        res = self.adapter._normalize(raw_list)
        self.assertTrue(isinstance(res, list))
        self.assertEqual(res[0].component_id, "btn1")

    def test_k_normalization_mapping(self):
        self.adapter._normalization_map = {'component_id': 'path', 'name': 'title'}
        raw_mcp = {
            "content": [{"type": "text", "text": "{\"path\": \"my/btn.tsx\", \"title\": \"MyButton\"}"}]
        }
        res = self.adapter._normalize(raw_mcp)
        self.assertEqual(res.component_id, "my/btn.tsx")
        self.assertEqual(res.name, "MyButton")
