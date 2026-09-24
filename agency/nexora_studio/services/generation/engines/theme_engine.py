import logging
import re
from typing import Any, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Theme

_logger = logging.getLogger(__name__)

def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3: hex_color = ''.join(c + c for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def luminance(r: int, g: int, b: int) -> float:
    a = [v / 255 for v in (r, g, b)]
    a = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in a]
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722

def contrast_ratio(hex1: str, hex2: str) -> float:
    try:
        l1 = luminance(*hex_to_rgb(hex1))
        l2 = luminance(*hex_to_rgb(hex2))
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
    except:
        return 1.0


def _adjust_until_contrast(color: str, base: str, target: float = 4.5) -> str:
    """Deterministically darken/lighten `color` until it reaches `target`
    contrast against `base`. Bounded steps (never loops forever)."""
    try:
        r, g, b = hex_to_rgb(color)
    except Exception:
        return '#000000' if luminance(*hex_to_rgb(base)) > 0.4 else '#ffffff'
    toward_dark = luminance(*hex_to_rgb(base)) > 0.4  # light base -> darken text
    for _ in range(40):
        if contrast_ratio(color, base) >= target:
            return color
        if toward_dark:
            r, g, b = int(r * 0.92), int(g * 0.92), int(b * 0.92)
        else:
            r, g, b = min(255, int(r * 1.08) + 1), min(255, int(g * 1.08) + 1), min(255, int(b * 1.08) + 1)
        color = '#%02x%02x%02x' % (r, g, b)
    return color


# ------------------------------------------------------------------
# Phase 47.23 (ADR-0075): constrained, brief-derived palette families.
# Each family defines semantic tokens; AA contrast for the text-bearing
# pairs is enforced at derivation time (_derive_palette guard). Selection
# is deterministic: explicit design language wins, then domain/category
# keyword matching. No LLM call — ThemeEngine stays the single owner.
#
# Phase 47.40: routing is CATEGORY/DOMAIN-AWARE. The palette family is
# routed on the bounded identity signals (domain + business_category)
# with specific verticals checked before broad studio terms, so a
# restaurant mentioning a "gallery" page or a brief with the word
# "design" can never be captured by warm_stone. Two families were added
# for previously unrouted verticals (craft ecommerce → linen,
# photography/visual portfolio → gallery).
# ------------------------------------------------------------------

