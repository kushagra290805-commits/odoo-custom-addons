"""Focused U6 tests for semantic CSF operation closure."""

import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel,
    ComponentTree,
    WebsiteGenerationArtifact,
)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.component_discovery_engine import (
    ComponentDiscoveryEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
    ComponentIntelligenceEngine,
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


class _ProviderManager:
    def __init__(self, adapters):
        self.adapters = adapters
        self.calls = []

    def get_capable_providers(self, capability):
        return [
            provider_id for provider_id, adapter in self.adapters.items()
            if capability in adapter.capabilities
        ]

    def route_request(self, provider_id, method, *args):
        self.calls.append((provider_id, method, args))
        return getattr(self.adapters[provider_id], method)(*args)


class _Adapter:
    def __init__(self, capabilities, search_result=None, discovery_result=None, error=None):
        self.capabilities = capabilities
        self.search_result = search_result or []
        self.discovery_result = discovery_result or []
        self.error = error

    def search(self, query):
        if self.error:
            raise self.error
        return self.search_result

    def discover_components(self):
        if self.error:
            raise self.error
        return self.discovery_result


class Phase476CsfOperationTests(unittest.TestCase):
    def test_component_source_uses_discover_and_generic_source_uses_search(self):
        pm = _ProviderManager({
            'threed_component_library': _Adapter(
                ['COMPONENT_SOURCE', 'SEARCH'],
                search_result=[_package('wrong-generic')],
                discovery_result=[_package('pmndrs-hero')],
            ),
            'react_bits': _Adapter(['SEARCH'], search_result=[_package('react-button')]),
            'shadcn': _Adapter(['SEARCH'], search_result=[_package('shadcn-card')]),
        })
        results = SearchEngine(pm).search(
            'hero', {}, operation='COMPONENT_SOURCE'
        )

        self.assertEqual(
            [(provider, method) for provider, method, _args in pm.calls],
            [
                ('react_bits', 'search'),
                ('shadcn', 'search'),
                ('threed_component_library', 'discover_components'),
            ],
        )
        self.assertEqual(
            {result['package'].name for result in results},
            {'pmndrs-hero', 'react-button', 'shadcn-card'},
        )

    def test_search_only_mode_does_not_invoke_component_source_operation(self):
        pm = _ProviderManager({
            'threed_component_library': _Adapter(
                ['COMPONENT_SOURCE', 'SEARCH'],
                search_result=[_package('wrong-generic')],
                discovery_result=[_package('pmndrs-hero')],
            ),
            'react_bits': _Adapter(['SEARCH'], search_result=[_package('react-button')]),
        })
        SearchEngine(pm).search('hero', {}, operation='SEARCH')
        self.assertEqual(
            [(provider, method) for provider, method, _args in pm.calls],
            [('threed_component_library', 'search'), ('react_bits', 'search')],
        )

    def test_one_provider_failure_preserves_other_provider_results_and_is_observable(self):
        pm = _ProviderManager({
            'broken': _Adapter(['SEARCH'], error=RuntimeError('source down')),
            'working': _Adapter(['SEARCH'], search_result=[_package('working')]),
        })
        engine = SearchEngine(pm)
        results = engine.search('hero', {})

        self.assertEqual([result['package'].name for result in results], ['working'])
        self.assertEqual(engine.provider_errors[0]['provider'], 'broken')
        self.assertEqual(engine.provider_errors[0]['operation'], 'search')

    def test_component_ranking_pipeline_runs_exactly_once(self):
        pm = _ProviderManager({
            'generic': _Adapter(['SEARCH'], search_result=[_package('generic')]),
            'specialized': _Adapter(
                ['COMPONENT_SOURCE'], discovery_result=[_package('specialized')]
            ),
        })
        from odoo.addons.nexora_studio.services.source_framework.component_ranking_pipeline import (
            ComponentRankingPipeline,
        )
        original = ComponentRankingPipeline.rank_components
        with patch.object(
            ComponentRankingPipeline,
            'rank_components',
            autospec=True,
            side_effect=original,
        ) as rank:
            SearchEngine(pm).search('components', {})
        rank.assert_called_once()

    def test_non_component_artifacts_are_excluded_before_ranking(self):
        non_components = [
            RepositoryArtifact(artifact_id='r', path='owner/repo'),
            BusinessData(data_id='b', category='business_place'),
            KnowledgeDocument(document_id='k', title='doc', content='text'),
            DesignAsset(asset_id='a', name='asset', type='image'),
        ]
        pm = _ProviderManager({'mixed': _Adapter(['SEARCH'], search_result=non_components)})
        results = SearchEngine(pm).search('mixed', {})
        self.assertEqual(results, [])

    def test_intelligence_preserves_rank_dependencies_provenance_and_metadata(self):
        package = _package('Hero')
        artifact = WebsiteGenerationArtifact(
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'sections': ['hero']},
            }),
            generation_metadata={
                'candidate_components': [{
                    'package': package,
                    'score': 0.91,
                    'final_score': 0.87,
                }],
                'modular_blueprint': {
                    'component': {'abstract_components': [
                        {'id': 'hero', 'purpose': 'hero'},
                    ]},
                },
            },
        )
        result = ComponentIntelligenceEngine(None).execute(artifact, MagicMock())
        node = result.artifact.component_tree.nodes[-1]

        self.assertEqual(node['score'], 0.91)
        self.assertEqual(node['final_score'], 0.87)
        self.assertEqual(node['dependencies'], package.dependencies)
        self.assertEqual(node['provenance']['repository'], 'pmndrs/drei')
        self.assertEqual(node['metadata']['source_code'], package.metadata['source_code'])
        self.assertIn('three', result.artifact.component_tree.dependencies)
        self.assertIn('react', result.artifact.component_tree.dependencies)

    def test_code_generation_consumes_selected_source_component(self):
        package = _package(
            'Hero',
            source='function HeroSource() { return <section>source-backed</section> }',
        )
        artifact = WebsiteGenerationArtifact(
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/', 'sections': ['hero']},
            }),
            component_tree=ComponentTree(nodes=[{
                'component_id': package.component_id,
                'code': package.metadata['source_code'],
                'score': 0.91,
                'final_score': 0.87,
                'dependencies': package.dependencies,
                'provenance': {'provider': 'pmndrs'},
                'metadata': {
                    'from_source': True,
                    'semantic': 'hero',
                    'source_identifier': package.component_id,
                },
            }]),
            generation_metadata={'modular_blueprint': {}},
        )
        runtime = MagicMock()
        runtime.ai.generate.side_effect = AssertionError('AI must not replace selected source code')
        runtime.tools.execute.return_value = []
        runtime.workspace.write_file = MagicMock()

        result = CodeGenerationEngine(MagicMock()).execute(artifact, runtime)
        self.assertTrue(result.success, result.error)
        page_write = next(
            call for call in runtime.workspace.write_file.call_args_list
            if call.args[0] == 'src/pages/index.tsx'
        )
        self.assertIn('source-backed', page_write.args[1])

    def test_u6_files_parse(self):
        for relative_path in (
            'services/source_framework/search_engine.py',
            'services/generation/engines/component_discovery_engine.py',
            'services/generation/engines/component_ranking_engine.py',
            'services/generation/engines/component_intelligence_engine.py',
            'services/generation/engines/code_generation_engine.py',
        ):
            ast.parse((ROOT / relative_path).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
