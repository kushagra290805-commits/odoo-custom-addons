# -*- coding: utf-8 -*-
"""Phase 45 U2 — GitHub repository intelligence over existing github_mcp.

Proves: source registration shape, MCP result → RepositoryArtifact mapping,
provenance preservation, NO ComponentPackage fabrication, canonical router
usage only.
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from odoo.addons.nexora_studio.services.source_framework.adapters.mcp_source_adapter import McpSourceAdapter
from odoo.addons.nexora_studio.services.source_framework.domain_models import (
    ComponentPackage, RepositoryArtifact)

BOOTSTRAP = 'odoo.addons.nexora_studio.services.connector.integration.bootstrap'

CONFIG = {
    'capability_map': {
        'repo_search': 'search_repositories',
        'code_search': 'search_code',
        'fetch_file': 'get_file_contents',
    },
    'normalization': {'artifact_id': 'id', 'path': 'full_name'},
}

REPO_ENVELOPE = {'content': [{'type': 'text', 'text': json.dumps({'items': [
    {'id': 1001, 'full_name': 'pmndrs/drei', 'html_url': 'https://github.com/pmndrs/drei',
     'description': 'useful helpers for react-three-fiber', 'language': 'TypeScript'},
    {'id': 1002, 'full_name': 'pmndrs/react-three-fiber',
     'html_url': 'https://github.com/pmndrs/react-three-fiber'},
]})}]}


def make_adapter():
    from test_mcp_source_adapter import FakeEnv, _Rec
    connector = _Rec(connector_id='github_mcp',
                     capability_ids=[_Rec(technical_name=t) for t in
                                     ('search_repositories', 'search_code', 'get_file_contents')])
    row = _Rec(technical_name='github_repo_intelligence',
               capabilities='REPOSITORY_INTELLIGENCE,FETCH',
               config_json=json.dumps(CONFIG))
    env = FakeEnv(connector, row, list(connector.capability_ids and
                                       [t.technical_name for t in connector.capability_ids]))
    with patch(BOOTSTRAP + '.get_connector_runtime', return_value=object()):
        return McpSourceAdapter(connector_id=7, env=env)


class TestGitHubRepositoryIntelligence(unittest.TestCase):

    def setUp(self):
        self.adapter = make_adapter()

    def test_source_registration_shape(self):
        """Source declares REPOSITORY_INTELLIGENCE/FETCH; no component tokens."""
        self.assertEqual(self.adapter.capabilities, ['REPOSITORY_INTELLIGENCE', 'FETCH'])
        self.assertNotIn('SEARCH', self.adapter.capabilities)
        # Concrete tools stay internal to execution.
        self.assertIn('search_repositories', self.adapter._discovered_tools())

    def test_mcp_result_maps_to_repository_artifacts(self):
        with patch(BOOTSTRAP + '.build_canonical_router') as br:
            ret = MagicMock()
            ret.success = True
            ret.result = REPO_ENVELOPE
            ret.logs = []
            br.return_value.execute.return_value = ret

            artifacts = self.adapter.fetch_repository_artifacts(
                intent='repo_search', params={'query': 'react-three-fiber'})

        ns = br.return_value.execute.call_args[0][0]
        self.assertEqual(ns, 'github_mcp.search_repositories')
        self.assertEqual(len(artifacts), 2)
        self.assertTrue(all(isinstance(a, RepositoryArtifact) for a in artifacts))
        self.assertNotIn(ComponentPackage, {type(a) for a in artifacts})
        drei = next(a for a in artifacts if a.artifact_id == '1001')
        self.assertEqual(drei.path, 'pmndrs/drei')
        self.assertEqual(drei.type, 'file')

    def test_provenance_preserved(self):
        with patch(BOOTSTRAP + '.build_canonical_router') as br:
            ret = MagicMock()
            ret.success = True
            ret.result = REPO_ENVELOPE
            ret.logs = []
            br.return_value.execute.return_value = ret
            artifacts = self.adapter.fetch_repository_artifacts(intent='repo_search')

        drei = next(a for a in artifacts if a.artifact_id == '1001')
        self.assertIsNotNone(drei.provenance)
        self.assertEqual(drei.provenance.provider, 'github_repo_intelligence')
        self.assertEqual(drei.provenance.repository, 'pmndrs/drei')
        self.assertTrue(drei.provenance.import_source.startswith('csf:'))

    def test_no_componentpackage_fabrication_on_unmappable_items(self):
        """Items lacking artifact identity are skipped, never forced into components."""
        envelope = {'content': [{'type': 'text', 'text': json.dumps({'items': [
            {'unrelated': 'payload'},
        ]})}]}
        with patch(BOOTSTRAP + '.build_canonical_router') as br:
            ret = MagicMock()
            ret.success = True
            ret.result = envelope
            ret.logs = []
            br.return_value.execute.return_value = ret
            artifacts = self.adapter.fetch_repository_artifacts(intent='repo_search')
        self.assertEqual(artifacts, [])

    def test_canonical_router_usage_only(self):
        """Execution must go through build_canonical_router — no other transport."""
        with patch(BOOTSTRAP + '.build_canonical_router') as br:
            self.adapter.fetch_repository_artifacts(intent='repo_search')
        br.assert_called_once()
        br.return_value.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