_PALETTE_FAMILIES = {
    # Premium architecture / studio / editorial — warm stone + bronze ink.
    'warm_stone': {
        'background': '#faf9f7', 'foreground': '#292524',
        'primary': '#8a5a2b', 'primary_foreground': '#ffffff',
        'secondary': '#57534e', 'accent': '#b45309',
        'border': '#e7e5e4', 'muted': '#79716b', 'card': '#ffffff',
        'font_heading': 'Playfair Display', 'font_body': 'Source Sans 3',
    },
    # Charcoal + champagne — editorial premium minimal.
    'ink_champagne': {
        'background': '#f7f5f2', 'foreground': '#1c1917',
        'primary': '#1c1917', 'primary_foreground': '#f7f5f2',
        'secondary': '#57534e', 'accent': '#8a5a2b',
        'border': '#e2ddd5', 'muted': '#6f6a63', 'card': '#ffffff',
        'font_heading': 'Playfair Display', 'font_body': 'Source Sans 3',
    },
    # Dark tech / crypto — deep navy + electric cyan.
    'dark_neon': {
        'background': '#0b1220', 'foreground': '#e2e8f0',
        'primary': '#22d3ee', 'primary_foreground': '#082f49',
        'secondary': '#94a3b8', 'accent': '#a78bfa',
        'border': '#1e293b', 'muted': '#94a3b8', 'card': '#111a2e',
        'font_heading': 'Space Grotesk', 'font_body': 'Inter',
    },
    # Deep indigo — SaaS / software / data.
    'deep_indigo': {
        'background': '#f8f7ff', 'foreground': '#1e1b4b',
        'primary': '#4338ca', 'primary_foreground': '#ffffff',
        'secondary': '#4c5064', 'accent': '#7c3aed',
        'border': '#e4e2f2', 'muted': '#6b6e84', 'card': '#ffffff',
        'font_heading': 'Space Grotesk', 'font_body': 'Inter',
    },
    # Sage — health / wellness / spa.
    'sage': {
        'background': '#f7faf7', 'foreground': '#1f2a24',
        'primary': '#2f6b4f', 'primary_foreground': '#ffffff',
        'secondary': '#4b5b52', 'accent': '#6b9e78',
        'border': '#dfe9e0', 'muted': '#5d6b62', 'card': '#ffffff',
        'font_heading': 'Lora', 'font_body': 'Inter',
    },
    # Terracotta — restaurant / cafe / food.
    'terracotta': {
        'background': '#fdf9f5', 'foreground': '#3b241c',
        'primary': '#9a3412', 'primary_foreground': '#ffffff',
        'secondary': '#6d5344', 'accent': '#c2410c',
        'border': '#f0e4da', 'muted': '#7c6053', 'card': '#ffffff',
        'font_heading': 'Playfair Display', 'font_body': 'Source Sans 3',
    },
    # Slate — professional default (deliberately not the old #3b82f6).
    'slate': {
        'background': '#f8fafc', 'foreground': '#0f172a',
        'primary': '#3f5c76', 'primary_foreground': '#ffffff',
        'secondary': '#475569', 'accent': '#0e7490',
        'border': '#e2e8f0', 'muted': '#5f6b7a', 'card': '#ffffff',
        'font_heading': 'Space Grotesk', 'font_body': 'Inter',
    },
    # Linen — craft ecommerce / objects / warm-neutral retail (Phase 47.40).
    'linen': {
        'background': '#faf8f5', 'foreground': '#33302a',
        'primary': '#6b5d4f', 'primary_foreground': '#ffffff',
        'secondary': '#5c564d', 'accent': '#8a6d4a',
        'border': '#e8e2d8', 'muted': '#6f6a60', 'card': '#ffffff',
        'font_heading': 'DM Sans', 'font_body': 'Inter',
    },
    # Gallery — photography / visual portfolio, monochrome image-led
    # (Phase 47.40): the imagery carries the color; chrome stays neutral.
    'gallery': {
        'background': '#fcfcfc', 'foreground': '#17171a',
        'primary': '#23262d', 'primary_foreground': '#ffffff',
        'secondary': '#4b5058', 'accent': '#6b7280',
        'border': '#e5e7eb', 'muted': '#6b7280', 'card': '#ffffff',
        'font_heading': 'Work Sans', 'font_body': 'DM Sans',
    },
}

# Phase 47.40: palette routing.
#
# 1. Explicit design language (unchanged contract).
# 2. DOMAIN — the bounded classification signal every other composition
#    owner (page_patterns, AssetEngine) already uses.
# 3. Business-category keyword scan, SPECIFIC VERTICALS FIRST: a
#    restaurant/cafe/food brief can never be captured by the broad
#    studio/design terms, and an ecommerce/craft brief never by the
#    photography terms. The joined raw brief is NEVER scanned — that
#    was the 47.39B convergence root cause (a "Pages: ... Gallery ..."
#    line or an audience phrase routed unrelated domains to warm_stone).
_DOMAIN_FAMILY_ROUTES = {
    'Restaurant': 'terracotta',
    'SaaS': 'deep_indigo',
    'Ecommerce': 'linen',
    'Portfolio': 'gallery',
    'Agency': 'warm_stone',
    'Real Estate': 'warm_stone',
    'Healthcare': 'sage',
    'Education': 'slate',
}

