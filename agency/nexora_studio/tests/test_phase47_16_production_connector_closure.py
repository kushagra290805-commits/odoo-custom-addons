# -*- coding: utf-8 -*-
"""Phase 47.16 — Required production connector / MCP integration closure.

Proves the canonical chain for every production-required integration using
EXISTING owners only:

    connector -> source_registry row -> McpSourceAdapter -> canonical router
    -> DIP artifact -> existing generation consumer

Implemented this phase:
    tavily_mcp -> tavily_knowledge (SEARCH) -> tavily_search tool
        -> text_result_format parsing -> KnowledgeDocument
        -> KnowledgeEnrichmentEngine -> artifact.knowledge

Already integrated (verified here at the matrix level; deeper behavior is
covered by test_github_repo_intelligence / test_threed_source_normalization /
test_gosom_business_source / test_phase47_7_artifact_consumers):
    github_mcp  -> react_bits / shadcn / github_repo_intelligence /
                   threed_component_library (SEARCH / FETCH /
                   REPOSITORY_INTELLIGENCE / COMPONENT_SOURCE)
    gosom_mcp   -> gosom_business (BUSINESS_SEARCH) -> BusinessData
                   -> BusinessResearchEngine

The ONLY externally-mocked seam in these tests is the MCP transport
(build_canonical_router) — the exact seam already proven live by the
2026-08-26 handshake/tool-discovery tests. Everything else — source rows,
adapter, tool-name resolution, discovered-tools guard, text parsing,
normalization, ProviderManager capability dispatch and engine consumption —
is real production code against the real registry.

No parallel registry/router/engine/pipeline is created; connectors remain
disabled in steady state (no lifecycle side effects).
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager
from odoo.addons.nexora_studio.services.source_framework.domain_models import (
    KnowledgeDocument, BusinessData,
)
from odoo.addons.nexora_studio.services.generation.engines.knowledge_enrichment_engine import (
    KnowledgeEnrichmentEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.business_research_engine import (
    BusinessResearchEngine,
)
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    WebsiteGenerationArtifact, RequirementModel,
)

ROUTER_PATH = ('odoo.addons.nexora_studio.services.connector.integration.bootstrap'
               '.build_canonical_router')

# Realistic tavily_search text response (shape captured from the LIVE
# tavily-mcp server on 2026-08-30; content abbreviated). The tool returns a
# human-readable "Field: value" report, NOT JSON — this is exactly what the
# text_result_format config parses.
TAVILY_LIVE_TEXT = """Detailed Results:

Title: Top 20 Best Dental Websites of 2026 (Design + SEO)
ID: adb49d-00
URL: https://www.lassomd.com/blog/top-10-best-dental-websites
Content: Well-designed dental clinic websites allow potential patients to learn about your practice from the comfort of their own homes.
Modern dental websites focus on sleek, professional, patient-friendly layouts with clear calls-to-action and online booking.

