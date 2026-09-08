# -*- coding: utf-8 -*-
"""Phase 47.8A — canonical McpSourceAdapter contract tests.

DB-free unit tests: env is faked; execution goes through a mocked canonical
router (post-ADR-0069 / Phase 44.2 closure contract). Legacy _runtime.dispatch
path removed — the adapter now uses build_canonical_router → ConnectorExecutionTarget
→ ConnectorRuntime.
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter import McpSourceAdapter
from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager

BOOTSTRAP = 'odoo.addons.nexora_studio.services.connector.integration.bootstrap'


# ---------------------------------------------------------------- fake env --
class _Rec:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _ConnModel:
    def __init__(self, connector):
        self._c = connector

    def browse(self, _id):
        return self._c


class _RegModel:
    def __init__(self, row):
        self._r = row

    def search(self, domain, limit=None):
        return self._r


class _ToolsModel:
    def __init__(self, tools):
        self._t = tools

    def search(self, domain, limit=None):
        return self._t


class FakeEnv:
    def __init__(self, connector, registry_row, discovered):
        self._connector = connector
        self._registry_row = registry_row
        self._discovered = [_Rec(tool_name=t) for t in discovered]

    def __getitem__(self, model):
        if model == 'nexora.connector':
            return _ConnModel(self._connector)
        if model == 'nexora.source_registry':
            return _RegModel(self._registry_row)
        if model == 'nexora.mcp_discovered_tool':
            return _ToolsModel(self._discovered)
        raise KeyError(model)


def make_adapter(capabilities='', config=None, discovered=('search_code', 'get_file_contents'),
                 technical_name='test_source', connector_id='test_mcp'):
    connector = _Rec(connector_id=connector_id, capability_ids=[_Rec(technical_name=t) for t in discovered])
    row = _Rec(technical_name=technical_name, capabilities=capabilities,
               config_json=json.dumps(config) if config is not None else None)
    env = FakeEnv(connector, row, discovered)
    with patch(BOOTSTRAP + '.get_connector_runtime', return_value=object()):
        return McpSourceAdapter(connector_id=101, env=env)


def router_mock(result_data=None, success=True):
    router = MagicMock()
    ret = MagicMock()
    ret.success = success
    ret.result = result_data if result_data is not None else {}
    ret.logs = []
    router.execute.return_value = ret
    return patch(BOOTSTRAP + '.build_canonical_router', return_value=router)


# ------------------------------------------------------- U1 mandated proofs --
class TestSemanticCapabilityReconciliation(unittest.TestCase):

    def test_1_declared_search_discoverable_by_search(self):
        """Mandate 1: a source declaring SEARCH is discoverable by SEARCH."""
        adapter = make_adapter(capabilities='SEARCH')
        pm = ProviderManager(env=None)
        pm.register_adapter('test_source', adapter)
        self.assertIn('test_source', pm.get_capable_providers('SEARCH'))
        self.assertEqual(adapter.capabilities, ['SEARCH'])

    def test_2_tool_names_do_not_imply_semantic_capability(self):
        """Mandate 2: exposing search_code without declarations is NOT discoverable."""
        adapter = make_adapter(capabilities='', discovered=('search_code',))
        pm = ProviderManager(env=None)
        pm.register_adapter('test_source', adapter)
        self.assertEqual(adapter.capabilities, [])
        self.assertNotIn('test_source', pm.get_capable_providers('SEARCH'))
        self.assertNotIn('search_code', adapter.capabilities)

    def test_3_execution_guard_still_validates_discovered_tools(self):
        """Mandate 3: concrete tool execution validates against discovered tools."""
        adapter = make_adapter(
            capabilities='SEARCH',
            config={'capability_map': {'search': 'search_code'}})
        # Undiscovered tool -> rejected even though semantics declare SEARCH.
        with patch(BOOTSTRAP + '.get_connector_runtime', return_value=object()):
            adapter2 = make_adapter(
                capabilities='SEARCH',
                config={'capability_map': {'search': 'not_a_real_tool'}})
            with self.assertRaises(ValueError):
                adapter2._execute('search', {'query': 'x'})
        # Discovered tool -> executes through the canonical router contract.
        with router_mock({'ok': True}) as mocked:
            res = adapter._execute('search', {'query': 'x'})
        self.assertEqual(res, {'ok': True})
        ns = mocked.return_value.execute.call_args[0][0]
        self.assertEqual(ns, 'test_mcp.search_code')

    def test_4_existing_source_shapes_keep_routing(self):
        """Mandate 4: react_bits/shadcn-style config keeps working end to end."""
        config = {
            'capability_map': {'search': 'search_code', 'get': 'get_file_contents'},
            'default_payload': {'repo': 'react-bits', 'owner': 'DavidHDev'},
            'normalization': {'component_id': 'path', 'name': 'name'},
        }
        adapter = make_adapter(capabilities='SEARCH,FETCH', config=config)
        envelope = {'content': [{'type': 'text',
                                  'text': json.dumps(
                                      {'items': [{'path': 'src/X.tsx', 'name': 'X'}]})}]}
        with router_mock(envelope) as mocked:
            out = adapter.search('animated text')
        call = mocked.return_value.execute.call_args
        self.assertEqual(call[0][0], 'test_mcp.search_code')
        args = call[0][1]['inputs']
        self.assertEqual(args['repo'], 'react-bits')       # source isolation intact
        self.assertEqual(args['owner'], 'DavidHDev')       # precedence intact
        self.assertEqual(args['query'], 'animated text')   # caller params present
        # Content envelope unwrapped + normalization map applied -> ComponentPackage
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].component_id, 'src/X.tsx')
        self.assertEqual(out[0].name, 'X')

    def test_5_no_concrete_tool_name_leaks_as_capability(self):
        """Mandate 5: declared tokens exactly; tool names never mixed in."""
        adapter = make_adapter(capabilities='SEARCH,FETCH',
                               discovered=('search_code', 'get_file_contents'))
        self.assertEqual(adapter.capabilities, ['SEARCH', 'FETCH'])
        self.assertNotIn('search_code', adapter.capabilities)
        self.assertNotIn('get_file_contents', adapter.capabilities)


class TestLegacyBehaviorsRefreshed(unittest.TestCase):
    """A–F equivalents against the post-ADR-0069 router path."""

    def setUp(self):
        self.adapter = make_adapter(
            capabilities='SEARCH',
            config={'capability_map': {'search': 'search_code'}})

    def test_a_params_wrapped_in_tools_call_shorthand(self):
        with router_mock() as mocked:
            self.adapter.search('test query')
        call = mocked.return_value.execute.call_args
        payload = call[0][1]
        self.assertEqual(payload['inputs'], {'query': 'test query'})

    def test_b_default_payload_merge(self):
        adapter = make_adapter(capabilities='SEARCH', config={
            'capability_map': {'search': 'search_code'},
            'default_payload': {'repo': 'DavidHDev/react-bits'}})
        with router_mock() as mocked:
            adapter.search('animated text')
        args = mocked.return_value.execute.call_args[0][1]['inputs']
        self.assertEqual(args['repo'], 'DavidHDev/react-bits')
        self.assertEqual(args['query'], 'animated text')

    def test_c_no_mutation_of_params_or_defaults(self):
        cfg = {'capability_map': {'search': 'search_code'},
               'default_payload': {'repo': 'DavidHDev/react-bits'}}
        adapter = make_adapter(capabilities='SEARCH', config=cfg)
        original = {'query': 'q', 'extra': {'a': 1}}
        with router_mock():
            adapter._execute('search', original)
        self.assertEqual(original, {'query': 'q', 'extra': {'a': 1}})
        self.assertEqual(adapter._default_payload, {'repo': 'DavidHDev/react-bits'})

    def test_d_invalid_default_payload_fails_safe(self):
        adapter = make_adapter(capabilities='SEARCH', config={
            'capability_map': {'search': 'search_code'},
            'default_payload': 'not-a-dict'})
        with router_mock() as mocked:
            adapter._execute('search', {'query': 'test'})
        args = mocked.return_value.execute.call_args[0][1]['inputs']
        self.assertEqual(adapter._default_payload, {})
        self.assertEqual(args, {'query': 'test'})

    def test_e_source_isolation_precedence(self):
        adapter = make_adapter(capabilities='SEARCH', config={
            'capability_map': {'search': 'search_code'},
            'default_payload': {'repo': 'DavidHDev/react-bits'}})
        with router_mock() as mocked:
            adapter._execute('search', {'query': 'test', 'repo': 'Other/Repo'})
        args = mocked.return_value.execute.call_args[0][1]['inputs']
        self.assertEqual(args['repo'], 'DavidHDev/react-bits')


if __name__ == '__main__':
    unittest.main()