# Specificity-ordered category routes (checked only when the domain is
# absent/unclassified): vertical families first, broad studio terms last.
_CATEGORY_FAMILY_ROUTES = [
    ('terracotta', ('restaurant', 'cafe', 'coffee', 'food', 'bakery',
                    'pizzeria', 'bistro', 'catering', 'hospitality', 'bar',
                    'dining', 'trattoria', 'osteria', 'menu')),
    ('sage', ('health', 'wellness', 'spa', 'dental', 'clinic', 'medical',
              'yoga', 'therapy', 'pharmacy')),
    ('deep_indigo', ('saas', 'software', 'tech', 'technology', 'crypto',
                     'startup', 'data', 'platform', 'developer', 'ai',
                     'analytics', 'fintech', 'b2b', 'subscription')),
    ('linen', ('ecommerce', 'shop', 'store', 'retail', 'ceramics',
               'textiles', 'goods', 'catalog', 'boutique')),
    ('gallery', ('photography', 'photographer', 'showcase', 'gallery')),
    ('warm_stone', ('architecture', 'interior', 'studio', 'design',
                    'agency', 'consulting', 'law', 'legal', 'finance',
                    'real estate', 'realestate', 'luxury', 'atelier')),
]


def _select_family(design_lang: str, brief_text: str, domain: str = '',
                   business_category: str = '') -> str:
    """Deterministic palette-family routing (Phase 47.40).

    Precedence: explicit design language → domain → business-category
    keywords (specificity-ordered) → slate. The ``brief_text`` argument is
    the BOUNDED identity signal (business_category / branding category),
    never the joined raw brief — page-list and audience phrasing cannot
    influence palette routing.
    """
    lang = (design_lang or '').strip().lower()
    if lang == 'dark_neon':
        return 'dark_neon'
    if lang == 'premium_minimal':
        return 'ink_champagne'
    family = _DOMAIN_FAMILY_ROUTES.get((domain or '').strip())
    if family:
        return family
    text = ' ' + ' '.join(filter(None, [
        business_category or '', brief_text or ''])).lower() + ' '
    for family, keywords in _CATEGORY_FAMILY_ROUTES:
        for kw in keywords:
            if kw and re_search_word(text, kw):
                return family
    return 'slate'


def re_search_word(text: str, kw: str) -> bool:
    return re.search(r'\b' + re.escape(kw.replace(' ', r'\s+')) + r'\b', text) is not None


# Google Fonts families available for deterministic webfont loading.
_WEBFONT_FAMILIES = {
    'Inter', 'Playfair Display', 'Source Sans 3', 'Space Grotesk',
    'Lora', 'Cormorant Garamond', 'Work Sans', 'DM Sans',
}


# ------------------------------------------------------------------
# Phase 47.40: TYPOGRAPHY DECOUPLING. The font pair is no longer locked
# to the palette family — it is a second bounded axis selected from
# fixed pairs by deterministic identity signals (positioning /
# differentiators / category / the brief's explicit visual line). All
# pairs use only _WEBFONT_FAMILIES names; explicit brief-requested
# webfonts (validated aliases) always win.
# ------------------------------------------------------------------

_FONT_PAIRS = {
    'editorial_serif': ('Playfair Display', 'Source Sans 3'),
    'grotesk_tech': ('Space Grotesk', 'Inter'),
    'humanist_serif': ('Lora', 'Inter'),
    'garamond_craft': ('Cormorant Garamond', 'Work Sans'),
    'geometric_clean': ('DM Sans', 'Inter'),
    'modern_workhorse': ('Work Sans', 'DM Sans'),
}

_FAMILY_DEFAULT_TYPOGRAPHY = {
    'warm_stone': 'editorial_serif',
    'ink_champagne': 'editorial_serif',
    'dark_neon': 'grotesk_tech',
    'deep_indigo': 'grotesk_tech',
    'sage': 'humanist_serif',
    'terracotta': 'editorial_serif',
    'slate': 'grotesk_tech',
    'linen': 'geometric_clean',
    'gallery': 'modern_workhorse',
}

# Ordered signal groups: the FIRST group with a match wins (heritage is a
# stronger identity signal than publication style, which is stronger than
# a technical register). Word-boundary matching over the bounded identity
# signal text only.
_TYPOGRAPHY_SIGNALS = [
    ('garamond_craft', ('heritage', 'craft', 'artisan', 'handmade',
                        'family-run', 'small-batch', 'slowly', 'tradition',
                        'traditional', 'kiln', 'weaving', 'woodwork')),
    ('editorial_serif', ('editorial', 'magazine', 'publication',
                         'storytelling', 'narrative', 'story-led')),
    ('grotesk_tech', ('technical', 'engineering', 'data', 'api',
                      'platform', 'developer', 'analytic', 'dashboard',
                      'infrastructure')),
]