Title: 20 Best Dental Websites of 2026 | Design Examples & Data
ID: 06a627-02
URL: https://delmain.co/blog/best-dental-websites
Content: Modern dental websites focus on mobile-first layouts, trust builders and transparent pricing.
Performance and accessibility directly affect patient conversions."""

GOSOM_JSON = json.dumps([
    {"data_id": "gosom:abc123", "category": "business_place",
     "payload": {"title": "Acme Dental", "phone": "+1234567890",
                 "address": "1 Main St"}},
    {"data_id": "gosom:def456", "category": "business_place",
     "payload": {"title": "Acme Orthodontics", "website": "https://example.com"}},
])


def _mcp_text_envelope(text):
    return {'content': [{'type': 'text', 'text': text}], 'isError': False}


class _FakeRouter:
    """Stands in for the canonical router at the MCP-transport seam only."""

    def __init__(self, mapping=None, fail_namespaces=()):
        self.mapping = mapping or {}
        self.fail_namespaces = set(fail_namespaces)
        self.calls = []

    def execute(self, namespace, payload, context=None):
        self.calls.append((namespace, payload, context))
        if namespace in self.fail_namespaces:
            return SimpleNamespace(success=False, result=None,
                                   logs=['simulated MCP failure'])
        envelope = self.mapping.get(namespace)
        if envelope is None:
            envelope = _mcp_text_envelope('[]')
        return SimpleNamespace(success=True, result=envelope, logs=[])

    def namespaces(self):
        return [c[0] for c in self.calls]


def _tavily_router():
    return _FakeRouter({
        'tavily_mcp.tavily_search': _mcp_text_envelope(TAVILY_LIVE_TEXT),
    })


def _requirements(domain='dental clinics', audience='prospective patients',
                  goals=None, branding=None):
    return RequirementModel(
        domain=domain, target_audience=audience,
        goals=goals if goals is not None else ['Showcase services'],
        branding=branding if branding is not None else {})


def _runtime(env, ai=None):
    rt = SimpleNamespace(env=env)
    ai = ai if ai is not None else MagicMock()
    ai.generate.return_value = {'knowledge': {}}
    rt.ai = ai
    return rt


def _src(rel):
    with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r',
              encoding='utf-8', errors='ignore') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# TASK 1/2 — production capability matrix (executable, against the real DB)
# ---------------------------------------------------------------------------
class TestU4716CapabilityMatrix(unittest.TestCase):
    """Locks the connector->source->capability->consumer matrix in code."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def _pm(self):
        pm = ProviderManager(self.env)
        pm.load_from_registry()
        return pm

    def test_source_rows_and_provider_matrix(self):
        pm = self._pm()
        providers = set(pm.adapters.keys())
        # github_mcp-backed sources + gosom + tavily — all load through the
        # SAME McpSourceAdapter with real registry rows.
        self.assertEqual(providers, {
            'react_bits', 'shadcn', 'github_repo_intelligence',
            'threed_component_library', 'gosom_business', 'tavily_knowledge',
        })
        # Capability-driven dispatch contracts:
        self.assertEqual(
            sorted(pm.get_capable_providers('SEARCH')),
            ['react_bits', 'shadcn', 'tavily_knowledge',
             'threed_component_library'])
        self.assertEqual(pm.get_capable_providers('BUSINESS_SEARCH'),
                         ['gosom_business'])
        self.assertEqual(pm.get_capable_providers('REPOSITORY_INTELLIGENCE'),
                         ['github_repo_intelligence'])
        self.assertEqual(pm.get_capable_providers('COMPONENT_SOURCE'),
                         ['threed_component_library'])

    def test_tavily_source_row_contract(self):
        row = self.env['nexora.source_registry'].search(
            [('technical_name', '=', 'tavily_knowledge')], limit=1)
        self.assertTrue(row, 'tavily_knowledge source row must exist')
        self.assertEqual(row.connector_id.connector_id, 'tavily_mcp')
        self.assertEqual(row.capabilities, 'SEARCH')
        self.assertTrue(row.is_mcp)
        cfg = json.loads(row.config_json)
        self.assertEqual(cfg['capability_map'],
                         {'search': 'tavily_search'})
        self.assertEqual(cfg['text_result_format']['block_start_field'],
                         'Title')
        self.assertEqual(cfg['normalization'],
                         {'document_id': 'URL', 'title': 'Title',
                          'content': 'Content'})

    def test_tavily_tool_is_discovered_on_connector(self):
        tools = self.env['nexora.mcp_discovered_tool'].search(
            [('connector_id.connector_id', '=', 'tavily_mcp')])
        names = {t.tool_name for t in tools}
        self.assertIn('tavily_search', names,
                      'tavily_search must be in the discovered tool set')

    def test_transport_only_connectors_have_no_source_rows(self):
        """context7 / firecrawl / penpot are transport-verified but have NO
        source row and therefore NO generation consumer (classification D/B).
        This lock prevents silently assuming they are integrated."""
        for technical in ('context7', 'firecrawl', 'penpot'):
            rows = self.env['nexora.source_registry'].search(
                [('technical_name', 'like', technical)])
            self.assertFalse(rows,
                             '%s must not have a source row until a consumer '
                             'gap is closed deliberately' % technical)
        pm = self._pm()
        for pid in ('context7', 'firecrawl', 'penpot', 'context7_mcp',
                    'firecrawl_mcp', 'penpot_mcp'):
            self.assertNotIn(pid, pm.adapters)

    def test_existing_consumer_wiring_is_reachable_from_pipeline(self):
        """The four existing consumer engines reference the source framework
        through the canonical ProviderManager — no tavily-specific branching
        anywhere in the generation engines (github/gosom appear only in
        historical docstrings, never in code branches)."""
        for rel in ('services/generation/engines/'
                    'knowledge_enrichment_engine.py',
                    'services/generation/engines/business_research_engine.py',
                    'services/generation/engines/component_discovery_engine.py',
                    'services/generation/engines/asset_engine.py'):
            src = _src(rel)
            self.assertIn('ProviderManager', src, rel)
            self.assertNotIn('tavily', src.lower(), rel)


