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
        # Phase 47.40: page-purpose-aware secondary compositions —
        # deterministic per route, built ONLY from shared builders.
        'secondary_pages': {
            'services': ['Hero', 'ServicesGrid', 'Testimonial'],
            'work': ['Hero', 'Gallery', 'Testimonial'],
            'contact': ['Hero', 'Content'],
        },
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
        'secondary_pages': {
            'services': ['Hero', 'ServicesGrid', 'Testimonial'],
            'about': ['Hero', 'About', 'Testimonial'],
            'contact': ['Hero', 'Content'],
        },
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
        # Phase 47.40: menu/reservation-purpose compositions.
        'secondary_pages': {
            'menu': ['Hero', 'MenuHighlights', 'Gallery'],
            'reservations': ['Hero', 'About', 'ContactCTA'],
            'contact': ['Hero', 'Content'],
        },
        'reason_stub': [
            'restaurant domain classification',
            'about/story section precedes the offer (information architecture)',
            'featured menu highlights instead of generic services',
            'gallery imagery appropriate for food/venue',
            'testimonial content appropriate',
        ],
    },
    'portfolio': {
        'id': 'portfolio',
        'suitable_domains': ['Portfolio'],
        'home_sections': ['Hero', 'About', 'Gallery', 'Testimonial', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        # Phase 47.40: project/about-purpose compositions — the body of
        # work leads on the projects page; the story leads on about.
        'secondary_pages': {
            'projects': ['Hero', 'Gallery', 'Testimonial'],
            'work': ['Hero', 'Gallery', 'Testimonial'],
            'about': ['Hero', 'About', 'Gallery'],
            'contact': ['Hero', 'Content'],
        },
        'reason_stub': [
            'portfolio domain classification',
            'about/story precedes the work (artist statement)',
            'gallery presents the body of work as primary content',
            'testimonial from editors/clients appropriate',
        ],
    },
    'saas_product': {
        'id': 'saas_product',
        'suitable_domains': ['SaaS'],
        'home_sections': ['Hero', 'FeatureGrid', 'Pricing', 'Testimonial', 'FAQ', 'ContactCTA'],
        'secondary_sections': ['Hero', 'Content'],
        # Phase 47.40: product/value/pricing/FAQ-purpose compositions.
        'secondary_pages': {
            'pricing': ['Hero', 'Pricing', 'FAQ'],
            'features': ['Hero', 'FeatureGrid', 'FAQ'],
            'contact': ['Hero', 'Content'],
        },
        'reason_stub': [
            'product/service domain classification',
            'feature grid communicates capabilities (not generic services)',
            'pricing plans are the primary conversion path for SaaS',
            'FAQ addresses evaluation-stage objections',
            'testimonial content appropriate',
        ],
    },
    'ecommerce': {
        'id': 'ecommerce',
        'suitable_domains': ['Ecommerce'],
        'home_sections': ['Hero', 'MenuHighlights', 'About', 'Gallery', 'ContactCTA'],
        'secondary_sections': ['Hero', 'MenuHighlights'],
        # Phase 47.40: product-discovery-purpose compositions.
        'secondary_pages': {
            'products': ['Hero', 'MenuHighlights', 'Gallery'],
            'shop': ['Hero', 'MenuHighlights', 'Gallery'],
            'collections': ['Hero', 'MenuHighlights', 'About'],
            'contact': ['Hero', 'About', 'ContactCTA'],
        },
        'reason_stub': [
            'ecommerce domain classification',
            'product/catalog grid is the primary conversion path (not SaaS pricing)',
            'craft/about precedes the offer (provider trust)',
            'gallery imagery supports product storytelling',
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
    ('ecommerce', ('ecommerce', 'shop', 'store', 'ceramics', 'textiles',
                   'goods', 'product', 'catalog', 'retail')),
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


def _route_purpose(path: str) -> str:
    """Phase 47.40: bounded route→purpose keyword ('/menu' → 'menu').
    The first path segment is the page's purpose token; unknown routes
    have no purpose (the pattern's default secondary composition
    applies)."""
    segments = [s for s in str(path or '').strip('/').split('/') if s]
    if not segments:
        return ''
    return segments[0].lower()


def pattern_sections(pattern: Optional[Dict[str, Any]], is_home: bool,
                     path: str = '') -> List[str]:
    """Section sequence for a page under the selected pattern.

    Phase 47.40: secondary pages resolve their composition from the
    pattern's ``secondary_pages`` table by route PURPOSE (deterministic
    page-purpose-aware composition — no randomization, no forced
    sections; every sequence references only the shared builders).
    Falls back to the pattern's ``secondary_sections`` for routes
    without a purpose entry."""
    if not pattern:
        return ['Hero', 'Content']
    if is_home:
        return list(pattern.get('home_sections') or ['Hero', 'Content'])
    purpose = _route_purpose(path)
    secondary_pages = pattern.get('secondary_pages') or {}
    if purpose and purpose in secondary_pages:
        return list(secondary_pages[purpose])
    return list(pattern.get('secondary_sections') or ['Hero', 'Content'])