# Brief lines may request webfonts explicitly ("Playfair + Source Sans").
# Bounded alias table — unknown font names are ignored, never fabricated.
_WEBFONT_ALIASES = [
    ('playfair', 'Playfair Display'),
    ('source sans', 'Source Sans 3'),
    ('space grotesk', 'Space Grotesk'),
    ('cormorant', 'Cormorant Garamond'),
    ('work sans', 'Work Sans'),
    ('dm sans', 'DM Sans'),
    ('lora', 'Lora'),
    ('inter', 'Inter'),
]


def _select_typography(family: str, signal_text: str):
    """Deterministic typography-direction selection (Phase 47.40).

    Returns (direction, heading_font, body_font). Explicit brief-requested
    webfonts (validated aliases) win; else the first matching signal
    group; else the family default. Never raises."""
    direction = _FAMILY_DEFAULT_TYPOGRAPHY.get(family, 'grotesk_tech')
    heading, body = _FONT_PAIRS[direction]
    text = ' ' + (signal_text or '').lower() + ' '
    # Explicit (validated) brief font requests take precedence.
    requested = [canonical for alias, canonical in _WEBFONT_ALIASES
                 if re_search_word(text, alias)]
    if requested:
        heading = requested[0]
        body = requested[1] if len(requested) > 1 else body
        if heading not in _WEBFONT_FAMILIES:
            heading = 'Inter'
        if body not in _WEBFONT_FAMILIES:
            body = 'Inter'
        return 'brief_requested', heading, body
    for direction_key, keywords in _TYPOGRAPHY_SIGNALS:
        for kw in keywords:
            if kw and re_search_word(text, kw):
                heading, body = _FONT_PAIRS[direction_key]
                return direction_key, heading, body
    return direction, heading, body


# ------------------------------------------------------------------
# Phase 47.40: VISUAL-DIRECTION POLICY (Nexora-owned, deterministic).
#
# The policy evaluates the EXISTING requirement signals — domain,
# business category, positioning, differentiators, and the brief's
# labeled visual line — through fixed, bounded tables. Identical briefs
# produce identical directions; different briefs differ for
# semantically legitimate reasons. The LLM never selects visual values;
# every axis value is enumerated and validated here.
# ------------------------------------------------------------------

_DENSITY_SCALES = {
    'compact': {'spacing-xs': '0.25rem', 'spacing-sm': '0.375rem',
                'spacing-md': '0.75rem', 'spacing-lg': '1.5rem',
                'spacing-xl': '3rem', 'spacing-2xl': '4.5rem'},
    'standard': {'spacing-xs': '0.25rem', 'spacing-sm': '0.5rem',
                 'spacing-md': '1rem', 'spacing-lg': '2rem',
                 'spacing-xl': '4rem', 'spacing-2xl': '6rem'},
    'airy': {'spacing-xs': '0.3125rem', 'spacing-sm': '0.625rem',
             'spacing-md': '1.25rem', 'spacing-lg': '2.5rem',
             'spacing-xl': '5rem', 'spacing-2xl': '7.5rem'},
}

_CORNER_SCALES = {
    'sharp': {'radius-sm': '2px', 'radius-md': '4px', 'radius-lg': '6px'},
    'soft': {'radius-sm': '4px', 'radius-md': '8px', 'radius-lg': '12px'},
    'rounded': {'radius-sm': '8px', 'radius-md': '14px',
                'radius-lg': '20px'},
}

_DEPTH_SCALES = {
    'flat': {'shadow-sm': 'none', 'shadow-md': 'none',
             'shadow-lg': 'none'},
    'subtle': {'shadow-sm': '0 1px 2px rgba(0,0,0,0.04)',
               'shadow-md': '0 2px 4px -1px rgba(0,0,0,0.07)',
               'shadow-lg': '0 6px 12px -3px rgba(0,0,0,0.08)'},
    'elevated': {'shadow-sm': '0 1px 2px rgba(0,0,0,0.05)',
                 'shadow-md': '0 4px 6px -1px rgba(0,0,0,0.1)',
                 'shadow-lg': '0 10px 15px -3px rgba(0,0,0,0.1)'},
}

