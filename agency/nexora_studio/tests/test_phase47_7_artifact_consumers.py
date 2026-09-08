"""Focused U7 tests for existing artifact consumer closure.

Covers:
  BusinessData       -> BusinessResearchEngine    -> artifact.research
  RepositoryArtifact -> KnowledgeEnrichmentEngine  -> artifact.knowledge
  KnowledgeDocument  -> KnowledgeEnrichmentEngine  -> artifact.knowledge
  DesignAsset        -> AssetEngine                -> artifact.assets
  ComponentPackage   -> ComponentTree              -> CodeGenerationEngine
  provenance preservation, optional provider failure isolation,
  malformed artifact rejection, U4 checkpoint compatibility,
  non-component artifact exclusion from component ranking.
"""

import ast
import re
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel,
    ComponentTree,
    GenerationContext,
    GenerationState,
    RequirementModel,
    WebsiteGenerationArtifact,
)
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import (
    GenerationStateManager,
)
from odoo.addons.nexora_studio.services.generation.engines.asset_engine import (
    AssetEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.business_research_engine import (
    BusinessResearchEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
    ComponentIntelligenceEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.knowledge_enrichment_engine import (
    KnowledgeEnrichmentEngine,
)
from odoo.addons.nexora_studio.services.source_framework.domain_models import (
    BusinessData,
    ComponentPackage,
    DesignAsset,
    KnowledgeDocument,
    Provenance,
    RepositoryArtifact,
)
from odoo.addons.nexora_studio.services.source_framework.search_engine import SearchEngine


ROOT = Path(__file__).resolve().parents[1]
PM_PATH = 'odoo.addons.nexora_studio.services.source_framework.provider_manager.ProviderManager'


class _ProviderManager:
    def __init__(self, adapters):
        self.adapters = adapters
        self.calls = []

    def load_from_registry(self):
        pass

    def get_capable_providers(self, capability):
        return [
            provider_id for provider_id, adapter in self.adapters.items()
            if capability in adapter.capabilities
        ]

    def route_request(self, provider_id, method, *args, **kwargs):
        self.calls.append((provider_id, method, args))
        return getattr(self.adapters[provider_id], method)(*args, **kwargs)


class _Adapter:
    def __init__(self, capabilities, business_result=None, search_result=None,
                 repo_result=None, error=None):
        self.capabilities = capabilities
        self.business_result = business_result or []
        self.search_result = search_result or []
        self.repo_result = repo_result or []
        self.error = error

    def search_businesses(self, queries):
        if self.error:
            raise self.error
        return self.business_result

    def search(self, query):
        if self.error:
            raise self.error
        return self.search_result

    def fetch_repository_artifacts(self, intent='repo_search', params=None):
        if self.error:
            raise self.error
        return self.repo_result


class _Runtime:
    def __init__(self, env=None, ai=None, orchestrator=None):
        self.env = env
        if ai is not None:
            self.ai = ai
        if orchestrator is not None:
            self.orchestrator = orchestrator


def _patch_pm(adapters):
    return patch(PM_PATH, return_value=_ProviderManager(adapters))


def _business_data():
    return BusinessData(
        data_id='gos-1',
        category='business_place',
        payload={
            'name': 'Acme Coffee',
            'address': '1 Main St',
            'phone': '+1-555-0100',
            'website': 'https://acme.example',
            'coordinates': {'latitude': 52.1, 'longitude': 4.3},
            'rating': 4.7,
            'reviews_count': 128,
            'opening_hours': ['08:00-18:00'],
        },
        provenance=Provenance(
            provider='gosom_business', import_source='csf:gosom_business',
        ),
    )


def _document():
    return KnowledgeDocument(
        document_id='doc-1',
        title='React Three Fiber guide',
        content='Use Canvas from @react-three/fiber.',
        metadata={'version': '8.x'},
        provenance=Provenance(provider='docs_source', release_version='8.x'),
    )


def _repo_artifact():
    return RepositoryArtifact(
        artifact_id='1001',
        path='pmndrs/drei',
        type='file',
        metadata={'language': 'TypeScript', 'stars': 2500},
        provenance=Provenance(
            provider='github_repo_intelligence', repository='pmndrs/drei',
            commit_sha='abc123', import_source='csf:github_repo_intelligence',
        ),
    )


def _design_asset(asset_id='img-1', asset_type='image', **metadata):
    return DesignAsset(
        asset_id=asset_id,
        name=f'Asset {asset_id}',
        type=asset_type,
        url=f'https://cdn.example/{asset_id}',
        metadata=dict(metadata),
        provenance=Provenance(provider='asset_source', license='CC0'),
    )


def _package(name, source='function Source() { return null }'):
    return ComponentPackage(
        component_id=f'components/{name}.tsx',
        name=name,
        description=f'{name} hero component',
        metadata={'source_code': source, 'source_identifier': name},
        dependencies=[{'name': 'three', 'version': '^0.1.0'}],
        provenance=Provenance(
            provider='pmndrs', repository='pmndrs/drei',
            commit_sha='abc123', license='MIT', import_source='csf:3d',
        ),
    )


def _requirements(**kwargs):
    defaults = dict(raw_input='Build a site', domain='Agency',
                    target_audience='Small businesses')
    defaults.update(kwargs)
    return RequirementModel(**defaults)


class Phase477BusinessDataTests(unittest.TestCase):
    def test_business_data_consumed_into_research_with_provenance(self):
        pm = _ProviderManager({'gosom_business': _Adapter(
            ['BUSINESS_SEARCH'], business_result=[_business_data()])})
        runtime = _Runtime(env=object())
        with patch(PM_PATH, return_value=pm):
            result = BusinessResearchEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()), runtime)

        self.assertTrue(result.success, result.error)
        research = result.artifact.research
        entry = research['business_data'][0]
        self.assertEqual(entry['data_id'], 'gos-1')
        self.assertEqual(entry['category'], 'business_place')
        self.assertEqual(entry['payload']['address'], '1 Main St')
        self.assertEqual(entry['payload']['phone'], '+1-555-0100')
        self.assertEqual(entry['payload']['website'], 'https://acme.example')
        self.assertEqual(entry['payload']['coordinates'], {'latitude': 52.1, 'longitude': 4.3})
        self.assertEqual(entry['payload']['rating'], 4.7)
        self.assertEqual(entry['payload']['opening_hours'], ['08:00-18:00'])
        self.assertEqual(entry['provenance']['provider'], 'gosom_business')
        self.assertEqual(entry['provenance']['import_source'], 'csf:gosom_business')
        self.assertEqual(research['business_research']['status'], 'completed')
        self.assertEqual(research['business_research']['providers_used'], ['gosom_business'])
        self.assertEqual(
            [(provider, method) for provider, method, _args in pm.calls],
            [('gosom_business', 'search_businesses')],
        )
        self.assertEqual(pm.calls[0][2][0], ['Agency Small businesses'])

    def test_business_research_not_applicable_without_business_sources(self):
        pm = _ProviderManager({'react_bits': _Adapter(['SEARCH'])})
        with patch(PM_PATH, return_value=pm):
            result = BusinessResearchEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()),
                _Runtime(env=object()))
        self.assertTrue(result.success, result.error)
        self.assertEqual(
            result.artifact.research['business_research']['status'], 'not_applicable')
        self.assertNotIn('business_data', result.artifact.research)
        self.assertEqual(pm.calls, [])

    def test_business_research_skipped_cleanly_without_environment(self):
        result = BusinessResearchEngine(MagicMock()).execute(
            WebsiteGenerationArtifact(requirements=_requirements()), _Runtime())
        self.assertTrue(result.success, result.error)
        self.assertEqual(
            result.artifact.research['business_research']['status'], 'not_applicable')

    def test_failed_business_source_preserves_successful_source(self):
        pm = _ProviderManager({
            'broken_business': _Adapter(['BUSINESS_SEARCH'], error=RuntimeError('gosom down')),
            'gosom_business': _Adapter(['BUSINESS_SEARCH'], business_result=[_business_data()]),
        })
        with patch(PM_PATH, return_value=pm):
            result = BusinessResearchEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()),
                _Runtime(env=object()))
        self.assertTrue(result.success, result.error)
        research = result.artifact.research
        self.assertEqual(len(research['business_data']), 1)
        self.assertEqual(research['business_data'][0]['data_id'], 'gos-1')
        status = research['business_research']
        self.assertEqual(status['status'], 'partially_completed')
        self.assertEqual(status['providers_used'], ['gosom_business'])
        self.assertEqual(status['provider_errors'][0]['provider'], 'broken_business')
        self.assertEqual(status['provider_errors'][0]['operation'], 'search_businesses')

    def test_all_business_sources_unavailable_is_recorded_not_fatal(self):
        pm = _ProviderManager({
            'gosom_business': _Adapter(['BUSINESS_SEARCH'], error=RuntimeError('down')),
        })
        with patch(PM_PATH, return_value=pm):
            result = BusinessResearchEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()),
                _Runtime(env=object()))
        self.assertTrue(result.success, result.error)
        status = result.artifact.research['business_research']
        self.assertEqual(status['status'], 'provider_unavailable')
        self.assertEqual(status['provider_errors'][0]['provider'], 'gosom_business')
        self.assertEqual(result.artifact.research['business_data'], [])

    def test_business_source_with_no_results_reports_no_data(self):
        pm = _ProviderManager({'gosom_business': _Adapter(
            ['BUSINESS_SEARCH'], business_result=[])})
        with patch(PM_PATH, return_value=pm):
            result = BusinessResearchEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()),
                _Runtime(env=object()))
        self.assertTrue(result.success, result.error)
        status = result.artifact.research['business_research']
        self.assertEqual(status['status'], 'no_data')
        self.assertEqual(result.artifact.research['business_data'], [])

    def test_malformed_business_data_fails_stage(self):
        for bad in (
            {'data_id': 'x', 'category': 'business_place'},
            BusinessData(data_id='', category='business_place', payload={}),
            BusinessData(data_id='x', category='business_place', payload=None),
        ):
            pm = _ProviderManager({'gosom_business': _Adapter(
                ['BUSINESS_SEARCH'], business_result=[bad])})
            with patch(PM_PATH, return_value=pm):
                result = BusinessResearchEngine(MagicMock()).execute(
                    WebsiteGenerationArtifact(requirements=_requirements()),
                    _Runtime(env=object()))
            self.assertFalse(result.success, f'malformed item accepted: {bad!r}')
            self.assertIn('Malformed BusinessData', result.error)

    def test_explicit_business_name_drives_query(self):
        pm = _ProviderManager({'gosom_business': _Adapter(
            ['BUSINESS_SEARCH'], business_result=[_business_data()])})
        with patch(PM_PATH, return_value=pm):
            BusinessResearchEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements(
                    branding={'business_name': 'Acme Coffee Roasters'})),
                _Runtime(env=object()))
        self.assertEqual(pm.calls[0][2][0], ['Acme Coffee Roasters'])


