import logging
from typing import List, Optional

from .base_provider import (
    CapabilityResolver,
    ProviderCategory,
    ProviderFeatureSet,
    ProviderExecutionContext,
    ExecutionPolicy,
    ExecutionPolicyType,
    BaseProvider,
    ProviderRegistry,
    ProviderFactory,
    ProviderStateMachine,
    ProviderMetricsService,
    CapabilityCache,
    ProviderFeatureNotSupportedError,
    ProviderServiceContainer
)

_logger = logging.getLogger(__name__)

class OdooCapabilityResolver(CapabilityResolver):
    """
    Resolves the best provider for a given capability request using Feature Negotiation
    and ExecutionPolicy ranking (ADR-0032).
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container

    @property
    def _registry(self) -> ProviderRegistry:
        return self._container.resolve(ProviderRegistry)

    @property
    def _factory(self) -> ProviderFactory:
        return self._container.resolve(ProviderFactory)

    @property
    def _state_machine(self) -> ProviderStateMachine:
        return self._container.resolve(ProviderStateMachine)

    @property
    def _metrics(self) -> ProviderMetricsService:
        return self._container.resolve(ProviderMetricsService)

    @property
    def _cap_cache(self) -> CapabilityCache:
        return self._container.resolve(CapabilityCache)

    def resolve(self, category: ProviderCategory, operation_type: str,
                required_features: ProviderFeatureSet, context: ProviderExecutionContext,
                policy: Optional[ExecutionPolicy] = None) -> BaseProvider:
        """
        Returns the highest-ranked provider that satisfies the requested features.
        """
        candidates = self.resolve_all(category, operation_type, required_features)
        
        if not candidates:
            # If a fallback policy is provided, we could try with relaxed constraints,
            # but usually fallback applies when primary policy yields empty results.
            # Here candidates are 0 before policy ranking.
            raise ProviderFeatureNotSupportedError(
                f"No provider found for {category.value}/{operation_type} satisfying {required_features}",
                provider_id="resolver"
            )

        policy = policy or ExecutionPolicy(policy_type=ExecutionPolicyType.BALANCED)
        ranked = self._rank_candidates(candidates, policy)
        
        if not ranked and policy.fallback_policy:
            ranked = self._rank_candidates(candidates, policy.fallback_policy)
            
        if not ranked:
            raise ProviderFeatureNotSupportedError(
                f"No provider satisfied the execution policy {policy.policy_type.value}.",
                provider_id="resolver"
            )

        best_provider = ranked[0]
        
        # Record selection in metrics
        self._metrics.record_selection(best_provider.metadata.provider_id, policy)
        
        return best_provider

    def resolve_all(self, category: ProviderCategory, operation_type: str,
                    required_features: ProviderFeatureSet) -> List[BaseProvider]:
        """
        Returns all providers that satisfy the feature constraints, without ranking.
        """
        candidates = []
        all_meta = self._registry.list_providers(category=category, active_only=True)
        
        for meta in all_meta:
            provider_id = meta.provider_id
            if not self._state_machine.is_invocable(provider_id):
                continue
                
            provider_class = self._registry.get_provider_class(provider_id)
            if not provider_class:
                continue
                
            # Instantiate provider with minimal context for capability check
            # In a highly optimized flow, we'd use a cached provider instance
            provider = provider_class(metadata=meta)
            
            # Fetch capabilities from cache
            capabilities = self._cap_cache.get_or_refresh(provider_id, provider)
            
            # Feature negotiation
            for cap in capabilities:
                if cap.operation_type == operation_type and required_features.is_satisfied_by(cap):
                    candidates.append(provider)
                    break
                    
        return candidates

    def _rank_candidates(self, candidates: List[BaseProvider], policy: ExecutionPolicy) -> List[BaseProvider]:
        """
        Ranks providers based on the requested ExecutionPolicyType.
        """
        if not candidates:
            return []
            
        if policy.policy_type == ExecutionPolicyType.CUSTOM and policy.custom_ranker:
            return policy.custom_ranker(candidates)
            
        if policy.policy_type == ExecutionPolicyType.PREFERRED:
            # Sort according to order in preferred_provider_ids list
            pref_list = policy.preferred_provider_ids
            def pref_score(p: BaseProvider):
                try:
                    return pref_list.index(p.metadata.provider_id)
                except ValueError:
                    return 999
            return sorted(candidates, key=pref_score)
            
        # For metric-based policies, fetch snapshots
        snapshots = {p.metadata.provider_id: self._metrics.get_snapshot(p.metadata.provider_id) for p in candidates}
        
        if policy.policy_type == ExecutionPolicyType.FASTEST:
            # Sort by p50 latency ascending
            return sorted(candidates, key=lambda p: snapshots[p.metadata.provider_id].p50_latency_ms)
            
        if policy.policy_type == ExecutionPolicyType.CHEAPEST:
            # Sort by priority weight since cost_rate isn't directly on metadata yet,
            # but assume priority_weight represents cost-efficiency if cost isn't there.
            # In ADR-0032 we mentioned cost_rate ascending. Let's use custom_attributes for cost_rate.
            return sorted(candidates, key=lambda p: p.metadata.custom_attributes.get('cost_rate', 1.0))
            
        if policy.policy_type == ExecutionPolicyType.HIGHEST_QUALITY:
            # success_rate DESC, priority_weight DESC
            def quality_score(p: BaseProvider):
                snap = snapshots[p.metadata.provider_id]
                sr = (snap.success_count / snap.request_count) if snap.request_count > 0 else 1.0
                # We want descending, so we return negative values
                return (-sr, -p.metadata.priority_weight)
            return sorted(candidates, key=quality_score)
            
        if policy.policy_type == ExecutionPolicyType.BALANCED:
            # Balanced: Latency (33%), Cost (33%), Quality (34%)
            # A simple heuristic score.
            def balanced_score(p: BaseProvider):
                snap = snapshots[p.metadata.provider_id]
                
                # Normalize latency (lower is better, so invert it)
                lat = snap.p50_latency_ms
                lat_score = 1000 / (lat + 1)
                
                # Cost score (lower is better, so invert)
                cost = p.metadata.custom_attributes.get('cost_rate', 1.0)
                cost_score = 10 / (cost + 0.1)
                
                # Quality score
                sr = (snap.success_count / snap.request_count) if snap.request_count > 0 else 1.0
                quality_score = (sr * 100) + p.metadata.priority_weight
                
                # Total weighted (higher is better)
                return (lat_score * 0.33) + (cost_score * 0.33) + (quality_score * 0.34)
                
            # Sort descending by score
            return sorted(candidates, key=balanced_score, reverse=True)

        return candidates