_MOTION_SCALES = {
    'none': {'motion-fast': '0ms', 'motion-normal': '0ms',
             'motion-slow': '0ms'},
    'subtle': {'motion-fast': '120ms ease-out',
               'motion-normal': '240ms ease-out',
               'motion-slow': '400ms ease-out'},
    'standard': {'motion-fast': '150ms ease-in-out',
                 'motion-normal': '300ms ease-in-out',
                 'motion-slow': '500ms ease-in-out'},
    'expressive': {'motion-fast': '180ms cubic-bezier(0.22, 1, 0.36, 1)',
                   'motion-normal': '350ms cubic-bezier(0.22, 1, 0.36, 1)',
                   'motion-slow': '600ms cubic-bezier(0.22, 1, 0.36, 1)'},
}

# Per-axis signal tables (ordered; first match wins) and domain defaults.
_DENSITY_SIGNALS = [
    ('airy', ('generous whitespace', 'whitespace', 'airy', 'breathing',
              'calm', 'serene', 'uncluttered')),
    ('compact', ('data-dense', 'dense', 'compact', 'dashboard', 'matrix',
                 'inventory', 'high-volume')),
]
_DENSITY_DOMAIN_DEFAULTS = {
    'Portfolio': 'airy', 'Restaurant': 'airy', 'SaaS': 'compact',
    'Ecommerce': 'standard', 'Agency': 'standard',
}

_CORNER_SIGNALS = [
    ('sharp', ('precision', 'precise', 'engineering', 'technical',
               'monochrome', 'data-viz', 'architectural', 'brutalist')),
    ('rounded', ('warmth', 'warm', 'friendly', 'family', 'community',
                 'care', 'organic', 'soft', 'playful')),
]
_CORNER_DOMAIN_DEFAULTS = {
    'Portfolio': 'sharp', 'Agency': 'sharp', 'Restaurant': 'rounded',
    'Healthcare': 'rounded', 'SaaS': 'soft', 'Ecommerce': 'soft',
}

_DEPTH_SIGNALS = [
    ('flat', ('flat', 'print-inspired', 'paper', 'monochrome',
              'image-led', 'minimal')),
    ('elevated', ('product-led', 'dimensional', 'layered',
                  'interactive', 'dashboard')),
]
_DEPTH_DOMAIN_DEFAULTS = {
    'SaaS': 'elevated',
}

_MOTION_SIGNALS = [
    ('none', ('fast loading', 'performance budget', 'reduced motion',
              'motion-sensitive')),
    ('expressive', ('playful', 'energetic', 'bold', 'experimental',
                    'vibrant', 'youthful')),
    ('standard', ('interactive', 'dynamic', 'animated', 'analytic',
                  'analytics', 'dashboard', 'motion')),
]

_COMPOSITION_SIGNALS = [
    ('immersive', ('immersive', 'showcase', 'image-led', 'full-bleed')),
    ('editorial', ('editorial', 'magazine', 'storytelling', 'narrative')),
    ('grid', ('catalog', 'product grid', 'inventory', 'collection')),
]
_COMPOSITION_DOMAIN_DEFAULTS = {
    'Restaurant': 'editorial', 'Portfolio': 'immersive',
    'Ecommerce': 'grid', 'Agency': 'editorial', 'SaaS': 'centered',
}

# Home hero variant per composition style (the native Hero organism
# already implements all three variants). Secondary pages use the
# lighter mapping in _SECONDARY_HERO_VARIANT.
_HERO_VARIANT_BY_COMPOSITION = {
    'immersive': 'fullscreen',
    'editorial': 'split',
    'grid': 'split',
    'centered': 'centered',
}
_SECONDARY_HERO_VARIANT = {
    'immersive': 'centered',
    'editorial': 'split',
    'grid': 'centered',
    'centered': 'centered',
}