class Phase477KnowledgeTests(unittest.TestCase):
    def _runtime(self, pm):
        ai = MagicMock()
        ai.generate.return_value = {'knowledge': {'business_summary': 'A site.'}}
        return _Runtime(env=object(), ai=ai), ai

    def test_knowledge_document_consumed_with_provenance(self):
        pm = _ProviderManager({'docs_source': _Adapter(
            ['SEARCH'], search_result=[_document(), _package('Hero')])})
        runtime, ai = self._runtime(pm)
        with patch(PM_PATH, return_value=pm):
            result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()), runtime)

        self.assertTrue(result.success, result.error)
        knowledge = result.artifact.knowledge
        entry = knowledge['knowledge_documents'][0]
        self.assertEqual(entry['document_id'], 'doc-1')
        self.assertEqual(entry['title'], 'React Three Fiber guide')
        self.assertIn('@react-three/fiber', entry['content'])
        self.assertEqual(entry['metadata'], {'version': '8.x'})
        self.assertEqual(entry['provenance']['provider'], 'docs_source')
        self.assertEqual(entry['provenance']['release_version'], '8.x')
        # ComponentPackage results never leak into knowledge.
        self.assertEqual(len(knowledge['knowledge_documents']), 1)
        # Phase 47.26 (ADR-0078): the stage is deterministic — the artifact
        # contract keys are preserved (business_summary derived from the
        # requirements) and NO LLM call is made.
        self.assertIn('business_summary', knowledge)
        self.assertIn(knowledge['knowledge_sources']['status'],
                      ('completed', 'partially_completed'))
        ai.generate.assert_not_called()

    def test_repository_artifact_consumed_as_implementation_context(self):
        pm = _ProviderManager({'github_repo_intelligence': _Adapter(
            ['REPOSITORY_INTELLIGENCE'], repo_result=[_repo_artifact()])})
        runtime, ai = self._runtime(pm)
        with patch(PM_PATH, return_value=pm):
            result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements(
                    goals=['Showcase 3D work'])), runtime)

        self.assertTrue(result.success, result.error)
        knowledge = result.artifact.knowledge
        entry = knowledge['implementation_context'][0]
        self.assertEqual(entry['artifact_id'], '1001')
        self.assertEqual(entry['path'], 'pmndrs/drei')
        self.assertEqual(entry['type'], 'file')
        self.assertEqual(entry['metadata']['language'], 'TypeScript')
        self.assertEqual(entry['provenance']['provider'], 'github_repo_intelligence')
        self.assertEqual(entry['provenance']['repository'], 'pmndrs/drei')
        self.assertEqual(entry['provenance']['commit_sha'], 'abc123')
        self.assertEqual(knowledge['knowledge_sources']['status'], 'completed')
        # Canonical CSF dispatch: intent + params through the existing adapter API.
        call = next(c for c in pm.calls if c[1] == 'fetch_repository_artifacts')
        self.assertEqual(call[0], 'github_repo_intelligence')
        self.assertEqual(call[2][0], 'repo_search')
        self.assertIn('query', call[2][1])
        # Phase 47.26 (ADR-0078): deterministic — no LLM call; the repo
        # artifacts land in the artifact contract directly.
        ai.generate.assert_not_called()
        self.assertEqual(
            knowledge['implementation_context'][0]['path'], 'pmndrs/drei')

    def test_knowledge_not_applicable_without_sources(self):
        pm = _ProviderManager({})
        runtime, _ai = self._runtime(pm)
        with patch(PM_PATH, return_value=pm):
            result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()), runtime)
        self.assertTrue(result.success, result.error)
        self.assertEqual(
            result.artifact.knowledge['knowledge_sources']['status'], 'not_applicable')
        self.assertEqual(result.artifact.knowledge['knowledge_documents'], [])
        self.assertEqual(result.artifact.knowledge['implementation_context'], [])

    def test_failed_knowledge_source_preserves_successful_source(self):
        pm = _ProviderManager({
            'broken_docs': _Adapter(['SEARCH'], error=RuntimeError('docs down')),
            'docs_source': _Adapter(['SEARCH'], search_result=[_document()]),
            'github_repo_intelligence': _Adapter(
                ['REPOSITORY_INTELLIGENCE'], repo_result=[_repo_artifact()]),
        })
        runtime, _ai = self._runtime(pm)
        with patch(PM_PATH, return_value=pm):
            result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()), runtime)
        self.assertTrue(result.success, result.error)
        sources = result.artifact.knowledge['knowledge_sources']
        self.assertEqual(sources['status'], 'partially_completed')
        self.assertEqual(sources['documents_found'], 1)
        self.assertEqual(sources['repository_artifacts_found'], 1)
        self.assertEqual(sources['provider_errors'][0]['provider'], 'broken_docs')
        self.assertEqual(
            result.artifact.knowledge['knowledge_documents'][0]['document_id'], 'doc-1')
        self.assertEqual(
            result.artifact.knowledge['implementation_context'][0]['artifact_id'], '1001')

    def test_knowledge_documents_survive_ai_failure(self):
        pm = _ProviderManager({'docs_source': _Adapter(
            ['SEARCH'], search_result=[_document()])})
        ai = MagicMock()
        ai.generate.side_effect = RuntimeError('ai unavailable')
        runtime = _Runtime(env=object(), ai=ai)
        with patch(PM_PATH, return_value=pm):
            result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()), runtime)
        self.assertTrue(result.success, result.error)
        self.assertEqual(
            result.artifact.knowledge['knowledge_documents'][0]['document_id'], 'doc-1')
        self.assertIn('business_summary', result.artifact.knowledge)

    def test_malformed_knowledge_document_fails_stage(self):
        bad = KnowledgeDocument(document_id='', title='', content='')
        pm = _ProviderManager({'docs_source': _Adapter(
            ['SEARCH'], search_result=[bad])})
        runtime, _ai = self._runtime(pm)
        with patch(PM_PATH, return_value=pm):
            result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                WebsiteGenerationArtifact(requirements=_requirements()), runtime)
        self.assertFalse(result.success)
        self.assertIn('Malformed KnowledgeDocument', result.error)

    def test_malformed_repository_artifact_fails_stage(self):
        for bad in (
            {'artifact_id': '1001', 'path': 'pmndrs/drei'},
            RepositoryArtifact(artifact_id='', path=''),
        ):
            pm = _ProviderManager({'github_repo_intelligence': _Adapter(
                ['REPOSITORY_INTELLIGENCE'], repo_result=[bad])})
            runtime, _ai = self._runtime(pm)
            with patch(PM_PATH, return_value=pm):
                result = KnowledgeEnrichmentEngine(MagicMock()).execute(
                    WebsiteGenerationArtifact(requirements=_requirements()), runtime)
            self.assertFalse(result.success, f'malformed item accepted: {bad!r}')
            self.assertIn('Malformed RepositoryArtifact', result.error)


