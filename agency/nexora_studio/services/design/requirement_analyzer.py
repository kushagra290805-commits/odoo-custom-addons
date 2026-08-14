from typing import List, Dict, Any
from .blueprint_models import RawRequirement

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "SaaS": ["saas", "software", "platform", "tool", "dashboard", "app", "subscription", "dev tool"],
    "Ecommerce": ["shop", "store", "ecommerce", "product", "cart", "checkout", "retail", "buy", "sell"],
    "Portfolio": ["portfolio", "showcase", "gallery", "freelance", "personal", "creative"],
    "Agency": ["agency", "studio", "consulting", "firm", "marketing"],
    "Real Estate": ["real estate", "property", "properties", "realty", "homes", "housing"],
    "Healthcare": ["health", "medical", "clinic", "hospital", "doctor", "patient"],
    "Education": ["education", "courses", "learning", "school", "university", "training"],
    "Restaurant": ["restaurant", "cafe", "food", "menu", "reservation", "dining"],
}

class RequirementAnalyzer:
    """
    Parses and sanitizes raw user intents into structured requirements.
    """
    def analyze(self, intent: str) -> RawRequirement:
        # In a fully realized system, an LLM might perform semantic entity extraction here.
        # For ADR-0050 deterministic implementation, we use basic keyword mapping.

        lower_intent = intent.lower()
        req = RawRequirement(intent=intent)

        if "3d" in lower_intent:
            req.preferences["rendering"] = "webgl"
            req.preferences["animation"] = "complex"

        if "fast" in lower_intent or "performance" in lower_intent:
            req.constraints.append("strict_performance_budget")

        if "apple" in lower_intent:
            req.preferences["design_language"] = "premium_minimal"

        if "crypto" in lower_intent:
            req.preferences["design_language"] = "dark_neon"

        # Domain keyword detection — feeds into DOMAIN_TEMPLATES lookup in PlanningEngine
        detected_domain = "Agency"  # default
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw in lower_intent for kw in keywords):
                detected_domain = domain
                break
        req.preferences["domain"] = detected_domain

        req.preferences["features"] = []
        if "blog" in lower_intent:
            req.preferences["features"].append("BlogSystem")

        return req
