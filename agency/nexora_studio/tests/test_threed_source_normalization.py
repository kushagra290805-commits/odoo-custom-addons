# -*- coding: utf-8 -*-
"""Phase 45 U3 — canonical 3D artifact ingestion/normalization contract.

Proves the config-driven qualification chain: bare repository/search results
never become ComponentPackages; only qualifying artifacts (real R3F/Drei
component code or scene assets) do, carrying ADR-0064 metadata.
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter import McpSourceAdapter
from odoo.addons.nexora_studio.services.source_framework.domain_models import (
    METADATA_THREE_D_SCENE,
    METADATA_RENDERER_EXPECTATION,
    ComponentPackage,
)

BOOTSTRAP = 'odoo.addons.nexora_studio.services.connector.integration.bootstrap'

QUALIFICATION = {
    'candidate_path_pattern': r'\.(tsx|jsx)$',
    'content_required_any': ['@react-three/fiber'],
    'required_dependencies': ['three', '@react-three/fiber'],
    'fetch_intent': 'fetch_file',
    'metadata': {'three_d_scene': True, 'renderer_expectation': 'react_three_fiber'},
}
CONFIG = {
    'capability_map': {
        'discover': 'search_code',
        'fetch_file': 'get_file_contents',
    },
    'discovery': {
        'intent': 'discover',
        'query': 'react-three-fiber hero language:tsx org:pmndrs',
    },
    'qualification': QUALIFICATION,
}

GOOD_CODE = 'import { Canvas } from "@react-three/fiber";\nexport const Hero = () => <Canvas/>;'
BAD_CODE = 'export default function Button() { return <button/>; }'


def make_adapter():
    from test_mcp_source_adapter import FakeEnv, _Rec
    connector = _Rec(connector_id='github_mcp',
                     capability_ids=[_Rec(technical_name=t) for t in
                                     ('search_code', 'get_file_contents')])
    row = _Rec(technical_name='threed_component_library',
               capabilities='COMPONENT_SOURCE,SEARCH,FETCH',
               config_json=json.dumps(CONFIG))
    env = FakeEnv(connector, row, ['search_code', 'get_file_contents'])
    with patch(BOOTSTRAP + '.get_connector_runtime', return_value=object()):
        return McpSourceAdapter(connector_id=9, env=env)


def script_router(adapter, search_items, contents_by_path):
    """Router replacement: build_canonical_router(env) returns `router`,
    whose .execute serves discovery results then per-path file contents."""
    router = MagicMock()

    def execute(ns, payload=None, context=None):
        tool = ns.split('.', 1)[1]
        if tool == 'search_code':
            ret = MagicMock()
            ret.success = True
            ret.logs = []
            ret.result = {'content': [{'type': 'text', 'text': json.dumps(
                {'items': search_items})}]}
            return ret
        if tool == 'get_file_contents':
            path = payload['inputs']['path']
            content = contents_by_path.get(path, BAD_CODE)
            ret = MagicMock()
            ret.success = True
            ret.logs = []
            ret.result = {'content': [{'type': 'text', 'text': content}]}
            return ret
        raise AssertionError('unexpected tool ' + tool)

    router.execute.side_effect = execute
    return patch(BOOTSTRAP + '.build_canonical_router', return_value=router)


class TestThreeDIngestionContract(unittest.TestCase):

    def test_qualifying_artifact_becomes_package_with_adr0064_metadata(self):
        adapter = make_adapter()
        items = [{'path': 'hero/HeroScene.tsx', 'name': 'HeroScene',
                  'dependencies': {'three': '^0.16', '@react-three/fiber': '^8'},
                  'repository': 'pmndrs/drei'}]
        contents = {'hero/HeroScene.tsx': GOOD_CODE}
        with script_router(adapter, items, contents):
            packages = adapter.discover_components()
        self.assertEqual(len(packages), 1)
        pkg = packages[0]
        self.assertIsInstance(pkg, ComponentPackage)
        self.assertEqual(pkg.component_id, 'hero/HeroScene.tsx')
        self.assertTrue(pkg.metadata[METADATA_THREE_D_SCENE] is True)
        self.assertEqual(pkg.metadata[METADATA_RENDERER_EXPECTATION], 'react_three_fiber')
        self.assertIn(GOOD_CODE, pkg.metadata['source_code'])
        self.assertIsNotNone(pkg.provenance)
        self.assertEqual(pkg.provenance.repository, 'pmndrs/drei')
        dep_names = sorted(d['name'] for d in pkg.dependencies)
        self.assertEqual(dep_names, ['@react-three/fiber', 'three'])

    def test_bare_repository_result_never_becomes_package(self):
        adapter = make_adapter()
        # Repository-level shell (no code path match) must be filtered out.
        items = [{'full_name': 'pmndrs/drei', 'description': 'helpers'}]
        with script_router(adapter, items, {}):
            packages = adapter.discover_components()
        self.assertEqual(packages, [])

    def test_non_3d_content_rejected_by_content_gate(self):
        adapter = make_adapter()
        items = [{'path': 'ui/Button.tsx', 'name': 'Button'}]
        with script_router(adapter, items, {'ui/Button.tsx': BAD_CODE}):
            packages = adapter.discover_components()
        self.assertEqual(packages, [])

    def test_missing_dependencies_rejected_when_info_available(self):
        adapter = make_adapter()
        items = [{'path': 'hero/HeroScene.tsx', 'name': 'HeroScene',
                  'dependencies': {'three': '^0.16'}}]  # fiber missing
        with script_router(adapter, items, {'hero/HeroScene.tsx': GOOD_CODE}):
            packages = adapter.discover_components()
        self.assertEqual(packages, [])

    def test_no_dependency_info_means_no_invention_but_content_gate_applies(self):
        """Without dependency info the gate is skipped (nothing invented);
        the content gate still decides."""
        adapter = make_adapter()
        items = [{'path': 'hero/Raw.tsx', 'name': 'Raw'}]  # no dependencies key
        contents = {'hero/Raw.tsx': 'import { Canvas } from "@react-three/fiber"; raw sketch'}
        with script_router(adapter, items, contents):
            packages = adapter.discover_components()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].dependencies, [])


if __name__ == '__main__':
    unittest.main()
