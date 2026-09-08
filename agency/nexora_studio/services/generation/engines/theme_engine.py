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
}

# Domain-keyword -> family routing (word-boundary matches on category +
# domain text). Checked in order; first hit wins.
_FAMILY_ROUTES = [
    ('dark_neon', ('dark_neon',)),
    ('ink_champagne', ('premium_minimal',)),
    ('warm_stone', ('architecture', 'interior', 'studio', 'design',
                    'agency', 'consulting', 'law', 'legal', 'finance',
                    'real estate', 'realestate', 'luxury', 'atelier',
                    'gallery', 'photograph')),
    ('sage', ('health', 'wellness', 'spa', 'dental', 'clinic', 'medical',
              'yoga', 'therapy', 'pharmacy')),
    ('terracotta', ('restaurant', 'cafe', 'coffee', 'food', 'bakery',
                    'pizzeria', 'bistro', 'catering', 'hospitality', 'bar')),
    ('deep_indigo', ('saas', 'software', 'tech', 'technology', 'crypto',
                     'startup', 'data', 'platform', 'developer', 'ai',
                     'analytics', 'fintech', 'b2b')),
]

# Google Fonts families available for deterministic webfont loading.
_WEBFONT_FAMILIES = {
    'Inter', 'Playfair Display', 'Source Sans 3', 'Space Grotesk',
    'Lora', 'Cormorant Garamond', 'Work Sans', 'DM Sans',
}


def _select_family(design_lang: str, brief_text: str) -> str:
    lang = (design_lang or '').strip().lower()
    if lang == 'dark_neon':
        return 'dark_neon'
    if lang == 'premium_minimal':
        return 'ink_champagne'
    text = ' ' + (brief_text or '').lower() + ' '
    for family, keywords in _FAMILY_ROUTES:
        for kw in keywords:
            if kw and re_search_word(text, kw):
                return family
    return 'slate'


def re_search_word(text: str, kw: str) -> bool:
    return re.search(r'\b' + re.escape(kw.replace(' ', r'\s+')) + r'\b', text) is not None


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
            req = artifact.requirements
            brief_text = ' '.join(filter(None, [
                str(getattr(req, 'business_category', '') or ''),
                (req.branding or {}).get('business_category', ''),
                req.domain, req.raw_input or '',
            ]))
            family = _select_family(design_lang, brief_text)
            palette = _derive_palette(family)
            fam = _PALETTE_FAMILIES[family]
            font_heading = fam['font_heading'] if fam['font_heading'] in _WEBFONT_FAMILIES else 'Inter'
            font_body = fam['font_body'] if fam['font_body'] in _WEBFONT_FAMILIES else 'Inter'
            metadata['palette_family'] = family
            metadata['font_heading'] = font_heading
            metadata['font_body'] = font_body
            _logger.info(
                "ThemeEngine derived palette family=%s primary=%s fonts=%s/%s",
                family, palette['primary'], font_heading, font_body)
            
            model = Theme(
                design_tokens={"version": "1.0", "prefix": "nx-"},
                typography_scale={
                    "h1": "2.25rem", "h2": "1.875rem", "h3": "1.5rem", "h4": "1.25rem",
                    "body": "1rem", "small": "0.875rem"
                },
                spacing_system={
                    "0": "0", "1": "0.25rem", "2": "0.5rem", "4": "1rem", "8": "2rem", "16": "4rem"
                },
                colors=palette,
                radius="0.375rem",
                shadows="0 4px 6px -1px rgb(0 0 0 / 0.1)",
                motion={
                    "fast": "150ms ease-in-out",
                    "normal": "300ms ease-in-out",
                    "slow": "500ms ease-in-out"
                },
                font_heading=font_heading,
                font_body=font_body,
            )
            
            return EngineExecutionResult(success=True, artifact=artifact.evolve(theme=model), metadata=metadata, error=None)
            
        except Exception as e:
            _logger.error(f"ThemeEngine delegation failed: {e}")
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=str(e))