# Curated zero-dependency effect components (Phase 47.40 audit §C).
# TiltedCard and GradientText are EXCLUDED: their current registry
# sources import 'motion/react' (framer-motion v12), which is outside
# the generated runtime's dependency contract — selecting them would
# fabricate an arbitrary npm dependency. The policy can only select
# components that are self-contained in the existing runtime.
_ALLOWED_EFFECT_COMPONENTS = ('SpotlightCard', 'StarBorder')

# 3D policy: the site-level renderer may only be recommended when the
# visual direction is immersive AND the brief's identity lines carry
# explicit 3D-supporting signals. Never a literal-word-only gate over
# the whole raw brief, and never automatic.
_3D_SUPPORT_SIGNALS = ('3d', 'webgl', 'spatial', 'configurator',
                       'virtual showroom', 'interactive product')


def _first_signal(text: str, table, default: str) -> str:
    for value, keywords in table:
        for kw in keywords:
            if kw and re_search_word(text, kw):
                return value
    return default


def derive_visual_direction(requirements, design_lang: str,
                            palette_family: str) -> Dict[str, Any]:
    """Deterministic, brief-derived visual direction (Phase 47.40).

    Pure function of the requirement signals + fixed tables — identical
    inputs always produce an identical direction (reproducibility), and
    every axis value comes from a bounded enumeration validated here.
    Never raises; unknown/absent signals fall back to domain defaults
    (and ultimately to the previous universal behavior).
    """
    req = requirements
    branding = getattr(req, 'branding', None) or {}
    domain = str(getattr(req, 'domain', '') or '').strip()
    # Bounded identity signal text: labeled brief lines only — page
    # lists, routes and audience phrasing are NOT visual signals.
    signal_text = ' '.join(filter(None, [
        str(getattr(req, 'business_category', '') or ''),
        str(branding.get('business_category', '') or ''),
        str(branding.get('positioning', '') or ''),
        str(branding.get('differentiators', '') or ''),
        str(branding.get('visual', '') or ''),
    ]))
    text = ' ' + signal_text.lower() + ' '

    typography_direction, font_heading, font_body = _select_typography(
        palette_family, signal_text)

    density = _first_signal(text, _DENSITY_SIGNALS,
                            _DENSITY_DOMAIN_DEFAULTS.get(domain, 'standard'))
    corner_style = _first_signal(
        text, _CORNER_SIGNALS, _CORNER_DOMAIN_DEFAULTS.get(domain, 'soft'))
    depth_level = _first_signal(
        text, _DEPTH_SIGNALS, _DEPTH_DOMAIN_DEFAULTS.get(domain, 'subtle'))
    motion_level = _first_signal(text, _MOTION_SIGNALS, 'subtle')
    composition_style = _first_signal(
        text, _COMPOSITION_SIGNALS,
        _COMPOSITION_DOMAIN_DEFAULTS.get(domain, 'centered'))

    # Enumerated-axis validation (defense in depth: policy output can
    # only carry vocabulary values).
    density = density if density in _DENSITY_SCALES else 'standard'
    corner_style = corner_style if corner_style in _CORNER_SCALES else 'soft'
    depth_level = depth_level if depth_level in _DEPTH_SCALES else 'subtle'
    motion_level = (motion_level if motion_level in _MOTION_SCALES
                    else 'subtle')
    composition_style = (composition_style
                         if composition_style in _HERO_VARIANT_BY_COMPOSITION
                         else 'centered')

    hero_variant = _HERO_VARIANT_BY_COMPOSITION[composition_style]
    secondary_hero_variant = _SECONDARY_HERO_VARIANT[composition_style]

    # Effects budget (bounded): hover depth on cards when the direction
    # justifies it; the animated CTA border only for expressive motion.
    effects = []
    if (depth_level in ('subtle', 'elevated')
            and motion_level in ('subtle', 'standard', 'expressive')):
        effects.append('SpotlightCard')
    if motion_level == 'expressive':
        effects.append('StarBorder')
    effects = [e for e in effects if e in _ALLOWED_EFFECT_COMPONENTS][:2]

    # Experience axis (Step 8/9 vocabulary): what the direction calls for.
    if composition_style == 'immersive':
        experience = 'immersive'
    elif effects:
        experience = 'dimensional'
    elif depth_level == 'elevated':
        experience = 'layered'
    else:
        experience = 'flat'

    # 3D policy: site-level renderer recommendation — only immersive
    # directions with explicit supporting signals in the identity lines.
    renderer_recommendation = 'none'
    if experience == 'immersive':
        for kw in _3D_SUPPORT_SIGNALS:
            if kw and re_search_word(text, kw):
                renderer_recommendation = 'webgl'
                break

    return {
        'design_language': (design_lang or 'minimal'),
        'palette_family': palette_family,
        'typography_direction': typography_direction,
        'typography_pair': [font_heading, font_body],
        'density': density,
        'corner_style': corner_style,
        'depth_level': depth_level,
        'motion_level': motion_level,
        'composition_style': composition_style,
        'hero_variant': hero_variant,
        'secondary_hero_variant': secondary_hero_variant,
        'effects': effects,
        'experience': experience,
        'renderer_recommendation': renderer_recommendation,
    }


