from typing import List, Optional
from .models import CapabilityManifest, CapabilityDescriptor

class CapabilityPolicyEngine:
    def evaluate(self, candidates: List[CapabilityManifest], context: dict) -> Optional[CapabilityDescriptor]:
        if not candidates:
            return None
        # Naive implementation: pick first candidate. Policy logic expands here.
        best_candidate = candidates[0]
        return CapabilityDescriptor(
            manifest=best_candidate,
            priority=100
        )