class Phase477DesignAssetTests(unittest.TestCase):
    def _execute(self, artifact, adapters=None):
        pm = _ProviderManager(adapters or {})
        runtime = _Runtime(env=object())
        with patch(PM_PATH, return_value=pm):
            result = AssetEngine(MagicMock()).execute(artifact, runtime)
        return result, pm

    def test_design_assets_incorporated_into_existing_assets_contract(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(),
            generation_metadata={'design_assets': [
                _design_asset('img-1', 'image', format='jpg', intended_usage='hero background'),
            ]},
        )
        result, pm = self._execute(artifact, adapters={
            'asset_source': _Adapter(['SEARCH'], search_result=[
                _design_asset('icon-1', 'icon', format='svg'),
                _design_asset('font-1', 'font', format='woff2'),
                _package('NotAnAsset'),
            ]),
        })
        self.assertTrue(result.success, result.error)
        assets = result.artifact.assets

        image_entry = next(e for e in assets.images if e.get('id') == 'img-1')
        self.assertEqual(image_entry['name'], 'Asset img-1')
        self.assertEqual(image_entry['type'], 'image')
        self.assertEqual(image_entry['url'], 'https://cdn.example/img-1')
        self.assertEqual(image_entry['format'], 'jpg')
        self.assertEqual(image_entry['license'], 'CC0')
        self.assertEqual(image_entry['provenance']['provider'], 'asset_source')
        self.assertEqual(image_entry['metadata']['intended_usage'], 'hero background')
        self.assertFalse(image_entry['materialized'])
        self.assertIsNone(image_entry['content'])

        self.assertTrue(any(e.get('id') == 'icon-1' for e in assets.icons))
        self.assertTrue(any(e.get('id') == 'font-1' for e in assets.fonts))
        # ComponentPackage results never leak into assets.
        self.assertFalse(any(e.get('id', '').startswith('components/') for e in assets.images))
        self.assertEqual(result.metadata['design_assets_incorporated'], 3)
        self.assertEqual(result.metadata['design_assets_deferred'], 0)
        self.assertEqual(
            [(provider, method) for provider, method, _args in pm.calls],
            [('asset_source', 'search')],
        )

    def test_design_asset_materialization_status_never_invented(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(),
            generation_metadata={'design_assets': [
                _design_asset('img-1', 'image'),
                _design_asset('img-2', 'image', materialized=True, content='<svg/>'),
            ]},
        )
        result, _pm = self._execute(artifact)
        self.assertTrue(result.success, result.error)
        entries = {e['id']: e for e in result.artifact.assets.images}
        self.assertFalse(entries['img-1']['materialized'])
        self.assertIsNone(entries['img-1']['content'])
        self.assertTrue(entries['img-2']['materialized'])
        self.assertEqual(entries['img-2']['content'], '<svg/>')

    def test_unmapped_design_asset_type_deferred_not_lost(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(),
            generation_metadata={'design_assets': [
                _design_asset('model-1', 'model', format='glb'),
            ]},
        )
        result, _pm = self._execute(artifact)
        self.assertTrue(result.success, result.error)
        assets = result.artifact.assets
        self.assertFalse(any(e.get('id') == 'model-1' for e in assets.images))
        self.assertFalse(any(e.get('id') == 'model-1' for e in assets.icons))
        self.assertFalse(any(e.get('id') == 'model-1' for e in assets.fonts))
        deferred = result.artifact.generation_metadata['design_assets_deferred']
        self.assertEqual(deferred[0]['id'], 'model-1')
        self.assertEqual(deferred[0]['type'], 'model')
        self.assertEqual(deferred[0]['provenance']['provider'], 'asset_source')
        self.assertFalse(deferred[0]['materialized'])
        self.assertEqual(result.metadata['design_assets_deferred'], 1)

    def test_design_asset_deduplicates_against_deterministic_assets(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(),
            component_tree=ComponentTree(nodes=[{'component_id': 'hero'}]),
            generation_metadata={'design_assets': [
                _design_asset('hero_bg_agency', 'image'),
            ]},
        )
        result, _pm = self._execute(artifact)
        self.assertTrue(result.success, result.error)
        ids = [e.get('id') for e in result.artifact.assets.images]
        self.assertEqual(ids.count('hero_bg_agency'), 1)

    def test_failed_asset_source_preserves_deterministic_assets(self):
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(),
            component_tree=ComponentTree(nodes=[{'component_id': 'hero'}]),
        )
        result, _pm = self._execute(artifact, adapters={
            'broken_assets': _Adapter(['SEARCH'], error=RuntimeError('asset source down')),
        })
        self.assertTrue(result.success, result.error)
        self.assertTrue(any(
            e.get('id') == 'hero_bg_agency' for e in result.artifact.assets.images))
        errors = result.metadata['asset_provider_errors']
        self.assertEqual(errors[0]['provider'], 'broken_assets')
        self.assertEqual(errors[0]['operation'], 'search')

    def test_malformed_design_asset_fails_stage(self):
        for bad in (
            {'name': 'missing identity'},
            DesignAsset(asset_id='', name='x', type='image'),
            'not-an-asset',
        ):
            artifact = WebsiteGenerationArtifact(
                requirements=_requirements(),
                generation_metadata={'design_assets': [bad]},
            )
            result, _pm = self._execute(artifact)
            self.assertFalse(result.success, f'malformed item accepted: {bad!r}')
            self.assertIn('Malformed DesignAsset', result.error)


