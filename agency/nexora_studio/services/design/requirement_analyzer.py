import re
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

# Phase 47.18 (Part A): labeled-brief field extraction. Realistic client
# briefs state their identity in labeled lines ("Business: ...",
# "Location & market: ..."). These patterns are brief-format aware and stay
# fully deterministic; absence of a label simply yields no extraction.
_FIELD_PATTERNS: Dict[str, re.Pattern] = {
    'business': re.compile(r'^\s*(?:business(?:\s*&\s*company)?|company)\s*:\s*(.+)$',
                           re.IGNORECASE | re.MULTILINE),
    'location': re.compile(r'^\s*(?:location(?:\s*&\s*market)?|market|based in)\s*:\s*(.+)$',
                           re.IGNORECASE | re.MULTILINE),
    'audience': re.compile(r'^\s*(?:target audience|audience)\s*:\s*(.+)$',
                           re.IGNORECASE | re.MULTILINE),
    'services': re.compile(r'^\s*services\s*:\s*(.+)$',
                           re.IGNORECASE | re.MULTILINE),
    'positioning': re.compile(r'^\s*(?:positioning|brand promise)\s*:\s*(.+)$',
                              re.IGNORECASE | re.MULTILINE),
    'differentiators': re.compile(r'^\s*differentiators\s*:\s*(.+)$',
                                  re.IGNORECASE | re.MULTILINE),
}

_LEADING_ARTICLE = re.compile(r'^\s*(?:a|an|the)\s+', re.IGNORECASE)


def _match_domain(text: str) -> str:
    """Phase 47.18 (Part A): word-boundary domain matching.

    A keyword only matches when it appears as a whole word/phrase, so
    "workshop" never matches the "shop" keyword and "architecture studio"
    resolves to Agency rather than Ecommerce. Multi-word keywords such as
    "real estate" match their exact phrase. All domains are considered and
    the EARLIEST keyword occurrence in the text wins, so "real estate firm"
    classifies as Real Estate (phrase at position 10) rather than Agency
    ("firm" at position 22).
    """
    lower = text.lower()
    best_domain = ""
    best_position = None
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            match = re.search(pattern, lower)
            if match and (best_position is None or match.start() < best_position):
                best_domain = domain
                best_position = match.start()
    return best_domain


class RequirementAnalyzer:
    """
    Parses and sanitizes raw user intents into structured requirements.
    """
    def analyze(self, intent: str) -> RawRequirement:
        # In a fully realized system, an LLM might perform semantic entity
        # extraction here. For ADR-0050 deterministic implementation, we use
        # word-boundary keyword mapping plus labeled-brief field extraction.

        lower_intent = intent.lower()
        req = RawRequirement(intent=intent)

        # Phase 47.18 (Part A): structured brief extraction. Explicit client
        # wording wins over generic keyword inference.
        business_match = _FIELD_PATTERNS['business'].search(intent)
        business_line = business_match.group(1).strip() if business_match else ''

        # Business name: the identity before a " - " description separator.
        business_name = ''
        business_category = ''
        if business_line:
            if ' - ' in business_line:
                business_name, _, description = business_line.partition(' - ')
                business_name = business_name.strip().strip('"').strip("'")
                business_category = _LEADING_ARTICLE.sub('', description.strip()).rstrip('.,')
            else:
                business_name = business_line.strip().strip('"').strip("'").rstrip('.,')

        location_match = _FIELD_PATTERNS['location'].search(intent)
        location = location_match.group(1).strip() if location_match else ''
        if location:
            # Trim trailing context clauses: "Copenhagen, Denmark; serving..."
            location = location.split(';')[0].strip().rstrip('.,')

        audience_match = _FIELD_PATTERNS['audience'].search(intent)
        target_audience = ''
        if audience_match:
            # Keep the primary audience clause (before the first comma).
            target_audience = audience_match.group(1).split(',')[0].strip().rstrip('.,')

        services_match = _FIELD_PATTERNS['services'].search(intent)
        services: List[str] = []
        if services_match:
            services = [
                s.strip().rstrip('.,')
                for s in services_match.group(1).split(',')
                if s.strip() and len(s.strip()) > 2
            ][:8]

        if business_name:
            req.preferences['business_name'] = business_name
        if business_category:
            req.preferences['business_category'] = business_category
        if location:
            req.preferences['location'] = location
        if target_audience:
            req.preferences['target_audience'] = target_audience
        if services:
            req.preferences['services'] = services

        # Phase 47.9 (U8): explicit Spline requirement detection. Checked before
        # the generic "3d" rule so "spline 3d scene" resolves to the Spline
        # renderer deterministically instead of falling into webgl/R3F.
        if re.search(r'\bspline\b', lower_intent):
            req.preferences["rendering"] = "spline"
            req.preferences["animation"] = "complex"
        elif re.search(r'\b3d\b', lower_intent):
            req.preferences["rendering"] = "webgl"
            req.preferences["animation"] = "complex"

        if re.search(r'\bfast\b|\bperformance\b', lower_intent):
            req.constraints.append("strict_performance_budget")

        # Phase 47.19 (Part D): the brief's technical requirements declaring
        # responsiveness/mobile support activate the bounded mobile viewport
        # validation in the existing browser-validation phase. Absent -> the
        # desktop contract remains completely unchanged.
        if re.search(r'\bresponsive\b|\bmobile\b', lower_intent):
            req.preferences["mobile_expected"] = True

        if re.search(r'\bapple\b', lower_intent):
            req.preferences["design_language"] = "premium_minimal"

        if re.search(r'\bcrypto\b', lower_intent):
            req.preferences["design_language"] = "dark_neon"

        # Domain keyword detection — feeds into DOMAIN_TEMPLATES lookup in
        # PlanningEngine. Phase 47.18 (Part A): word-boundary matching, with
        # explicit client wording (the business/category line) taking
        # precedence over incidental keywords elsewhere in the brief.
        detected_domain = ""
        if business_category:
            detected_domain = _match_domain(business_category)
        if not detected_domain:
            detected_domain = _match_domain(intent)
        req.preferences["domain"] = detected_domain or "Agency"

        req.preferences["features"] = []
        if re.search(r'\bblog\b', lower_intent):
            req.preferences["features"].append("BlogSystem")

        return req