def visual_fingerprint(visual_direction: Dict[str, Any],
                       page_pattern_id: str) -> Dict[str, Any]:
    """Phase 47.40: bounded visual-diversity fingerprint for QA and
    reproducibility — a plain-value projection of the visual direction
    plus the composition pattern, riding the EXISTING generation
    metadata transport (no separate registry, no arbitrary score)."""
    effects = list(visual_direction.get('effects') or [])
    interaction = ('animated' if 'StarBorder' in effects
                   else 'hover' if 'SpotlightCard' in effects else 'none')
    return {
        'palette_family': visual_direction.get('palette_family'),
        'typography_direction': visual_direction.get('typography_direction'),
        'composition_style': visual_direction.get('composition_style'),
        'density': visual_direction.get('density'),
        'corner_style': visual_direction.get('corner_style'),
        'depth_level': visual_direction.get('depth_level'),
        'motion_level': visual_direction.get('motion_level'),
        'interaction_level': interaction,
        'hero_variant': visual_direction.get('hero_variant'),
        'effects': effects,
        'pattern': page_pattern_id,
    }


def _derive_palette(family_name: str) -> Dict[str, str]:
    """Copy the family palette and enforce AA contrast on the text-bearing
    pairs (foreground/background, primary_foreground/primary,
    secondary/background, muted/background). Decorative pairs (border,
    card, accent) are passed through."""
    fam = _PALETTE_FAMILIES[family_name]
    pal = dict(fam)
    pal['foreground'] = _adjust_until_contrast(pal['foreground'], pal['background'])
    pal['primary_foreground'] = _adjust_until_contrast(pal['primary_foreground'], pal['primary'])
    pal['secondary'] = _adjust_until_contrast(pal['secondary'], pal['background'])
    pal['muted'] = _adjust_until_contrast(pal['muted'], pal['background'])
    return pal


class ThemeEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ThemeEngine (Delegating to DesignIntelligenceEngine)...")
        # In Phase B, the modular blueprint is created upstream by PlanningEngine 
        # and stored in generation_metadata.
        modular_blueprint_dict = artifact.generation_metadata.get("modular_blueprint", {})
        
        try:
            # We construct a mock object or extract dict fields to satisfy Theme mapping
            # (Until ThemeEngine itself is fully migrated)
            design = modular_blueprint_dict.get("design", {})
            design_lang = design.get("language", "minimal")
            
            metadata = {}
            # Phase 47.23 (ADR-0075): deterministic, brief-derived semantic
            # palette + webfont selection (replaces the universal
            # Tailwind-blue constants). Contrast-safe by construction.
            # Phase 47.40: routing uses the BOUNDED identity signals
            # (domain + business_category) — never the joined raw brief.
            req = artifact.requirements
            business_category = str(getattr(req, 'business_category', '') or '')
            branding_category = str((req.branding or {}).get('business_category', '') or '')
            family = _select_family(
                design_lang,
                ' '.join(filter(None, [business_category, branding_category])),
                domain=str(getattr(req, 'domain', '') or ''),
                business_category=business_category or branding_category,
            )
            palette = _derive_palette(family)

            # Phase 47.40: the deterministic visual-direction policy —
            # ThemeEngine remains the single design owner (ADR-0075) and
            # now also owns density / corner / depth / motion /
            # composition / hero-variant / effects decisions.
            visual_direction = derive_visual_direction(req, design_lang, family)
            font_heading, font_body = visual_direction['typography_pair']
            if font_heading not in _WEBFONT_FAMILIES:
                font_heading = 'Inter'
            if font_body not in _WEBFONT_FAMILIES:
                font_body = 'Inter'
            metadata['palette_family'] = family
            metadata['font_heading'] = font_heading
            metadata['font_body'] = font_body
            metadata['visual_direction'] = visual_direction
            _logger.info(
                "ThemeEngine derived palette family=%s primary=%s fonts=%s/%s "
                "direction=%s",
                family, palette['primary'], font_heading, font_body,
                {k: visual_direction[k] for k in (
                    'density', 'corner_style', 'depth_level', 'motion_level',
                    'composition_style', 'hero_variant', 'experience')})

            # Phase 47.40: token scales derived from the direction —
            # transported to the renderer through the existing token_set
            # contract (DesignOrchestrationEngine bridge). The Theme model
            # fields carry level-appropriate values (Theme.motion is no
            # longer a dead constant).
            density_scale = _DENSITY_SCALES[visual_direction['density']]
            corner_scale = _CORNER_SCALES[visual_direction['corner_style']]
            depth_scale = _DEPTH_SCALES[visual_direction['depth_level']]
            motion_scale = _MOTION_SCALES[visual_direction['motion_level']]
            
            model = Theme(
                design_tokens={
                    "version": "1.1", "prefix": "nx-",
                    # Phase 47.40: variant token scales (spacing / radius /
                    # shadow / motion) — additive, transported via token_set.
                    "spacing": dict(density_scale),
                    "radius": dict(corner_scale),
                    "shadow": dict(depth_scale),
                    "motion": dict(motion_scale),
                },
                typography_scale={
                    "h1": "2.25rem", "h2": "1.875rem", "h3": "1.5rem", "h4": "1.25rem",
                    "body": "1rem", "small": "0.875rem"
                },
                spacing_system=dict(density_scale),
                colors=palette,
                radius=corner_scale.get('radius-md', '8px'),
                shadows=depth_scale.get('shadow-md', 'none'),
                motion=dict(motion_scale),
                font_heading=font_heading,
                font_body=font_body,
            )

            # Phase 47.40: publish the visual direction + fingerprint on
            # the artifact's generation_metadata bus (the same transport
            # page_pattern uses) so the existing downstream owners —
            # CodeGenerationEngine builders, DesignOrchestrationEngine,
            # ValidationEngine evidence — consume one canonical decision.
            new_generation_metadata = dict(artifact.generation_metadata)
            new_generation_metadata['visual_direction'] = visual_direction
            page_pattern_id = str(
                (new_generation_metadata.get('page_pattern') or {}).get('id')
                or '')
            new_generation_metadata['visual_fingerprint'] = visual_fingerprint(
                visual_direction, page_pattern_id)

            # Phase 47.40 3D policy: when (and only when) the canonical
            # visual-direction policy recommends the immersive renderer,
            # the modular blueprint's rendering strategy is updated so the
            # existing DesignOrchestrationEngine → RenderingProviderRegistry
            # contract resolves R3F. Never a literal-word-only gate, never
            # automatic — and never for the five standard brief families.
            if visual_direction.get('renderer_recommendation') == 'webgl':
                updated_blueprint = dict(modular_blueprint_dict)
                rendering_bp = dict(updated_blueprint.get('rendering') or {})
                rendering_bp['strategy'] = 'webgl'
                updated_blueprint['rendering'] = rendering_bp
                new_generation_metadata['modular_blueprint'] = updated_blueprint

            evolved = artifact.evolve(
                theme=model, generation_metadata=new_generation_metadata)
            return EngineExecutionResult(success=True, artifact=evolved, metadata=metadata, error=None)
            
        except Exception as e:
            _logger.error(f"ThemeEngine delegation failed: {e}")
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=str(e))
