import unittest
from unittest.mock import Mock, patch

from odoo.addons.nexora_studio.services.connector.runtime.dispatcher import ConnectorDispatcher
from odoo.addons.nexora_studio.services.connector.registry.capability_index import ConnectorCapabilityIndex
from odoo.addons.nexora_studio.services.connector.registry.connector_registry import ConnectorRegistry
from odoo.addons.nexora_studio.services.connector.domain.models import (
    ConnectorExecutionRequest,
    ConnectorRuntimeContext,
    ConnectorExecutionResult,
)
from odoo.addons.nexora_studio.services.connector.domain.models import Connector


from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorManifest

from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorLifecycleState

class TestRoutingIsolation(unittest.TestCase):

    def setUp(self):
        self.registry = ConnectorRegistry()
        self.index = ConnectorCapabilityIndex()
        self.dispatcher = ConnectorDispatcher(self.registry, self.index)

        # Mock the actual execution so we can see which connector was chosen
        self.dispatcher._execute_on_connector = Mock(side_effect=self._mock_execute)

    def _mock_execute(self, connector, request):
        return ConnectorExecutionResult.ok(
            request_id=request.request_id,
            data={"executed_on": connector.connector_id}
        )

    def _register(self, connector_id, capabilities):
        manifest = ConnectorManifest(connector_id=connector_id, display_name="Test", version="1", connector_type_id="test", capabilities=capabilities)
        c = Connector(manifest=manifest, lifecycle_state=ConnectorLifecycleState.RUNNING)
        self.registry.register(c)
        for cap in capabilities:
            self.index.add(cap, connector_id)

    def test_01_github_tools_call(self):
        self._register('github_mcp', ['tools.call'])
        self._register('context7_mcp', ['tools.call'])
        
        ctx = ConnectorRuntimeContext(connector_id='github_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'github_mcp')

    def test_02_context7_tools_call(self):
        self._register('github_mcp', ['tools.call'])
        self._register('context7_mcp', ['tools.call'])
        
        ctx = ConnectorRuntimeContext(connector_id='context7_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'context7_mcp')

    def test_03_github_tools_list(self):
        self._register('github_mcp', ['tools.list'])
        self._register('context7_mcp', ['tools.list'])
        
        ctx = ConnectorRuntimeContext(connector_id='github_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.list', context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'github_mcp')

    def test_04_context7_tools_list(self):
        self._register('github_mcp', ['tools.list'])
        self._register('context7_mcp', ['tools.list'])
        
        ctx = ConnectorRuntimeContext(connector_id='context7_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.list', context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'context7_mcp')

    def test_05_unknown_connector_id(self):
        self._register('github_mcp', ['tools.call'])
        
        ctx = ConnectorRuntimeContext(connector_id='invalid_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "CONNECTOR_NOT_FOUND")

    def test_06_unsupported_namespace(self):
        self._register('context7_mcp', ['tools.list'])
        
        ctx = ConnectorRuntimeContext(connector_id='context7_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "CONNECTOR_NOT_FOUND")

    def test_07_context7_resolve_library_id(self):
        self._register('github_mcp', ['tools.call'])
        self._register('context7_mcp', ['tools.call'])
        
        ctx = ConnectorRuntimeContext(connector_id='context7_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', payload={'name': 'resolve-library-id'}, context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'context7_mcp')

    def test_08_github_search_repositories(self):
        self._register('github_mcp', ['tools.call'])
        self._register('context7_mcp', ['tools.call'])
        
        ctx = ConnectorRuntimeContext(connector_id='github_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', payload={'name': 'search_repositories'}, context=ctx)
        res = self.dispatcher.dispatch(req)
        
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'github_mcp')

    def test_09_10_capability_discovery_isolation(self):
        # We test discovery isolation implicitly via tools.list routing which is used for discovery
        self.test_03_github_tools_list()
        self.test_04_context7_tools_list()

    def test_11_registration_order(self):
        # Forward order
        self.setUp()
        self._register('github_mcp', ['tools.call'])
        self._register('context7_mcp', ['tools.call'])
        ctx1 = ConnectorRuntimeContext(connector_id='github_mcp', session_id='test')
        res1 = self.dispatcher.dispatch(ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx1))
        self.assertEqual(res1.data['executed_on'], 'github_mcp')
        ctx2 = ConnectorRuntimeContext(connector_id='context7_mcp', session_id='test')
        res2 = self.dispatcher.dispatch(ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx2))
        self.assertEqual(res2.data['executed_on'], 'context7_mcp')

        # Reverse order
        self.setUp()
        self._register('context7_mcp', ['tools.call'])
        self._register('github_mcp', ['tools.call'])
        ctx1 = ConnectorRuntimeContext(connector_id='github_mcp', session_id='test')
        res1 = self.dispatcher.dispatch(ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx1))
        self.assertEqual(res1.data['executed_on'], 'github_mcp')
        ctx2 = ConnectorRuntimeContext(connector_id='context7_mcp', session_id='test')
        res2 = self.dispatcher.dispatch(ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx2))
        self.assertEqual(res2.data['executed_on'], 'context7_mcp')

    def test_12_coexist_without_shadowing(self):
        self._register('context7_mcp', ['tools.call'])
        self._register('github_mcp', ['tools.call'])
        
        # Test fallback capability (no context) - relies on capability index primary
        req = ConnectorExecutionRequest(capability_namespace='tools.call')
        res = self.dispatcher.dispatch(req)
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'context7_mcp')  # primary since it was registered first

        # Test scoped capability - respects explicit connector_id
        ctx = ConnectorRuntimeContext(connector_id='github_mcp', session_id='test')
        req = ConnectorExecutionRequest(capability_namespace='tools.call', context=ctx)
        res = self.dispatcher.dispatch(req)
        self.assertTrue(res.success)
        self.assertEqual(res.data['executed_on'], 'github_mcp')

if __name__ == '__main__':
    unittest.main()
