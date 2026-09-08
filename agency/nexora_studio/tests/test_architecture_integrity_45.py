# -*- coding: utf-8 -*-
"""Phase 45 U6 â€” architecture-integrity assertions.

Proves (by static inspection of the addon tree) that no parallel CSF/DIP/
registry/ranking/routing architecture was introduced and that deferred
consolidation items remain untouched.
"""
import os
import re
import unittest

ROOT = r'D:\ODOO\custom-addons\agency\nexora_studio'
SF = os.path.join(ROOT, 'services', 'source_framework')


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def walk_sources():
    for base, _dirs, files in os.walk(os.path.join(ROOT, 'services', 'source_framework')):
        for f in files:
            if f.endswith('.py'):
                yield os.path.join(base, f)


class TestArchitectureIntegrity(unittest.TestCase):

    def test_exactly_one_csf_search_and_ranking(self):
        self.assertTrue(os.path.isfile(os.path.join(SF, 'search_engine.py')))
        src = read('services', 'source_framework', 'search_engine.py')
        self.assertEqual(src.count('class SearchEngine'), 1)
        rp = read('services', 'source_framework', 'component_ranking_pipeline.py')
        self.assertEqual(rp.count('class ComponentRankingPipeline'), 1)

    def test_single_dip_domain_model_layer(self):
        dm = read('services', 'source_framework', 'domain_models.py')
        for cls in ('ComponentPackage', 'RepositoryArtifact', 'Provenance',
                    'KnowledgeDocument', 'DesignAsset', 'BusinessData'):
            self.assertEqual(dm.count('class %s' % cls), 1, cls)
        # No competing domain-model layer elsewhere under services/.
        dupes = []
        for path in walk_sources():
            if path.endswith(('domain_models.py', 'adapters\\mcp_source_adapter.py')):
                continue
            with open(path, encoding='utf-8', errors='replace') as fh:
                txt = fh.read()
            if re.search(r'^class (ComponentPackage|RepositoryArtifact|BusinessData)\b', txt, re.M):
                dupes.append(path)
        self.assertEqual(dupes, [])

    def test_two_sanctioned_router_construction_sites_only(self):
        hits = []
        for base, dirs, files in os.walk(os.path.join(ROOT, 'services')):
            for f in files:
                if not f.endswith('.py'):
                    continue
                p = os.path.join(base, f)
                with open(p, encoding='utf-8', errors='replace') as fh:
                    txt = fh.read()
                # Strip comments so prose mentions don't count as code.
                txt = re.sub(r'#.*', '', txt)
                if 'build_canonical_router' in txt or \
                        re.search(r'UniversalCapabilityRouter\(', txt):
                    hits.append(p.replace(ROOT + os.sep, '').replace(os.sep, '/'))
        allowed = {
            'services/connector/integration/bootstrap.py',
            'services/generation/core/generation_runtime.py',
            'services/capabilities/router.py',
            # Sanctioned consumers of the canonical router:
            'services/source_framework/adapters/mcp_source_adapter.py',
            'models/mcp_model_providers.py',
            'controllers/connector_api.py',
        }
        unexpected = [h for h in hits if h not in allowed]
        self.assertEqual(unexpected, [],
                         'unsanctioned router construction appeared: %s' % unexpected)

    def test_no_direct_http_clients_in_source_framework(self):
        banned = re.compile(r'^\s*(import requests|import httpx|import aiohttp|from requests|from httpx)', re.M)
        offenders = []
        for path in walk_sources():
            with open(path, encoding='utf-8', errors='replace') as fh:
                if banned.search(fh.read()):
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_no_second_3d_registry_or_engine(self):
        banned_names = ('ThreeDRegistry', 'ThreeDComponentService',
                        'ThreeDRankingEngine', 'ThreeDDiscoveryEngine',
                        'ThreeDProviderRegistry')
        found = []
        for base, _d, files in os.walk(os.path.join(ROOT, 'services')):
            for f in files:
                if not f.endswith('.py'):
                    continue
                p = os.path.join(base, f)
                with open(p, encoding='utf-8', errors='replace') as fh:
                    txt = fh.read()
                for n in banned_names:
                    if re.search(r'class\s+%s\b' % n, txt):
                        found.append((p, n))
        self.assertEqual(found, [])

    def test_source_registry_remains_the_registration_authority(self):
        m = read('models', 'source_framework', 'source_registry.py')
        self.assertIn("_name = 'nexora.source_registry'", m)
        # exactly one Odoo model defines the CSF registration store
        count = 0
        models_dir = os.path.join(ROOT, 'models')
        for base, _d, files in os.walk(models_dir):
            for f in files:
                if not f.endswith('.py'):
                    continue
                p = os.path.join(base, f)
                with open(p, encoding='utf-8') as fh:
                    if "_name = 'nexora.source_registry'" in fh.read():
                        count += 1
        self.assertEqual(count, 1)

    def test_deferred_items_untouched(self):
        # ProviderManager non-MCP branch still a documented stub (deferred).
        pm = read('services', 'source_framework', 'provider_manager.py')
        self.assertIn('# Load existing non-MCP adapters', pm)
        # PlanningEngine must reuse GenerationRuntime's canonical router.
        pe = read('services', 'generation', 'engines', 'planning_engine.py')
        self.assertNotIn('UniversalCapabilityRouter(', pe)
        self.assertIn('runtime.orchestrator.execute_prepared_plan(plan)', pe)
        # Figma remnant untouched (deferred).
        self.assertTrue(os.path.isfile(os.path.join(
            ROOT, 'services', 'providers', 'component', 'figma_adapter.py')))

    def test_gosom_integration_stays_off_architecture(self):
        """Phase 46.2 / ADR-0073: the Gosom business-location connector is a
        thin MCP shim + declarative registration — never a parallel CSF/DIP
        architecture and never a ComponentPackage producer."""
        shim = read('mcp_shims', 'gosom_mcp_server.py')
        # Pure stdio shim: no Odoo coupling, no registry/ranking classes.
        self.assertNotIn('import odoo', shim)
        self.assertNotIn('from odoo', shim)
        for banned in ('SearchEngine', 'ComponentRankingPipeline',
                       'DiscoveryEngine', 'ProviderRegistry',
                       'CapabilityRegistry', 'ConnectorRegistry'):
            self.assertNotIn('class %s' % banned, shim)
        # Declarative registration only, single semantic capability.
        # (Record lives in connector_gosom_data.xml — after the connector —
        # so the Many2one ref resolves on fresh installs.)
        cg = read('data', 'connector_gosom_data.xml')
        self.assertIn('gosom_business', cg)
        self.assertRegex(
            cg, r'<field name="capabilities">BUSINESS_SEARCH</field>')
        # Adapter contract: business search yields BusinessData only.
        adapter = read('services', 'source_framework', 'adapters',
                       'mcp_source_adapter.py')
        sb = adapter[adapter.index('def search_businesses'):]
        sb = sb[:sb.index('def get_component')]
        self.assertIn('List[BusinessData]', sb)
        self.assertNotIn('ComponentPackage', sb)
        self.assertNotIn('discover_components', sb)


if __name__ == '__main__':
    unittest.main()
