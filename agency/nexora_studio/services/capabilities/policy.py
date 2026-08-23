from typing import List, Optional
from .models import CapabilityManifest, CapabilityDescriptor

class CapabilityPolicyEngine:
    def evaluate(self, candidates: List[CapabilityManifest], context: dict) -> Optional[CapabilityDescriptor]:
        if not candidates:
            return None

        # Phase 44.2 closure (C-05 / PV-11): one explicit, stated rule —
        # prefer a live connector-backed candidate over a registry-derived
        # one. The repository already orders candidates connector-first; this
        # rule makes selection independent of insertion order. No scoring
        # framework.
        best_candidate = next(
            (
                c for c in candidates
                if c.metadata.get('implementation_model') == 'connector'
                and c.metadata.get('source') == 'live_connector'
            ),
            candidates[0],
        )
        return CapabilityDescriptor(
            manifest=best_candidate,
            priority=100
        )
