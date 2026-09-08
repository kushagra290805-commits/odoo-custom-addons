# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Any
from .provider_manager import ProviderManager
from .metadata_normalizer import MetadataNormalizer
from .dependency_resolver import DependencyResolver
from .compatibility_checker import CompatibilityChecker
from .quality_scorer import QualityScorer
from .domain_models import ComponentPackage

_logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self, provider_manager: ProviderManager):
        self.provider_manager = provider_manager
        self.normalizer = MetadataNormalizer()
        self.resolver = DependencyResolver()
        self.compatibility = CompatibilityChecker()
        self.scorer = QualityScorer()
        self.provider_errors: List[Dict[str, str]] = []
        
    def search(
        self,
        query: str,
        builder_context: Dict[str, Any],
        operation: str = 'SEARCH',
    ) -> List[Dict[str, Any]]:
        self.provider_errors = []
        component_source_providers = (
            self.provider_manager.get_capable_providers('COMPONENT_SOURCE')
            if operation == 'COMPONENT_SOURCE' else []
        )
        generic_search_providers = [
            provider_id
            for provider_id in self.provider_manager.get_capable_providers('SEARCH')
            if provider_id not in component_source_providers
        ]
        results: List[ComponentPackage] = []

        operations = [
            (provider_id, 'search', (query,))
            for provider_id in generic_search_providers
        ] + [
            (provider_id, 'discover_components', ())
            for provider_id in component_source_providers
        ]

        for provider_id, method, args in operations:
            try:
                provider_results = self.provider_manager.route_request(
                    provider_id, method, *args
                )
                items = provider_results if isinstance(provider_results, list) else [provider_results]
                for item in items:
                    if isinstance(item, ComponentPackage):
                        results.append(item)
                    else:
                        _logger.warning(
                            "Provider %s returned non-component output during %s; ignored: %s",
                            provider_id, method, type(item).__name__,
                        )
            except Exception as exc:
                failure = {
                    'provider': provider_id,
                    'operation': method,
                    'error': str(exc),
                }
                self.provider_errors.append(failure)
                _logger.warning(
                    "Component provider %s failed during %s: %s",
                    provider_id, method, exc,
                )
                
        # Normalize
        normalized_results = self.normalizer.normalize_list(results)
        
        # Enrich and score
        final_results = []
        for comp in normalized_results:
            comp = self.resolver.resolve_graph(comp)
            comp = self.compatibility.validate_context(comp, builder_context)
            score = self.scorer.score_component(comp)
            # Serialize for output
            final_results.append({
                "package": comp,
                "score": score
            })
            
        # SearchEngine is the sole owner of the component ranking decision.
        from .component_ranking_pipeline import ComponentRankingPipeline
        ranking_pipeline = ComponentRankingPipeline()
        final_results = ranking_pipeline.rank_components(final_results)
        
        return final_results
