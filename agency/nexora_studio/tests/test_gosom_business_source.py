# -*- coding: utf-8 -*-
"""Phase 46 — Gosom business-location intelligence tests (ADR-0073).

DB-free unit tests covering:
  1. Shim pure functions (validate_bounds, shape_place, parse_places_csv)
  2. McpSourceAdapter.search_businesses normalization & provenance
  3. Capability discoverability (BUSINESS_SEARCH declared on source_registry)
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter import McpSourceAdapter
from odoo.addons.nexora_studio.services.source_framework.domain_models import BusinessData, Provenance

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


def make_gosom_adapter(config=None, discovered=('business_search',)):
    connector = _Rec(
        connector_id='gosom_mcp',
        capability_ids=[_Rec(technical_name=t) for t in discovered])
    row = _Rec(
        technical_name='gosom_business',
        capabilities='BUSINESS_SEARCH',
        config_json=json.dumps(config) if config is not None else None)
    env = FakeEnv(connector, row, discovered)
    with patch(BOOTSTRAP + '.get_connector_runtime', return_value=object()):
        return McpSourceAdapter(connector_id=200, env=env)


def router_mock(result_data=None, success=True):
    router = MagicMock()
    ret = MagicMock()
    ret.success = success
    ret.result = result_data if result_data is not None else {}
    ret.logs = []
    router.execute.return_value = ret
    return patch(BOOTSTRAP + '.build_canonical_router', return_value=router)


# ========================================================== Shim tests ======
class TestShimPureFunctions(unittest.TestCase):
    """Tests for gosom_mcp_server pure functions (no network, no MCP)."""

    def setUp(self):
        import sys
        import os
        shim_dir = os.path.join(
            os.path.dirname(__file__), '..', 'mcp_shims')
        if shim_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(shim_dir))
        from gosom_mcp_server import validate_bounds, shape_place, parse_places_csv
        self.validate_bounds = validate_bounds
        self.shape_place = shape_place
        self.parse_places_csv = parse_places_csv

    # -- validate_bounds --
    def test_valid_single_query(self):
        self.validate_bounds(['pizza near me'], 5)

    def test_valid_max_queries(self):
        self.validate_bounds(['a', 'b', 'c', 'd', 'e'], 21)

    def test_empty_queries_raises(self):
        with self.assertRaises(ValueError):
            self.validate_bounds([], 5)

    def test_six_queries_raises(self):
        with self.assertRaises(ValueError):
            self.validate_bounds(['q'] * 6, 5)

    def test_empty_string_query_raises(self):
        with self.assertRaises(ValueError):
            self.validate_bounds(['  '], 5)

    def test_long_query_raises(self):
        with self.assertRaises(ValueError):
            self.validate_bounds(['x' * 241], 5)

    def test_limit_22_raises(self):
        with self.assertRaises(ValueError):
            self.validate_bounds(['x'], 22)

    # -- shape_place --
    def test_shape_core_fields(self):
        row = {'title': 'Acme', 'place_id': 'P1', 'phone': '555'}
        result = self.shape_place(row, False)
        self.assertEqual(result['_type'], 'business_data')
        self.assertEqual(result['category'], 'business_place')
        self.assertEqual(result['data_id'], 'P1')
        self.assertEqual(result['payload']['title'], 'Acme')
        self.assertEqual(result['payload']['phone'], '555')
        self.assertNotIn('user_reviews', result['payload'])

    def test_shape_optional_fields_included(self):
        row = {'title': 'B', 'place_id': 'P2', 'review_rating': '4.5',
               'review_count': '120'}
        result = self.shape_place(row, False)
        self.assertEqual(result['payload']['review_rating'], '4.5')
        self.assertEqual(result['payload']['review_count'], '120')

    def test_shape_fragile_fields_opt_in(self):
        row = {'title': 'C', 'place_id': 'P3', 'user_reviews': '[rev]'}
        result_fragile = self.shape_place(row, True)
        self.assertEqual(result_fragile['payload']['user_reviews'], '[rev]')
        result_plain = self.shape_place(row, False)
        self.assertNotIn('user_reviews', result_plain['payload'])

    def test_shape_fallback_data_id(self):
        row = {'title': 'D', 'cid': 'CID1'}
        result = self.shape_place(row, False)
        self.assertEqual(result['data_id'], 'CID1')

    def test_shape_empty_row(self):
        result = self.shape_place({}, False)
        self.assertEqual(result['_type'], 'business_data')
        self.assertEqual(result['category'], 'business_place')
        self.assertIsInstance(result['payload'], dict)

    # -- parse_places_csv --
    def test_parse_csv(self):
        csv_text = 'title,place_id,phone\nCafe,P3,123\nBar,P4,456'
        rows = self.parse_places_csv(csv_text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['title'], 'Cafe')
        self.assertEqual(rows[1]['place_id'], 'P4')

    def test_parse_csv_empty(self):
        rows = self.parse_places_csv('')
        self.assertEqual(rows, [])

    # -- DEFAULT_LANG --
    def test_default_lang_is_en(self):
        import gosom_mcp_server as g
        self.assertEqual(g.DEFAULT_LANG, 'en')


# ====================================================== Adapter tests ========
class TestSearchBusinessesNormalization(unittest.TestCase):
    """McpSourceAdapter.search_businesses produces BusinessData with provenance."""

    def setUp(self):
        self.adapter = make_gosom_adapter(config={
            'capability_map': {'business_search': 'business_search'}})

    def test_returns_list_of_business_data(self):
        shim_result = json.dumps([
            {'_type': 'business_data', 'data_id': 'P1',
             'category': 'business_place',
             'payload': {'title': 'Acme', 'phone': '555'}},
        ])
        with router_mock(shim_result) as mocked:
            results = self.adapter.search_businesses(['pizza near me'])
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], BusinessData)
        self.assertEqual(results[0].data_id, 'P1')

    def test_provenance_attached(self):
        shim_result = json.dumps([
            {'_type': 'business_data', 'data_id': 'P2',
             'category': 'business_place',
             'payload': {'title': 'Bakery'}},
        ])
        with router_mock(shim_result):
            results = self.adapter.search_businesses(['bakery nearby'])
        self.assertIsInstance(results[0].provenance, Provenance)
        self.assertEqual(results[0].provenance.provider, 'gosom_business')

    def test_single_dict_result_wrapped(self):
        shim_result = {'_type': 'business_data', 'data_id': 'P3',
                       'category': 'business_place',
                       'payload': {'title': 'Cafe'}}
        with router_mock(shim_result):
            results = self.adapter.search_businesses(['cafe'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].data_id, 'P3')

    def test_empty_result(self):
        with router_mock(json.dumps([])):
            results = self.adapter.search_businesses(['nonexistent query'])
        self.assertEqual(results, [])

    def test_invalid_json_fallback(self):
        with router_mock('not-valid-json'):
            with self.assertRaises(RuntimeError):
                self.adapter.search_businesses(['query'])

    def test_iserror_envelope_raises(self):
        """Shim-side errors (bounds/job failures) must surface, not vanish."""
        envelope = {'content': [{'type': 'text',
                                 'text': 'queries exceeds cap of 5 per request'}],
                    'isError': True}
        with router_mock(envelope):
            with self.assertRaises(RuntimeError) as ctx:
                self.adapter.search_businesses(['q'] * 6)
        self.assertIn('queries exceeds cap', str(ctx.exception))

    def test_real_mcp_envelope_shape(self):
        """Canonical tools.call envelope (provider contract) normalizes."""
        envelope = {'content': [{'type': 'text', 'text': json.dumps([
            {'_type': 'business_data', 'data_id': 'P9',
             'category': 'business_place',
             'payload': {'title': 'Envelope Cafe'}}])}],
                    'isError': False}
        with router_mock(envelope):
            results = self.adapter.search_businesses(['cafe'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].data_id, 'P9')
        self.assertEqual(results[0].provenance.provider, 'gosom_business')

    def test_no_queries_param_passes_through(self):
        shim_result = json.dumps([
            {'_type': 'business_data', 'data_id': 'P4',
             'category': 'business_place', 'payload': {'title': 'X'}},
        ])
        with router_mock(shim_result) as mocked:
            self.adapter.search_businesses(
                ['q1', 'q2'], limit_per_query=10, lang='de',
                include_reviews=True)
        call_args = mocked.return_value.execute.call_args[0]
        payload = call_args[1]['inputs']
        self.assertEqual(payload['queries'], ['q1', 'q2'])
        self.assertEqual(payload['limit_per_query'], 10)
        self.assertEqual(payload['lang'], 'de')
        self.assertTrue(payload['include_reviews'])


class TestCapabilityDiscoverability(unittest.TestCase):
    """BUSINESS_SEARCH capability is declared and discoverable."""

    def test_capability_declared(self):
        adapter = make_gosom_adapter()
        self.assertEqual(adapter.capabilities, ['BUSINESS_SEARCH'])

    def test_discoverable_by_business_search(self):
        from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager
        adapter = make_gosom_adapter()
        pm = ProviderManager(env=None)
        pm.register_adapter('gosom_business', adapter)
        self.assertIn('gosom_business', pm.get_capable_providers('BUSINESS_SEARCH'))

    def test_not_discoverable_by_wrong_capability(self):
        from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager
        adapter = make_gosom_adapter()
        pm = ProviderManager(env=None)
        pm.register_adapter('gosom_business', adapter)
        self.assertNotIn('gosom_business', pm.get_capable_providers('SEARCH'))


if __name__ == '__main__':
    unittest.main()
