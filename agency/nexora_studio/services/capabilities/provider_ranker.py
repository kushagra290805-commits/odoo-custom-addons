from typing import List, Dict, Any, Tuple
from .models import CapabilityManifest
from .health import RuntimeHealthRegistry, ProviderHealthState

class ProviderRanker:
    """
    Responsible for deterministic scoring and weighted ranking of capability providers.
    Delegates all discovery to the resolver, and focuses purely on ranking logic.
    """
    
    def __init__(self):
        self.health_registry = RuntimeHealthRegistry()
        
    def score_manifest(self, manifest: CapabilityManifest, requested_capability: str) -> Tuple[int, Dict[str, Any]]:
        """
        Calculates a deterministic score for a manifest based on:
        1. Lifecycle (Production > Verified)
        2. Runtime Health
        3. Priority (from metadata)
        4. Estimated Latency (Inverse)
        """
        score = 0
        details = {}
        
        # 1. Lifecycle Score (Max 200)
        lifecycle = manifest.metadata.get('lifecycle', 'planned')
        if lifecycle == 'production':
            lifecycle_score = 200
        elif lifecycle == 'verified':
            lifecycle_score = 150
        elif lifecycle == 'experimental':
            lifecycle_score = 50
        else:
            lifecycle_score = 0
        score += lifecycle_score
        details['lifecycle'] = lifecycle_score
        
        # 2. Runtime Health Score (Max 300)
        health = self.health_registry.get_health(manifest.namespace)
        if health == ProviderHealthState.HEALTHY:
            health_score = 300
        elif health == ProviderHealthState.DEGRADED:
            health_score = 100
        else:
            health_score = 0 # OFFLINE or MAINTENANCE should be filtered before this, but if passed, score 0
        score += health_score
        details['health'] = health_score
        
        # 3. Priority Score (Max 1000 - typically 1-100 mapped linearly)
        # Assuming priority in config is 1-100, where 100 is highest.
        priority = manifest.metadata.get('priority', 50)
        priority_score = priority * 4
        score += priority_score
        details['priority'] = priority_score
        
        # 4. Latency Inverse Score (Max 100)
        # Latency is estimated in ms. 0 ms = 100 score, 2000 ms = 0 score
        latency = manifest.metadata.get('estimated_latency_ms', 500)
        latency_score = max(0, 100 - int(latency / 20))
        score += latency_score
        details['latency'] = latency_score
        
        details['total_score'] = score
        return score, details

    def rank_candidates(self, candidates: List[CapabilityManifest], requested_capability: str) -> List[Tuple[CapabilityManifest, int, Dict[str, Any]]]:
        """
        Ranks candidates and returns an ordered list of tuples: (Manifest, Score, Details)
        """
        ranked = []
        for c in candidates:
            score, details = self.score_manifest(c, requested_capability)
            ranked.append((c, score, details))
            
        # Sort descending by score
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
