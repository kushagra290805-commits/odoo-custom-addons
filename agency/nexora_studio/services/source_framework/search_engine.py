# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from .provider_manager import ProviderManager
from .metadata_normalizer import MetadataNormalizer
from .dependency_resolver import DependencyResolver
from .compatibility_checker import CompatibilityChecker
from .quality_scorer import QualityScorer
from .domain_models import ComponentPackage

class SearchEngine:
    def __init__(self, provider_manager: ProviderManager):
        self.provider_manager = provider_manager
        self.normalizer = MetadataNormalizer()
        self.resolver = DependencyResolver()
        self.compatibility = CompatibilityChecker()
        self.scorer = QualityScorer()
        
    def search(self, query: str, builder_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        capable_providers = self.provider_manager.get_capable_providers('SEARCH')
        results: List[ComponentPackage] = []
        
        for provider_id in capable_providers:
            try:
                # Route request via ProviderManager
                provider_results = self.provider_manager.route_request(provider_id, 'search', query)
                results.extend(provider_results)
            except Exception as e:
                # Log failure but continue federated search
                pass
                
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
            
        # Apply Component Ranking Pipeline
        from .component_ranking_pipeline import ComponentRankingPipeline
        ranking_pipeline = ComponentRankingPipeline()
        final_results = ranking_pipeline.rank_components(final_results)
        
        return final_results