class Phase477ComponentHandoffTests(unittest.TestCase):
    def test_non_component_artifacts_never_enter_component_ranking(self):
        class _MixedProviderManager:
            def __init__(self):
                self.adapters = {'mixed': _Adapter(
                    ['SEARCH'],
                    search_result=[
                        _package('Hero'),
                        BusinessData(data_id='b', category='business_place'),
                        RepositoryArtifact(artifact_id='r', path='owner/repo'),
                        KnowledgeDocument(document_id='k', title='doc', content='text'),
                        DesignAsset(asset_id='a', name='asset', type='image'),
                    ],
                )}

            def get_capable_providers(self, capability):
                return [
                    provider_id for provider_id, adapter in self.adapters.items()
                    if capability in adapter.capabilities
                ]

            def route_request(self, provider_id, method, *args):
                return getattr(self.adapters[provider_id], method)(*args)

        results = SearchEngine(_MixedProviderManager()).search('mixed', {})
        self.assertEqual([r['package'].name for r in results], ['Hero'])

    def test_component_package_survives_to_code_generation(self):
        package = _package(
            'Hero',
            source='function HeroSource() { return <section>source-backed</section> }',
        )
        artifact = WebsiteGenerationArtifact(
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/', 'sections': ['hero']},
            }),
            generation_metadata={
                'candidate_components': [{
                    'package': package, 'score': 0.91, 'final_score': 0.87,
                }],
                'modular_blueprint': {'component': {'abstract_components': [
                    {'id': 'hero', 'purpose': 'hero'},
                ]}},
            },
        )
        intelligence_result = ComponentIntelligenceEngine(None).execute(
            artifact, MagicMock())
        node = intelligence_result.artifact.component_tree.nodes[-1]
        self.assertEqual(node['code'], package.metadata['source_code'])
        self.assertEqual(node['dependencies'], package.dependencies)
        self.assertEqual(node['provenance']['repository'], 'pmndrs/drei')
        self.assertIn('three', intelligence_result.artifact.component_tree.dependencies)

        code_artifact = artifact.evolve(
            component_tree=intelligence_result.artifact.component_tree)
        runtime = MagicMock()
        runtime.ai.generate.side_effect = AssertionError(
            'AI must not replace selected source code')
        runtime.workspace.write_file = MagicMock()
        code_result = CodeGenerationEngine(MagicMock()).execute(code_artifact, runtime)
        self.assertTrue(code_result.success, code_result.error)
        page_write = next(
            call for call in runtime.workspace.write_file.call_args_list
            if call.args[0] == 'src/pages/index.tsx'
        )
        # Phase 47.28: home Hero is now deterministic native Hero
        self.assertIn("import Hero from '../components/Hero.jsx'", page_write.args[1])
        self.assertIn('data-nexora-source="native/Hero"', page_write.args[1])


