import logging
from typing import List, Dict, Any, Optional
from .models import CapabilityResult
from .resolver import CapabilityResolver
from .router import UniversalCapabilityRouter
from .provider_ranker import ProviderRanker
from .health import RuntimeHealthRegistry, ProviderHealthState

_logger = logging.getLogger(__name__)

class CapabilitySelectionEngine:
    """
    Implements ADR-0047 Capability Selection Engine.
    Responsibilities:
    - Capability-based provider discovery
    - Filtering (Lifecycle, Health, Auth)
    - Ranking (delegated to ProviderRanker)
    - Automatic Failover
    """
    
    def __init__(self, resolver: CapabilityResolver, router: UniversalCapabilityRouter):
        self.resolver = resolver
        self.router = router
        self.ranker = ProviderRanker()
        self.health = RuntimeHealthRegistry()
        
    def discover_candidates(self, capability: str) -> List[Dict[str, Any]]:
        """
        Discovers and ranks viable providers for a given semantic capability.
        Returns the ranked chain with explanation.
        """
        candidates = self.resolver.resolve_by_capability(capability)
        
        # Filtering
        viable = []
        for c in candidates:
            # 1. Filter Lifecycle
            lifecycle = c.metadata.get('lifecycle', 'planned')
            if lifecycle in ['planned', 'deprecated']:
                continue
                
            # 2. Filter Runtime Health
            state = self.health.get_health(c.namespace)
            if state in [ProviderHealthState.OFFLINE, ProviderHealthState.MAINTENANCE]:
                continue
                
            viable.append(c)
            
        # Ranking
        ranked_tuples = self.ranker.rank_candidates(viable, capability)
        
        return [{
            "manifest": t[0],
            "namespace": t[0].namespace,
            "score": t[1],
            "details": t[2]
        } for t in ranked_tuples]
        
    def execute_capability(self, capability: str, payload: dict, context: dict = None) -> CapabilityResult:
        """
        Executes a capability by trying the best provider and automatically failing over if necessary.
        """
        context = context or {}
        chain = self.discover_candidates(capability)
        
        if not chain:
            return CapabilityResult(success=False, result=None, logs=[f"No viable providers found for capability: {capability}"])
            
        execution_trace = []
        
        for candidate in chain:
            namespace = candidate['namespace']
            _logger.info(f"CapabilitySelectionEngine: Attempting {namespace} (Score: {candidate['score']}) for {capability}")
            
            try:
                # Execute through UCEL
                result = self.router.execute(namespace, payload, context)
                
                # If success, return immediately
                if getattr(result, 'success', False):
                    execution_trace.append({"namespace": namespace, "status": "success"})
                    # Inject trace into logs
                    logs = getattr(result, 'logs', [])
                    logs.append(f"CSE Execution Trace: {execution_trace}")
                    setattr(result, 'logs', logs)
                    return result
                    
                # If it failed, record failure and failover to next
                execution_trace.append({"namespace": namespace, "status": "failed", "logs": getattr(result, 'logs', [])})
                _logger.warning(f"Provider {namespace} failed for capability {capability}. Failing over...")
                
            except Exception as e:
                execution_trace.append({"namespace": namespace, "status": "error", "error": str(e)})
                _logger.error(f"Provider {namespace} threw an unhandled exception: {e}. Failing over...")
                
        # If we exhausted the chain without success
        return CapabilityResult(
            success=False, 
            result=None, 
            logs=[f"All providers failed for capability {capability}. Trace: {execution_trace}"]
        )

    # --- Discovery APIs ---
    def get_failover_chain(self, capability: str) -> List[str]:
        chain = self.discover_candidates(capability)
        return [c['namespace'] for c in chain]
        
    def explain_ranking(self, capability: str) -> dict:
        chain = self.discover_candidates(capability)
        return {
            "capability": capability,
            "ranked_providers": [
                {
                    "namespace": c['namespace'],
                    "score": c['score'],
                    "breakdown": c['details']
                } for c in chain
            ]
        }
