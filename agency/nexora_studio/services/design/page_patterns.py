# -*- coding: utf-8 -*-
"""Phase 47.24 (ADR-0076): deterministic page-pattern catalog.

A pattern is COMPOSITION METADATA, not a renderer: it names the section
sequence per page and the reason it was selected. The section builders
live in CodeGenerationEngine (deterministic scaffolds consuming the
ContentEngine artifact); this module never duplicates component
implementations — every pattern references the same shared builder ids.
"""
import re
from typing import Any, Dict, List, Optional

# Shared section builders (deterministic, owned by CodeGenerationEngine):
#   Hero          — LLM-generated (content adaptation) with 47.23 validation
#   Content       — LLM-generated (content adaptation) with 47.23 fallback
#   About         — deterministic content/overview block (Phase 47.25)
#   ServicesGrid  — deterministic grid (services + ContentEngine copy)
#   FeatureGrid   — deterministic feature grid (SaaS features; native
#                   FeatureGrid organism composes when matched)
#   MenuHighlights— deterministic featured-menu grid (restaurant; composes
#                   the matched card/feature-grid component)
#   Testimonial   — deterministic quote block (native Testimonial composes)
#   ContactCTA    — deterministic contact/CTA block (native Button composes)
#   Gallery       — deterministic stock-image grid (skipped without images)
_SHARED_BUILDERS = ("Hero", "Content", "About", "ServicesGrid", "FeatureGrid",
                    "MenuHighlights", "Pricing", "FAQ", "Testimonial",
                    "ContactCTA", "Gallery")

PAGE_PATTERN_CATALOG: Dict[str, Dict[str, Any]] = {
    'agency': {
        'id': 'agency',
        'suitable_domains': ['Agency'],
        'home_sections': ['Hero', 'ServicesGrid', 'Testimonial', 'Gallery', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        'reason_stub': [
            'agency domain classification',
            'services capability present',
            'testimonial content appropriate',
            'gallery imagery supports portfolio presentation',
        ],
    },
    'professional_service': {
        'id': 'professional_service',
        'suitable_domains': ['Consulting', 'Healthcare', 'Education', 'Real Estate'],
        'home_sections': ['Hero', 'ServicesGrid', 'Testimonial', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        'reason_stub': [
            'professional service domain classification',
            'services capability present',
            'testimonial content appropriate',
        ],
    },
    'restaurant': {
        'id': 'restaurant',
        'suitable_domains': ['Restaurant'],
        'home_sections': ['Hero', 'About', 'MenuHighlights', 'Gallery', 'Testimonial', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        'reason_stub': [
            'restaurant domain classification',
            'about/story section precedes the offer (information architecture)',
            'featured menu highlights instead of generic services',
            'gallery imagery appropriate for food/venue',
            'testimonial content appropriate',
        ],
    },
    'saas_product': {
        'id': 'saas_product',
        'suitable_domains': ['SaaS', 'Ecommerce', 'Portfolio'],
        'home_sections': ['Hero', 'FeatureGrid', 'Pricing', 'Testimonial', 'FAQ', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        'reason_stub': [
            'product/service domain classification',
            'feature grid communicates capabilities (not generic services)',
            'pricing plans are the primary conversion path for SaaS',
            'FAQ addresses evaluation-stage objections',
            'testimonial content appropriate',
        ],
    },
    'default': {
        'id': 'default',
        'suitable_domains': [],
        'home_sections': ['Hero', 'ServicesGrid', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        'reason_stub': [
            'no domain-specific pattern matched; standard composition applied',
        ],
    },
}

# Domain keyword routing (word-boundary) for domains missing from the
# explicit suitability lists.
_KEYWORD_ROUTES = [
    ('restaurant', ('restaurant', 'cafe', 'coffee', 'bistro', 'bakery',
                    'catering', 'pizzeria')),
    ('saas_product', ('saas', 'software', 'platform', 'startup', 'product',
                      'ecommerce', 'shop', 'store', 'portfolio')),
    ('professional_service', ('clinic', 'consulting', 'law', 'legal',
                              'dental', 'wellness', 'spa', 'real estate',
                              'education', 'school', 'training')),
    ('agency', ('agency', 'studio', 'design', 'marketing', 'architecture',
                'interior', 'photography', 'creative')),
]


def _word_match(text: str, keyword: str) -> bool:
    return re.search(r'\b' + re.escape(keyword.replace(' ', r'\s+')) + r'\b',
                     text) is not None


def select_pattern(domain: str, brief_text: str = '') -> Dict[str, Any]:
    """Deterministic, explainable pattern selection.

    Precedence: explicit domain suitability → brief keyword routing →
    default composition. Returns the pattern dict (with a materialized
    `reason` list); never raises.
    """
    domain = (domain or '').strip()
    for pattern in PAGE_PATTERN_CATALOG.values():
        if domain and domain in pattern['suitable_domains']:
            out = dict(pattern)
            out['reason'] = list(pattern['reason_stub'])
            return out

    text = ' ' + (brief_text or '').lower() + ' ' + (domain or '').lower() + ' '
    for pattern_id, keywords in _KEYWORD_ROUTES:
        for kw in keywords:
            if kw and _word_match(text, kw):
                out = dict(PAGE_PATTERN_CATALOG[pattern_id])
                out['reason'] = ['brief keyword: %s' % kw] + list(
                    PAGE_PATTERN_CATALOG[pattern_id]['reason_stub'])
                return out

    out = dict(PAGE_PATTERN_CATALOG['default'])
    out['reason'] = list(PAGE_PATTERN_CATALOG['default']['reason_stub'])
    return out


def pattern_sections(pattern: Optional[Dict[str, Any]], is_home: bool) -> List[str]:
    """Section sequence for a page under the selected pattern."""
    if not pattern:
        return ['Hero', 'Content']
    key = 'home_sections' if is_home else 'secondary_sections'
    return list(pattern.get(key) or ['Hero', 'Content'])