class Phase477CheckpointCompatibilityTests(unittest.TestCase):
    def test_u4_checkpoint_round_trip_preserves_populated_u7_fields(self):
        research = {
            'business_data': [{
                'data_id': 'gos-1',
                'category': 'business_place',
                'payload': {'name': 'Acme Coffee', 'rating': 4.7},
                'provenance': {'provider': 'gosom_business',
                               'import_source': 'csf:gosom_business'},
            }],
            'business_research': {'status': 'completed', 'queries': ['Acme Coffee'],
                                  'providers_used': ['gosom_business'],
                                  'provider_errors': []},
        }
        knowledge = {
            'business_summary': 'A site.',
            'knowledge_documents': [{
                'document_id': 'doc-1', 'title': 'R3F guide',
                'content': 'Use Canvas.', 'metadata': {'version': '8.x'},
                'provenance': {'provider': 'docs_source'},
            }],
            'implementation_context': [{
                'artifact_id': '1001', 'path': 'pmndrs/drei', 'type': 'file',
                'content': None, 'metadata': {'language': 'TypeScript'},
                'provenance': {'provider': 'github_repo_intelligence',
                               'repository': 'pmndrs/drei'},
            }],
            'knowledge_sources': {'status': 'completed', 'providers_used': [],
                                  'provider_errors': [], 'documents_found': 1,
                                  'repository_artifacts_found': 1},
        }
        artifact = WebsiteGenerationArtifact(
            requirements=_requirements(),
            research=research,
            knowledge=knowledge,
        )
        asset_result = AssetEngine(MagicMock()).execute(
            artifact.evolve(generation_metadata={'design_assets': [
                _design_asset('img-1', 'image', format='jpg'),
                _design_asset('model-1', 'model', format='glb'),
            ]}),
            _Runtime(),
        )
        self.assertTrue(asset_result.success, asset_result.error)
        populated = asset_result.artifact

        context = GenerationContext(
            context_id='u7-artifacts',
            artifact=populated,
            state=GenerationState.ASSETS_GENERATED,
        )
        manager = GenerationStateManager()
        manager.save_checkpoint(context)
        restored = manager.load_checkpoint(context.context_id)

        self.assertEqual(restored.artifact.research, populated.research)
        self.assertEqual(restored.artifact.knowledge, populated.knowledge)
        self.assertEqual(restored.artifact.assets, populated.assets)
        self.assertEqual(
            restored.artifact.generation_metadata, populated.generation_metadata)
        self.assertEqual(
            restored.artifact.assets.images[-1]['provenance']['provider'],
            'asset_source')