# ---------------------------------------------------------------------------
# TASK 3/6 — tavily -> SEARCH -> KnowledgeDocument -> consumer (real value)
# ---------------------------------------------------------------------------
class TestU4716TavilyKnowledgeChain(unittest.TestCase):
    """source row -> adapter -> (MCP seam) -> KnowledgeDocument."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def _pm(self):
        pm = ProviderManager(self.env)
        pm.load_from_registry()
        return pm

    def test_search_returns_knowledge_documents(self):
        pm = self._pm()
        router = _tavily_router()
        with patch(ROUTER_PATH, return_value=router):
            results = pm.route_request(
                'tavily_knowledge', 'search',
                'dental clinic website best practices')
        self.assertTrue(all(isinstance(r, KnowledgeDocument) for r in results),
                        'every tavily result must be a KnowledgeDocument')
        self.assertEqual(len(results), 2)
        first = results[0]
        self.assertEqual(first.document_id,
                         'https://www.lassomd.com/blog/top-10-best-dental-websites')
        self.assertEqual(first.title,
                         'Top 20 Best Dental Websites of 2026 (Design + SEO)')
        self.assertIn('Well-designed dental clinic websites', first.content)
        self.assertIn('Modern dental websites', first.content,
                      'multi-line content must be preserved')
        self.assertEqual(results[1].document_id,
                         'https://delmain.co/blog/best-dental-websites')

    def test_canonical_tool_resolution_and_payload(self):
        pm = self._pm()
        router = _tavily_router()
        with patch(ROUTER_PATH, return_value=router):
            pm.route_request('tavily_knowledge', 'search', 'implants SEO')
        self.assertEqual(router.namespaces(), ['tavily_mcp.tavily_search'],
                         'the semantic SEARCH intent must resolve to the '
                         'tavily_search tool via the capability_map')
        _, payload, _ = router.calls[0]
        args = payload['inputs']
        self.assertEqual(args['query'], 'implants SEO')
        self.assertEqual(args['max_results'], 5,
                         'default_payload must be merged into the tool call')

    def test_engine_consumes_tavily_documents(self):
        """Full generation-side consumption: the REAL KnowledgeEnrichmentEngine
        builds the REAL ProviderManager from the registry; only the MCP seam
        is faked. Documents must land in artifact.knowledge."""
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements())
        router = _tavily_router()
        engine = KnowledgeEnrichmentEngine(MagicMock())
        with patch(ROUTER_PATH, return_value=router):
            result = engine.execute(artifact, _runtime(self.env))
        self.assertTrue(result.success, result.error)
        knowledge = result.artifact.knowledge
        docs = knowledge.get('knowledge_documents') or []
        self.assertEqual(len(docs), 2,
                         'tavily documents must be consumed into knowledge')
        self.assertEqual(docs[0]['document_id'],
                         'https://www.lassomd.com/blog/top-10-best-dental-websites')
        self.assertEqual(docs[0]['title'],
                         'Top 20 Best Dental Websites of 2026 (Design + SEO)')
        self.assertIn('dental clinic websites', docs[0]['content'])
        sources = knowledge.get('knowledge_sources') or {}
        self.assertIn('tavily_knowledge', sources.get('providers_used', []))
        # Pre-existing isolated behavior: threed_component_library declares
        # SEARCH but its capability_map has no 'search' intent, so its
        # knowledge search errors are isolated (never fatal) — the phase
        # preserves this provider-failure semantics. The tavily path itself
        # must carry NO provider error.
        tavily_errors = [e for e in sources.get('provider_errors', [])
                         if e.get('provider') == 'tavily_knowledge']
        self.assertEqual(tavily_errors, [],
                         'the tavily integration must be error-free')
        self.assertIn(sources.get('status'),
                      ('completed', 'partially_completed'),
                      'isolated third-party provider errors may downgrade '
                      'the aggregate status but never fail the stage')

    def test_demand_driven_query_derived_from_requirements(self):
        """No requirements context -> no tavily invocation at all (the SEARCH
        path is guarded on the requirements-derived query; the repository
        path is capability-driven and fires independently)."""
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(domain='', audience=''))
        router = _tavily_router()
        engine = KnowledgeEnrichmentEngine(MagicMock())
        with patch(ROUTER_PATH, return_value=router):
            result = engine.execute(artifact, _runtime(self.env))
        self.assertTrue(result.success, result.error)
        tavily_calls = [n for n in router.namespaces()
                        if n == 'tavily_mcp.tavily_search']
        self.assertEqual(tavily_calls, [],
                         'knowledge search is demand-driven: no domain/'
                         'audience means no tavily MCP call')
        self.assertEqual(
            (result.artifact.knowledge.get('knowledge_documents') or []), [])

    def test_demand_driven_query_uses_domain_and_audience(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(domain='orthodontics',
                                       audience='adult patients'))
        router = _tavily_router()
        engine = KnowledgeEnrichmentEngine(MagicMock())
        with patch(ROUTER_PATH, return_value=router):
            engine.execute(artifact, _runtime(self.env))
        tavily_calls = [c for c in router.calls
                        if c[0] == 'tavily_mcp.tavily_search']
        self.assertTrue(tavily_calls)
        self.assertEqual(tavily_calls[0][1]['inputs']['query'],
                         'orthodontics adult patients')

    def test_provider_failure_isolated_not_fatal(self):
        """Tavily MCP failure stays observable and never fails generation."""
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements())
        router = _FakeRouter(fail_namespaces={'tavily_mcp.tavily_search'})
        engine = KnowledgeEnrichmentEngine(MagicMock())
        with patch(ROUTER_PATH, return_value=router):
            result = engine.execute(artifact, _runtime(self.env))
        self.assertTrue(result.success,
                        'provider failure must never fail the stage')
        sources = result.artifact.knowledge.get('knowledge_sources') or {}
        errors = {e.get('provider'): e for e in sources.get('provider_errors', [])}
        self.assertIn('tavily_knowledge', errors,
                      'the failure must be recorded through the existing '
                      'provider-error mechanism')
        self.assertIn('simulated MCP failure', str(errors['tavily_knowledge']))
        self.assertNotIn('tavily_knowledge', sources.get('providers_used', []),
                         'a failed provider is not reported as used')
        self.assertEqual(
            (result.artifact.knowledge.get('knowledge_documents') or []), [],
            'a failed provider must not invent artifacts')

    def test_component_results_never_forced_into_knowledge(self):
        """SEARCH-capable github sources returning ComponentPackages stay in
        the component path — only KnowledgeDocuments enter knowledge."""
        pm = self._pm()
        github_json = json.dumps([
            {"path": "src/Hero.tsx", "name": "Hero",
             "component_id": "src/Hero.tsx"}])
        router = _FakeRouter({
            'github_mcp.search_code': _mcp_text_envelope(github_json),
            'tavily_mcp.tavily_search': _mcp_text_envelope(TAVILY_LIVE_TEXT),
        })
        with patch(ROUTER_PATH, return_value=router):
            results = pm.route_request('react_bits', 'search', 'hero')
        self.assertTrue(results)
        self.assertTrue(all(not isinstance(r, KnowledgeDocument)
                            for r in results),
                        'github component results must not become documents')
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements())
        engine = KnowledgeEnrichmentEngine(MagicMock())
        with patch(ROUTER_PATH, return_value=router):
            result = engine.execute(artifact, _runtime(self.env))
        docs = result.artifact.knowledge.get('knowledge_documents') or []
        self.assertEqual(len(docs), 2,
                         'only the tavily documents reach knowledge')


# ---------------------------------------------------------------------------
# Existing-consumer proof through the REAL adapter chain (gosom)
# ---------------------------------------------------------------------------
class TestU4716GosomChain(unittest.TestCase):
    """gosom_mcp -> BUSINESS_SEARCH -> BusinessData -> BusinessResearchEngine
    through the real source row + adapter (MCP seam faked only)."""

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_business_search_returns_business_data(self):
        pm = ProviderManager(self.env)
        pm.load_from_registry()
        router = _FakeRouter({
            'gosom_mcp.business_search': _mcp_text_envelope(GOSOM_JSON),
        })
        with patch(ROUTER_PATH, return_value=router):
            results = pm.route_request(
                'gosom_business', 'search_businesses', ['Acme Dental'])
        self.assertTrue(all(isinstance(r, BusinessData) for r in results))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].data_id, 'gosom:abc123')
        self.assertEqual(results[0].category, 'business_place')

    def test_business_research_engine_consumes_business_data(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(
                branding={'business_name': 'Acme Dental'}))
        router = _FakeRouter({
            'gosom_mcp.business_search': _mcp_text_envelope(GOSOM_JSON),
        })
        engine = BusinessResearchEngine(MagicMock())
        with patch(ROUTER_PATH, return_value=router):
            result = engine.execute(artifact, _runtime(self.env))
        self.assertTrue(result.success, result.error)
        research = result.artifact.research
        entries = research.get('business_data') or []
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]['data_id'], 'gosom:abc123')
        self.assertIn('gosom_business',
                      research.get('business_research', {}).get(
                          'providers_used', []))


# ---------------------------------------------------------------------------
# TASK 11 — architecture integrity
# ---------------------------------------------------------------------------
class TestU4716Architecture(unittest.TestCase):

    FORBIDDEN_OWNERS = (
        'FinalConnectorRegistry', 'ProductionSourceRegistry',
        'ProductionCapabilityRegistry', 'ProductionProviderManager',
        'ProductionSearchEngine', 'KnowledgeSearchService',
        'WebSearchService', 'TavilyService', 'TavilyAdapter',
        'SecondConnectorRuntime',
    )

    def test_no_parallel_owners_introduced(self):
        offenders = []
        for root, dirs, files in os.walk(os.path.join(ADDON, 'services')):
            dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
            for f in files:
                if not f.endswith('.py'):
                    continue
                with open(os.path.join(root, f), 'r', encoding='utf-8',
                          errors='ignore') as fh:
                    text = fh.read()
                for name in self.FORBIDDEN_OWNERS:
                    if name in text:
                        offenders.append('%s:%s' % (f, name))
        self.assertEqual(offenders, [])

    def test_adapter_text_parser_is_config_driven_no_provider_names(self):
        src = _src('services/source_framework/adapters/mcp_source_adapter.py')
        start = src.index('def _parse_text_blocks')
        body = src[start:src.index('def search', start)]
        for provider in ('tavily', 'firecrawl', 'context7', 'gosom',
                         'penpot', 'github'):
            self.assertNotIn(provider, body.lower(),
                             'the text parser must stay provider-neutral')

    def test_no_connector_specific_branching_in_source_row(self):
        """The tavily wiring lives ONLY in declarative config — no production
        code file names tavily_knowledge (data/migration/tests excluded)."""
        for rel in ('services/source_framework/adapters/mcp_source_adapter.py',
                    'services/source_framework/provider_manager.py',
                    'services/generation/engines/knowledge_enrichment_engine.py',
                    'services/generation/engines/business_research_engine.py'):
            self.assertNotIn('tavily_knowledge', _src(rel),
                             '%s must not hardcode source identities' % rel)

    def test_single_owners_unchanged(self):
        engines = os.listdir(os.path.join(
            ADDON, 'services', 'generation', 'engines'))
        self.assertEqual(
            [f for f in engines if 'knowledge' in f.lower()],
            ['knowledge_enrichment_engine.py'])
        self.assertEqual(
            [f for f in engines if 'business' in f.lower()],
            ['business_research_engine.py'])
        sf = os.listdir(os.path.join(
            ADDON, 'services', 'source_framework'))
        self.assertIn('provider_manager.py', sf)
        self.assertEqual([f for f in sf if 'provider_manager' in f],
                         ['provider_manager.py'])

    def test_db_readonly_integrity(self):
        registry = Registry.new('nexora_studio')
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            connectors = env['nexora.connector'].search([])
            self.assertEqual(len(connectors), 6)
            self.assertTrue(all(not c.enabled for c in connectors),
                            'no connector may be enabled as a test side effect')
            self.assertTrue(all(c.state == 'disabled' for c in connectors))
            sources = env['nexora.source_registry'].search([])
            self.assertEqual(len(sources), 7)
            tavily = sources.filtered(
                lambda s: s.technical_name == 'tavily_knowledge')
            self.assertEqual(tavily.connector_id.connector_id, 'tavily_mcp')
            self.assertEqual(len(env['nexora.mcp_credential'].search([])), 5)
            self.assertEqual(
                len(env['nexora.mcp_server_config'].search([])), 6)
            self.assertEqual(
                len(env['nexora.capability_registry'].search([])), 17)
            penpot_cap = env['nexora.capability_registry'].search(
                [('capability_id', '=', 'mcp.penpot.1.0.0')], limit=1)
            self.assertEqual(penpot_cap.implementation_model, 'connector')
            renderer_caps = env['nexora.capability_registry'].search([
                ('capability_id', 'in',
                 ('mcp.spline.1.0.0', 'mcp.threejs_docs.1.0.0',
                  'mcp.r3f_docs.1.0.0', 'mcp.drei_docs.1.0.0'))])
            self.assertEqual(len(renderer_caps), 4)
            self.assertTrue(all(not c.enabled for c in renderer_caps))


# ---------------------------------------------------------------------------
# Opt-in LIVE full-chain proof (real Tavily API through the canonical chain)
# ---------------------------------------------------------------------------
@unittest.skipUnless(os.environ.get('NEXORA_U4716_LIVE') == '1',
                     'opt-in live tavily chain (set NEXORA_U4716_LIVE=1; '
                     'costs a real API call)')
class TestU4716LiveTavilyChain(unittest.TestCase):
    """LIVE proof of the complete production chain:

        real source row -> real McpSourceAdapter -> canonical router
        -> ephemeral ConnectorRuntime -> real tavily-mcp stdio transport
        -> real Tavily API -> KnowledgeDocument

    Uses the connection-tester's ephemeral-runtime pattern: the global
    bootstrap runtime is never touched, the connector is registered only in
    the ephemeral in-memory runtime, and every registration write happens
    inside a savepoint that is rolled back. No connector lifecycle state is
    changed in the database.
    """

    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()

    def test_live_search_full_chain(self):
        from odoo.addons.nexora_studio.services.connector.runtime.connector_runtime import (
            ConnectorRuntime,
        )
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import (
            McpOnboardingService,
        )

        record = self.env['nexora.connector'].search(
            [('connector_id', '=', 'tavily_mcp')], limit=1)
        self.assertTrue(record, 'tavily_mcp connector record missing')

        ephemeral = None
        self.cr.execute('SAVEPOINT u4716_live')
        try:
            ephemeral = ConnectorRuntime()
            ephemeral.startup()
            onboarding = McpOnboardingService(
                ephemeral, ephemeral.registration_pipeline, self.env)
            onboarding.register_connector(record)

            # The canonical router resolves "{connector}.{tool}" namespaces
            # through nexora.mcp_discovered_tool with a routable-lifecycle
            # filter on the connector record. The ephemeral runtime keeps
            # its registry in memory only, so mirror the running state on
            # the record INSIDE the savepoint — flushing it to SQL so the
            # rollback below genuinely undoes it — and restore the
            # steady-state 'disabled' afterwards.
            record.write({'state': 'running'})
            # 'enabled' is a stored compute derived from 'state': flush BOTH
            # so the savepoint rollback genuinely undoes them.
            self.env['nexora.connector'].flush_model(['state', 'enabled'])

            pm = ProviderManager(self.env)
            pm.load_from_registry()

            with patch('odoo.addons.nexora_studio.services.connector.'
                       'integration.bootstrap.get_connector_runtime',
                       return_value=ephemeral):
                results = pm.route_request(
                    'tavily_knowledge', 'search',
                    'dental clinic website design best practices')

            self.assertTrue(results, 'live tavily search must return results')
            self.assertTrue(all(isinstance(r, KnowledgeDocument)
                                for r in results),
                            'live results must normalize to KnowledgeDocument')
            first = results[0]
            self.assertTrue(first.document_id.startswith('http'),
                            'document_id must be the result URL')
            self.assertTrue(first.title)
            self.assertTrue(len(first.content) > 50,
                            'live content must be substantive')
        finally:
            if ephemeral is not None:
                try:
                    ephemeral.shutdown()
                except Exception:
                    pass
            self.cr.execute('ROLLBACK TO SAVEPOINT u4716_live')
            self.cr.execute('RELEASE SAVEPOINT u4716_live')
        # Post-conditions: connector still disabled in DB (no side effect).
        record.invalidate_recordset()
        self.assertEqual(record.state, 'disabled')
        self.assertFalse(record.enabled)


if __name__ == '__main__':
    unittest.main()