class Phase477ArchitectureBoundaryTests(unittest.TestCase):
    def _source(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    U7_ENGINE_FILES = (
        'services/generation/engines/business_research_engine.py',
        'services/generation/engines/knowledge_enrichment_engine.py',
        'services/generation/engines/asset_engine.py',
        'services/generation/engines/code_generation_engine.py',
        'services/generation/engines/component_intelligence_engine.py',
    )

    def test_no_direct_http_clients_in_generation_engines(self):
        banned = re.compile(
            r'^\s*(import requests|import httpx|import aiohttp|import urllib\.request'
            r'|from requests|from httpx|from aiohttp)', re.M)
        offenders = [
            path for path in self.U7_ENGINE_FILES
            if banned.search(self._source(path))
        ]
        self.assertEqual(offenders, [])

    def test_no_new_artifact_models_or_registries_in_u7_engines(self):
        banned_class = re.compile(
            r'^class\s+(BusinessData|RepositoryArtifact|KnowledgeDocument|DesignAsset'
            r'|ComponentPackage|Provenance)\w*\b', re.M)
        banned_registry = re.compile(
            r'^class\s+\w*(Registry|KnowledgeRegistry|DocumentationEngine'
            r'|DocumentationContext|ComponentAssembler)\b', re.M)
        for path in self.U7_ENGINE_FILES:
            source = self._source(path)
            self.assertIsNone(banned_class.search(source), path)
            self.assertIsNone(banned_registry.search(source), path)

    def test_single_dip_domain_model_layer_unchanged(self):
        domain_models = self._source('services/source_framework/domain_models.py')
        for cls in ('ComponentPackage', 'RepositoryArtifact', 'Provenance',
                    'KnowledgeDocument', 'DesignAsset', 'BusinessData'):
            self.assertEqual(domain_models.count('class %s' % cls), 1, cls)

    def test_u7_consumers_use_existing_source_framework_entry_only(self):
        for path in self.U7_ENGINE_FILES[:3]:
            source = self._source(path)
            self.assertIn(
                'from odoo.addons.nexora_studio.services.source_framework.'
                'provider_manager import ProviderManager', source, path)
            self.assertNotIn('build_canonical_router', source, path)
            self.assertNotIn('UniversalCapabilityRouter(', source, path)
            self.assertNotIn('ConnectorRuntime', source, path)

    def test_runtime_scopes_grant_env_to_u7_consumers(self):
        runtime = self._source('services/generation/core/generation_runtime.py')
        self.assertIn(
            "self._registry.register(BusinessResearchEngine, {'orchestrator', 'env'})",
            runtime)
        self.assertIn(
            "self._registry.register(KnowledgeEnrichmentEngine, {'ai', 'env'})",
            runtime)
        self.assertIn("self._registry.register(AssetEngine, {'env'})", runtime)

    def test_u7_files_parse(self):
        for relative_path in self.U7_ENGINE_FILES:
            ast.parse(self._source(relative_path), filename=relative_path)


if __name__ == '__main__':
    unittest.main()
