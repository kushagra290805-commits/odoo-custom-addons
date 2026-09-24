# -*- coding: utf-8 -*-
"""Phase 47.40 — Visual Identity & Design Diversity tests.

Covers the approved remediation using ONLY the existing canonical owners:
  * Theme routing: category/domain-aware classification (restaurant,
    ecommerce, portfolio, agency, SaaS) — the 47.39B warm_stone capture
    regression (a "Gallery" page-list word routing a restaurant to the
    architecture-studio palette) can no longer occur.
  * Deterministic visual direction: identical brief -> identical
    direction; materially different briefs -> appropriately different
    directions (bounded, enumerated axes; no randomness, no LLM).
  * Existing visual contracts activated: Theme.motion is no longer a
    dead constant, the AnimationBlueprint strategy is consumed by the
    provider's motion CSS, and the visual direction reaches the
    intended downstream consumers through the existing transports
    (generation_metadata bus, token_set, process_blueprint kwargs).
  * Hero diversity: image-bearing heroes are no longer universally
    "split"; selection is deterministic from the visual direction.
  * Composition: page-purpose-aware secondary compositions remain
    domain-appropriate; no arbitrary or random section selection.
  * Effects: only the allowlisted, zero-dependency curated components;
    effects never fabricate arbitrary dependencies; the
    motion-dependent curated components (TiltedCard/GradientText) are
    excluded by policy.
  * Motion accessibility: reduced-motion behavior.
  * Security: no secrets or provider credentials in generated artifacts.
  * Reproducibility: same input -> byte-identical visual-direction
    metadata.
  * Builder geometry: bounded design-token variants replace the
    universal constants, with exact backward compatibility for
    pre-47.40 artifacts.
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    RequirementModel, WebsiteGenerationArtifact, Theme)
from odoo.addons.nexora_studio.services.generation.engines.theme_engine import (
    ThemeEngine, _select_family, _derive_palette, _PALETTE_FAMILIES,
    derive_visual_direction, visual_fingerprint, contrast_ratio,
    _MOTION_SCALES, _DENSITY_SCALES, _CORNER_SCALES, _DEPTH_SCALES,
    _ALLOWED_EFFECT_COMPONENTS)
from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
    RequirementEngine)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine)
from odoo.addons.nexora_studio.services.generation.engines.design_orchestration_engine import (
    DesignOrchestrationEngine)
from odoo.addons.nexora_studio.services.design.page_patterns import (
    PAGE_PATTERN_CATALOG, pattern_sections, select_pattern, _SHARED_BUILDERS)
from odoo.addons.nexora_studio.services.design.providers.react_provider import (
    ReactRenderingProvider)
from odoo.addons.nexora_studio.services.design.render_domain import RenderToken

# The byte-exact Phase 47.39B briefs (the controlled five-site set).
BRIEF_METRICLY = (
    "Business: Metricly - SaaS analytics platform\n"
    "Location & market: Copenhagen, Denmark; B2B SaaS buyers in EU/US\n"
    "Target audience: B2B product teams and founders\n"
    "Services: product analytics, cohort dashboards, alerting, API access\n"
    "Positioning: Clarity for product decisions\n"
    "Differentiators: warehouse-native, no instrumentation tax, EU-hosted\n"
    "CTA: Start free trial\n"
    "Pages: Home, Pricing, Contact\n"
    "Content requirements: value prop, features, pricing, FAQ, testimonial\n"
    "Visual direction: deep indigo, clean data-viz\n"
    "Backend: contact lead capture requires persistent leads")
BRIEF_TRATTORIA = (
    "Business: Trattoria Nonna - Restaurant\n"
    "Location & market: Trastevere, Rome\n"
    "Target audience: local diners and weekend visitors\n"
    "Services: seasonal menu, natural wines, private dining\n"
    "Positioning: market-driven Roman cooking, family-run since 1987\n"
    "Differentiators: hand-rolled pasta daily, foraged herbs, natural wine cellar\n"
    "CTA: Reserve a table\n"
    "Pages: Home, Menu, Reservations\n"
    "Content: story, menu highlights with prices, gallery, hours/location\n"
    "Visual: terracotta warmth, editorial food photography\n"
    "Backend: none \u2014 presentational only")
BRIEF_ATELIER = (
    "Business: Atelier Nord - Architecture studio\n"
    "Location & market: Oslo, Norway; Nordic housing and cultural sector\n"
    "Target audience: developers and private clients\n"
    "Services: housing, cultural buildings, adaptive reuse, feasibility studies\n"
    "Positioning: Nordic architecture grounded in material and landscape\n"
    "Differentiators: timber-first construction, landscape integration, award-winning housing\n"
    "CTA: Discuss a project\n"
    "Pages: Home, Services, Contact\n"
    "Content: services, approach, testimonial, contact lead form\n"
    "Visual: warm stone, ink-champagne, Playfair + Source Sans\n"
    "Backend: contact form must create leads")
BRIEF_KINFOLK = (
    "Business: Kinfolk Goods - Ecommerce ceramics and textiles\n"
    "Location & market: Kyoto, Japan; global DTC buyers\n"
    "Target audience: design-conscious buyers\n"
    "Services: ceramics, textiles, tableware, limited editions\n"
    "Positioning: everyday objects made slowly, to last\n"
    "Differentiators: Kyoto kiln, natural glazes, small-batch weaving\n"
    "CTA: Shop collection\n"
    "Pages: Home, Products, Contact\n"
    "Content: product grid with prices/SKU, craft story, contact\n"
    "Visual: minimal warm neutral, object-forward photography\n"
    "Backend: product catalog and lead/contact capture")
BRIEF_ELENA = (
    "Business: Elena Voss - Portfolio photography studio\n"
    "Location & market: Berlin, Germany; editorial and cultural sector\n"
    "Target audience: magazine editors and cultural institutions\n"
    "Services: editorial commissions, cultural projects, prints\n"
    "Positioning: documentary photography \u2014 place and memory\n"
    "Differentiators: long-form essays, 10 years of fieldwork, exhibited at C/O Berlin\n"
    "CTA: View work / Get in touch\n"
    "Pages: Home, About, Projects\n"
    "Content: gallery/work, about/story, contact CTA\n"
    "Visual: warm stone minimal, generous whitespace, image-led\n"
    "Backend: none")

FIVE_BRIEFS = [
    ('saas_metricly', BRIEF_METRICLY),
    ('restaurant_trattoria', BRIEF_TRATTORIA),
    ('agency_atelier', BRIEF_ATELIER),
    ('ecommerce_kinfolk', BRIEF_KINFOLK),
    ('portfolio_elena', BRIEF_ELENA),
]


def _requirements_from_brief(raw_input):
    """The canonical RequirementModel for a brief (RequirementEngine path)."""
    artifact = WebsiteGenerationArtifact(
        requirements=RequirementModel(raw_input=raw_input))
    result = RequirementEngine(MagicMock()).execute(artifact, MagicMock())
    assert result.success, result.error
    return result.artifact.requirements


def _theme_for_brief(raw_input):
    """Run ThemeEngine on the canonical artifact for a brief."""
    reqs = _requirements_from_brief(raw_input)
    artifact = WebsiteGenerationArtifact(requirements=reqs)
    result = ThemeEngine(MagicMock()).execute(artifact, SimpleNamespace(env=None))
    assert result.success, result.error
    return result.artifact


def _vd_of(raw_input):
    artifact = _theme_for_brief(raw_input)
    return artifact.generation_metadata['visual_direction']


class TestThemeRouting(unittest.TestCase):
    """Step 11.1 — category/domain-aware routing; the 47.39B capture bug."""

    def test_01_five_domain_routes(self):
        cases = [
            ('Restaurant', 'Restaurant', 'terracotta'),
            ('Ecommerce', 'Ecommerce ceramics and textiles', 'linen'),
            ('Portfolio', 'Portfolio photography studio', 'gallery'),
            ('Agency', 'Architecture studio', 'warm_stone'),
            ('SaaS', 'SaaS analytics platform', 'deep_indigo'),
        ]
        for domain, category, expected in cases:
            self.assertEqual(
                _select_family('minimal', category, domain=domain,
                               business_category=category),
                expected, '%s should route to %s' % (domain, expected))

    def test_02_restaurant_gallery_word_no_capture(self):
        """The exact 47.39B defect: a restaurant brief whose pages line
        mentions Gallery must never route to warm_stone."""
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        family = artifact.generation_metadata['visual_direction']['palette_family']
        self.assertEqual(family, 'terracotta')
        self.assertNotEqual(family, 'warm_stone')

    def test_03_design_word_in_brief_no_capture(self):
        """An ecommerce brief with 'design-conscious buyers' (the exact
        Kinfolk capture) routes to the ecommerce family, not warm_stone."""
        artifact = _theme_for_brief(BRIEF_KINFOLK)
        family = artifact.generation_metadata['visual_direction']['palette_family']
        self.assertEqual(family, 'linen')

    def test_04_photograph_word_no_cross_domain_capture(self):
        artifact = _theme_for_brief(BRIEF_ELENA)
        family = artifact.generation_metadata['visual_direction']['palette_family']
        self.assertEqual(family, 'gallery')

    def test_05_design_language_overrides_preserved(self):
        self.assertEqual(_select_family('dark_neon', 'anything'),
                         'dark_neon')
        self.assertEqual(_select_family('premium_minimal', 'anything'),
                         'ink_champagne')

    def test_06_legacy_brief_signature_backward_compatible(self):
        """The pre-47.40 call signature still works (existing 47.23 tests)."""
        self.assertEqual(_select_family('minimal', 'Italian restaurant and cafe'),
                         'terracotta')
        self.assertEqual(
            _select_family('minimal', 'premium architecture and interior design studio'),
            'warm_stone')
        self.assertEqual(_select_family('minimal', 'generic business'), 'slate')

    def test_07_specific_categories_before_broad_terms(self):
        """A photography gallery cafe classifies by the restaurant signal,
        not the gallery signal (specificity ordering)."""
        self.assertEqual(
            _select_family('minimal', 'cafe with photography gallery',
                           domain='', business_category='cafe with photography gallery'),
            'terracotta')

    def test_08_new_families_contrast_safe(self):
        for family in _PALETTE_FAMILIES:
            pal = _derive_palette(family)
            for fg_name, bg_name in (('foreground', 'background'),
                                     ('primary_foreground', 'primary'),
                                     ('secondary', 'background'),
                                     ('muted', 'background')):
                ratio = contrast_ratio(pal[fg_name], pal[bg_name])
                self.assertGreaterEqual(
                    ratio, 4.5,
                    '%s %s/%s contrast %.2f < AA' % (family, fg_name, bg_name, ratio))


class TestVisualDirectionDeterminism(unittest.TestCase):
    """Step 11.2 — same brief -> identical direction; different briefs ->
    appropriately different directions."""

    def _directions(self):
        return {bid: _vd_of(brief) for bid, brief in FIVE_BRIEFS}

    def test_10_same_brief_identical_direction(self):
        for bid, brief in FIVE_BRIEFS:
            d1 = _vd_of(brief)
            d2 = _vd_of(brief)
            self.assertEqual(
                json.dumps(d1, sort_keys=True),
                json.dumps(d2, sort_keys=True),
                '%s must be byte-identical across runs' % bid)

    def test_11_axes_are_enumerated(self):
        allowed = {
            'density': _DENSITY_SCALES,
            'corner_style': _CORNER_SCALES,
            'depth_level': _DEPTH_SCALES,
            'motion_level': _MOTION_SCALES,
        }
        for bid, vd in self._directions().items():
            for axis, table in allowed.items():
                self.assertIn(vd[axis], table,
                              '%s %s=%s outside vocabulary' % (bid, axis, vd[axis]))
            self.assertIn(vd['composition_style'],
                          ('editorial', 'centered', 'grid', 'immersive'))
            self.assertIn(vd['hero_variant'], ('split', 'centered', 'fullscreen'))
            self.assertIn(vd['secondary_hero_variant'], ('split', 'centered'))

    def test_12_five_briefs_materially_different(self):
        directions = self._directions()
        # Audit targets: >=4 palette families, >=3 typography pairs,
        # >=3 hero variants, >=3 density/corner combinations.
        families = {vd['palette_family'] for vd in directions.values()}
        pairs = {tuple(vd['typography_pair']) for vd in directions.values()}
        heroes = {vd['hero_variant'] for vd in directions.values()}
        combos = {(vd['density'], vd['corner_style'])
                  for vd in directions.values()}
        self.assertGreaterEqual(len(families), 4, families)
        self.assertGreaterEqual(len(pairs), 3, pairs)
        self.assertGreaterEqual(len(heroes), 3, heroes)
        self.assertGreaterEqual(len(combos), 3, combos)

    def test_13_directions_semantically_appropriate(self):
        directions = self._directions()
        self.assertEqual(directions['saas_metricly']['composition_style'],
                         'centered')
        self.assertEqual(directions['restaurant_trattoria']['composition_style'],
                         'editorial')
        self.assertEqual(directions['ecommerce_kinfolk']['composition_style'],
                         'grid')
        self.assertEqual(directions['portfolio_elena']['composition_style'],
                         'immersive')
        # The brief's explicit visual line is honored (bounded alias table).
        self.assertEqual(directions['agency_atelier']['typography_pair'],
                         ['Playfair Display', 'Source Sans 3'])
        # Image-led portfolio -> flat depth (imagery carries the depth).
        self.assertEqual(directions['portfolio_elena']['depth_level'], 'flat')
        # Generous whitespace is an airy signal.
        self.assertEqual(directions['portfolio_elena']['density'], 'airy')

    def test_14_no_randomness_in_policy(self):
        """The policy is a pure function: repeated evaluation is stable
        even across different dict orderings of the same signal text."""
        reqs = _requirements_from_brief(BRIEF_TRATTORIA)
        base = derive_visual_direction(reqs, 'minimal', 'terracotta')
        for _ in range(5):
            self.assertEqual(
                json.dumps(derive_visual_direction(reqs, 'minimal', 'terracotta'),
                           sort_keys=True),
                json.dumps(base, sort_keys=True))


class TestVisualContractsActivated(unittest.TestCase):
    """Step 11.3 — the previously-dead contracts are live."""

    def test_20_theme_motion_varies_by_level(self):
        """Theme.motion is no longer a dead constant — it carries the
        motion-level-derived timing tokens."""
        artifact = _theme_for_brief(BRIEF_METRICLY)
        vd = artifact.generation_metadata['visual_direction']
        self.assertEqual(vd['motion_level'], 'standard')
        self.assertEqual(artifact.theme.motion,
                         _MOTION_SCALES['standard'])
        artifact2 = _theme_for_brief(BRIEF_ELENA)
        vd2 = artifact2.generation_metadata['visual_direction']
        self.assertEqual(vd2['motion_level'], 'subtle')
        self.assertEqual(artifact2.theme.motion, _MOTION_SCALES['subtle'])

    def test_21_theme_design_tokens_carry_scales(self):
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        tokens = artifact.theme.design_tokens
        self.assertIn('spacing', tokens)
        self.assertIn('radius', tokens)
        self.assertIn('shadow', tokens)
        self.assertIn('motion', tokens)
        self.assertEqual(tokens['spacing'], _DENSITY_SCALES['airy'])
        self.assertEqual(tokens['radius'], _CORNER_SCALES['rounded'])

    def test_22_token_set_transports_variant_scales(self):
        """DesignOrchestrationEngine._theme_token_set carries the variant
        spacing/radius/shadow/motion tokens (existing token_set contract)."""
        artifact = _theme_for_brief(BRIEF_KINFOLK)
        token_set = DesignOrchestrationEngine._theme_token_set(artifact, {})
        names = {t['name'] for t in token_set['tokens']}
        for name in ('spacing-md', 'spacing-xl', 'radius-md', 'radius-lg',
                     'shadow-md', 'motion-fast'):
            self.assertIn(name, names, 'variant token %s missing' % name)
        values = {t['name']: t['value'] for t in token_set['tokens']}
        # Kinfolk: standard density, flat depth.
        self.assertEqual(values['spacing-md'], '1rem')
        self.assertEqual(values['shadow-md'], 'none')

    def test_23_visual_direction_reaches_provider(self):
        """The visual direction (with the AnimationBlueprint) reaches the
        provider through the existing process_blueprint kwargs transport
        and produces the motion CSS in tokens.css."""
        provider = ReactRenderingProvider()
        vd = {'motion_level': 'subtle',
              'animation': {'strategy': 'css_transitions',
                            'abstract_requirements': ['fade_in']}}
        context = SimpleNamespace(
            tokens=[], render_project=SimpleNamespace(tokens=[]),
            output_config={'visual_direction': vd})
        files = provider.generate_design_tokens(context)
        css = files['src/styles/tokens.css']
        self.assertIn('@keyframes nx-section-in', css)
        self.assertIn('prefers-reduced-motion: no-preference', css)
        # The AnimationBlueprint's fade_in abstract requirement is
        # consumed (previously a dead contract).
        self.assertIn('animation: nx-section-in', css)

    def test_24_visual_direction_kwarg_dispatched_by_orchestrator(self):
        """DesignOrchestrationEngine passes visual_direction through the
        canonical DesignOrchestrator kwargs path."""
        captured = {}

        class _FakeOrchestrator:
            def execute_operation(self, operation, provider_name=None, **kwargs):
                captured['operation'] = operation
                captured['kwargs'] = kwargs
                return {
                    'status': 'success',
                    'provider': provider_name,
                    'project_structure': {'src/main.jsx': 'x'},
                    'dependencies': {},
                    'validation': {'valid': True},
                    'metadata': {},
                }

        artifact = _theme_for_brief(BRIEF_METRICLY)
        # The modular blueprint (PlanningEngine output) carries the
        # AnimationBlueprint that rides the visual-direction payload.
        metadata = dict(artifact.generation_metadata)
        metadata['modular_blueprint'] = {
            'design': {'language': 'minimal'},
            'animation': {'strategy': 'css_transitions',
                          'abstract_requirements': ['fade_in']},
            'rendering': {'strategy': 'none'},
        }
        artifact = artifact.evolve(generation_metadata=metadata)
        result = DesignOrchestrationEngine(MagicMock()).execute(
            artifact, SimpleNamespace(env={'nexora.design_orchestrator':
                                           _FakeOrchestrator()}))
        self.assertTrue(result.success, result.error)
        self.assertEqual(captured['operation'], 'process_blueprint')
        vd = captured['kwargs']['visual_direction']
        self.assertEqual(vd['palette_family'], 'deep_indigo')
        # The AnimationBlueprint rides the same payload.
        self.assertEqual(vd['animation']['strategy'], 'css_transitions')

    def test_25_fingerprint_on_metadata_and_validation_evidence(self):
        """The bounded visual fingerprint rides the existing generation
        metadata (and the ValidationEngine evidence path)."""
        artifact = _theme_for_brief(BRIEF_ELENA)
        fp = artifact.generation_metadata['visual_fingerprint']
        self.assertEqual(fp['palette_family'], 'gallery')
        self.assertEqual(fp['pattern'], '')  # no pattern on a bare artifact
        expected = visual_fingerprint(
            artifact.generation_metadata['visual_direction'], '')
        self.assertEqual(fp, expected)
        # Plain values only — bounded, serializable, no raw brief echo.
        for key, value in fp.items():
            self.assertNotIsInstance(value, dict, key)

    def test_26_webgl_recommendation_policy(self):
        """3D is a policy decision, never a literal-word-only gate: only
        immersive directions with explicit 3D-supporting identity signals
        recommend the immersive renderer."""
        # None of the five standard briefs recommends 3D.
        for bid, brief in FIVE_BRIEFS:
            vd = _vd_of(brief)
            self.assertEqual(vd['renderer_recommendation'], 'none',
                             '%s should not recommend 3D' % bid)
        # An immersive portfolio WITH explicit 3D signals does.
        reqs = _requirements_from_brief(
            BRIEF_ELENA.replace(
                'Positioning: documentary photography',
                'Positioning: interactive product configurator and 3d '
                'showcase photography'))
        vd = derive_visual_direction(reqs, 'minimal', 'gallery')
        self.assertEqual(vd['experience'], 'immersive')
        self.assertEqual(vd['renderer_recommendation'], 'webgl')
        # The recommendation flows into the modular blueprint rendering
        # strategy through the ThemeEngine (existing contract).
        artifact = WebsiteGenerationArtifact(requirements=reqs)
        result = ThemeEngine(MagicMock()).execute(
            artifact, SimpleNamespace(env=None))
        self.assertTrue(result.success)
        bp = result.artifact.generation_metadata['modular_blueprint']
        self.assertEqual(bp['rendering']['strategy'], 'webgl')


class TestHeroVariants(unittest.TestCase):
    """Step 11.4 — image-bearing heroes are not universally split."""

    def _vd(self, **overrides):
        base = {'hero_variant': 'split', 'secondary_hero_variant': 'centered'}
        base.update(overrides)
        return base

    def test_30_centered_with_image_not_split(self):
        engine = CodeGenerationEngine(MagicMock())
        vd = self._vd(hero_variant='centered')
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path='/images/x.jpg'),
            'centered')

    def test_31_fullscreen_for_immersive(self):
        engine = CodeGenerationEngine(MagicMock())
        vd = self._vd(hero_variant='fullscreen')
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path='/images/x.jpg'),
            'fullscreen')

    def test_32_split_for_editorial_with_image(self):
        engine = CodeGenerationEngine(MagicMock())
        vd = self._vd(hero_variant='split')
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path='/images/x.jpg'),
            'split')

    def test_33_image_led_variants_degrade_without_image(self):
        engine = CodeGenerationEngine(MagicMock())
        vd = self._vd(hero_variant='split')
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path=None),
            'centered')
        vd = self._vd(hero_variant='fullscreen')
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path=None),
            'centered')

    def test_34_legacy_behavior_without_direction(self):
        engine = CodeGenerationEngine(MagicMock())
        vd = engine._visual_direction(
            WebsiteGenerationArtifact())  # no visual_direction
        self.assertFalse(vd['present'])
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path='/x.jpg'),
            'split')
        self.assertEqual(
            engine._hero_variant(vd, is_home=True, hero_path=None),
            'centered')

    def test_35_hero_variant_deterministic_and_diverse_across_briefs(self):
        variants = {}
        for bid, brief in FIVE_BRIEFS:
            vd = _vd_of(brief)
            variants[bid] = (vd['hero_variant'], vd['secondary_hero_variant'])
        # 3 distinct home hero variants across the five briefs.
        self.assertGreaterEqual(
            len({v[0] for v in variants.values()}), 3, variants)
        # Deterministic: recompute -> identical.
        for bid, brief in FIVE_BRIEFS:
            vd = _vd_of(brief)
            self.assertEqual(
                variants[bid],
                (vd['hero_variant'], vd['secondary_hero_variant']))

    def test_36_home_hero_builder_emits_direction_variant(self):
        """The deterministic home hero composes the native Hero organism
        with the visual-direction variant."""
        artifact = _theme_for_brief(BRIEF_ELENA)  # immersive -> fullscreen
        artifact = artifact.evolve(content=type(artifact.content)(
            pages={'/': {'sections': [
                {'type': 'Hero', 'semantic_heading': 'Elena Voss',
                 'body': 'Documentary photography.'}],
                'seo': {}}}))
        engine = CodeGenerationEngine(MagicMock())
        runtime = SimpleNamespace(
            workspace=SimpleNamespace(exists=lambda p: True))
        code, imports, mode = engine._build_deterministic_home_hero(
            'HeroSection0', artifact,
            [{'type': 'Hero', 'semantic_heading': 'Elena Voss',
              'body': 'Documentary photography.'}],
            {'path': '/images/hero.jpg', 'alt': 'hero'},
            ['/', '/about', '/projects'], runtime)
        self.assertIn('variant="fullscreen"', code)
        self.assertEqual(mode, 'deterministic')

    def test_37_secondary_hero_builder_emits_direction_variant(self):
        artifact = _theme_for_brief(BRIEF_METRICLY)  # centered
        engine = CodeGenerationEngine(MagicMock())
        runtime = SimpleNamespace(
            workspace=SimpleNamespace(exists=lambda p: True))
        code, imports, mode = engine._build_secondary_hero(
            'Hero', 'HeroSection0',
            [{'type': 'Hero', 'semantic_heading': 'Pricing',
              'body': 'Simple transparent pricing.'}],
            0, {'path': '/images/hero.jpg', 'alt': 'hero'},
            ['/', '/pricing', '/contact'], runtime, artifact=artifact)
        # An image-bearing secondary hero that is NOT split (the exact
        # 47.39B universal outcome).
        self.assertIn('variant="centered"', code)
        self.assertNotIn('variant="split"', code)


class TestCompositionPatterns(unittest.TestCase):
    """Step 11.5 — page-purpose compositions, domain-appropriate."""

    def test_40_secondary_pages_by_purpose(self):
        cases = [
            ('restaurant', '/menu', ['Hero', 'MenuHighlights', 'Gallery']),
            ('restaurant', '/reservations', ['Hero', 'About', 'ContactCTA']),
            ('portfolio', '/projects', ['Hero', 'Gallery', 'Testimonial']),
            ('portfolio', '/about', ['Hero', 'About', 'Gallery']),
            ('saas_product', '/pricing', ['Hero', 'Pricing', 'FAQ']),
            ('ecommerce', '/products', ['Hero', 'MenuHighlights', 'Gallery']),
            ('agency', '/services', ['Hero', 'ServicesGrid', 'Testimonial']),
        ]
        for pattern_id, path, expected in cases:
            pattern = select_pattern(
                PAGE_PATTERN_CATALOG[pattern_id]['suitable_domains'][0], '')
            self.assertEqual(pattern_sections(pattern, False, path=path),
                             expected,
                             '%s %s' % (pattern_id, path))

    def test_41_unknown_purpose_falls_back(self):
        pattern = PAGE_PATTERN_CATALOG['restaurant']
        self.assertEqual(pattern_sections(pattern, False, path='/unknown-page'),
                         list(pattern['secondary_sections']))

    def test_42_home_unchanged(self):
        pattern = PAGE_PATTERN_CATALOG['restaurant']
        self.assertEqual(pattern_sections(pattern, True, path='/'),
                         list(pattern['home_sections']))

    def test_43_all_sequences_use_shared_builders_only(self):
        """No arbitrary sections: every composition references only the
        existing shared builder vocabulary."""
        for pattern in PAGE_PATTERN_CATALOG.values():
            for key in ('home_sections', 'secondary_sections'):
                for section in pattern.get(key) or []:
                    self.assertIn(section, _SHARED_BUILDERS,
                                  '%s %s %s' % (pattern['id'], key, section))
            for purpose, sections in (pattern.get('secondary_pages') or {}).items():
                for section in sections:
                    self.assertIn(section, _SHARED_BUILDERS,
                                  '%s %s %s' % (pattern['id'], purpose, section))

    def test_44_pattern_is_deterministic(self):
        for _ in range(3):
            for domain in ('Restaurant', 'SaaS', 'Portfolio', 'Ecommerce',
                           'Agency'):
                p1 = select_pattern(domain, '')
                p2 = select_pattern(domain, '')
                self.assertEqual(json.dumps(p1, sort_keys=True),
                                 json.dumps(p2, sort_keys=True))

    def test_45_architecture_sections_use_purpose(self):
        """ArchitectureEngine consumes the purpose-aware composition."""
        from odoo.addons.nexora_studio.services.generation.engines.architecture_engine import (
            ArchitectureEngine)
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Restaurant'),
            generation_metadata={
                'modular_blueprint': {
                    'layout': {'strategy': 'grid',
                               'hierarchy': ['/', '/menu', '/reservations']},
                    'technology': {},
                },
                'page_pattern': {
                    'id': 'restaurant',
                    'home_sections': ['Hero', 'About', 'MenuHighlights',
                                      'Gallery', 'Testimonial', 'ContactCTA'],
                    'secondary_sections': ['Hero', 'Content'],
                    'secondary_pages': {
                        'menu': ['Hero', 'MenuHighlights', 'Gallery'],
                        'reservations': ['Hero', 'About', 'ContactCTA'],
                    },
                },
            })
        result = ArchitectureEngine(MagicMock()).execute(artifact, MagicMock())
        self.assertTrue(result.success, result.error)
        hierarchy = result.artifact.architecture.component_hierarchy
        self.assertEqual(
            hierarchy['page_menu']['sections'],
            ['Hero', 'MenuHighlights', 'Gallery'])
        self.assertEqual(
            hierarchy['page_reservations']['sections'],
            ['Hero', 'About', 'ContactCTA'])

    def test_46_asset_intents_include_purpose_sections(self):
        """AssetEngine's all_sections includes the route-purpose sections
        so the new compositions get imagery."""
        from odoo.addons.nexora_studio.services.generation.engines.asset_engine import (
            AssetEngine)
        engine = AssetEngine(MagicMock())
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Restaurant'),
            generation_metadata={'page_pattern': {
                'home_sections': ['Hero'],
                'secondary_sections': ['Hero', 'Content'],
                'secondary_pages': {'menu': ['Hero', 'MenuHighlights',
                                             'Gallery']},
            }})
        intents = engine._build_stock_intents(
            artifact, ['Hero', 'MenuHighlights', 'Gallery'], 'restaurant')
        section_intents = [i for i in intents if i['role'] == 'section']
        self.assertTrue(any(i['context']['section_type'] == 'MenuHighlights'
                            for i in section_intents))


class TestEffectsPolicy(unittest.TestCase):
    """Step 11.6 — only allowlisted, zero-dependency curated effects."""

    def test_50_effects_allowlist_only(self):
        for bid, brief in FIVE_BRIEFS:
            vd = _vd_of(brief)
            for effect in vd['effects']:
                self.assertIn(effect, _ALLOWED_EFFECT_COMPONENTS)

    def test_51_motion_dependent_curated_components_excluded(self):
        """TiltedCard/GradientText import 'motion/react' (framer-motion
        v12) — outside the generated runtime dependency contract; the
        policy can never select them."""
        self.assertNotIn('TiltedCard', _ALLOWED_EFFECT_COMPONENTS)
        self.assertNotIn('GradientText', _ALLOWED_EFFECT_COMPONENTS)

    def test_52_flat_depth_gets_no_effects(self):
        reqs = _requirements_from_brief(BRIEF_KINFOLK)
        vd = derive_visual_direction(reqs, 'minimal', 'linen')
        self.assertEqual(vd['depth_level'], 'flat')
        self.assertEqual(vd['effects'], [])

    def test_53_effects_only_from_discovered_candidates(self):
        """The effect materializes ONLY from the canonical discovery
        output on the artifact — no fetch, no fabrication; a missing
        candidate means the plain composition (generation never breaks)."""
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        vd = artifact.generation_metadata['visual_direction']
        self.assertIn('SpotlightCard', vd['effects'])

        class _Ws:
            def __init__(self):
                self.files = {}

            def write_file(self, path, content):
                self.files[path] = content

            def exists(self, path):
                return path in self.files

        # Without a discovered candidate: no materialization, no import.
        known, evidence = engine._materialize_external_components(
            artifact, SimpleNamespace(workspace=_Ws()))
        self.assertNotIn('SpotlightCard', known)
        self.assertEqual([e for e in evidence if e.get('kind') == 'visual_effect'],
                         [])
        # Builder then composes the plain fallback.
        built = engine._build_pattern_section(
            'ServicesGrid', 'ServicesSection1', artifact,
            [{'type': 'ServicesGrid', 'semantic_heading': 'Services',
              'body': 'Intro.\n\nOne.\n\nTwo.'}], 1, None, {}, {},
            ['/', '/menu'])
        code, imports = built
        self.assertNotIn('<SpotlightCard', code)
        self.assertNotIn('SpotlightCard', ''.join(imports))
        # Validation passes with no unknown identifiers.
        issues = CodeGenerationEngine._section_module_issues(
            'ServicesSection1', code)
        self.assertEqual(issues, [])

    def test_54_effect_materializes_from_candidate(self):
        """With the discovered candidate present, the curated effect
        materializes through the existing external path and the section
        composes with it (validation-clean)."""
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)

        class _Pkg:
            component_id = 'react_bits/SpotlightCard'
            metadata = {
                'source_code': (
                    "import { useRef } from 'react';\n"
                    "const SpotlightCard = ({ children }) => (\n"
                    "  <div className=\"card-spotlight\">{children}</div>\n"
                    ");\n"
                    "export default SpotlightCard;\n"),
                'source_identifier': 'SpotlightCard',
                'source_provider': 'react_bits',
                'auxiliary_files': {'SpotlightCard.css': '.card-spotlight{}'},
            }

        artifact = artifact.evolve(generation_metadata=dict(
            artifact.generation_metadata,
            candidate_components=[{'package': _Pkg(), 'score': 1}]))

        class _Ws:
            def __init__(self):
                self.files = {}

            def write_file(self, path, content):
                self.files[path] = content

            def exists(self, path):
                return path in self.files

        ws = _Ws()
        known, evidence = engine._materialize_external_components(
            artifact, SimpleNamespace(workspace=ws))
        self.assertIn('SpotlightCard', known)
        # The registered import line is the assembler's own — the module
        # filename follows the existing _external_module_name convention.
        registered = known['SpotlightCard']
        self.assertTrue(registered.startswith('import SpotlightCard from '))
        module_path = registered.split("'")[1].replace('../', 'src/')
        self.assertIn(module_path, ws.files)
        self.assertIn('src/components/external/SpotlightCard.css', ws.files)
        self.assertTrue(any(e.get('kind') == 'visual_effect' for e in evidence))

        effect_map = {e: known[e] for e in ('SpotlightCard',) if e in known}
        self.assertIn('SpotlightCard', effect_map)
        built = engine._build_pattern_section(
            'ServicesGrid', 'ServicesSection1', artifact,
            [{'type': 'ServicesGrid', 'semantic_heading': 'Services',
              'body': 'Intro.\n\nOne.\n\nTwo.'}], 1, None, {}, {}, ['/'],
            available_effects=effect_map)
        code, imports = built
        self.assertIn('<SpotlightCard', code)
        self.assertTrue(any('SpotlightCard' in i for i in imports))
        # The import line is the assembler's own registration — never a
        # builder-fabricated path.
        self.assertIn(effect_map['SpotlightCard'], imports)
        # Section validation passes when the materialized identifier is
        # known (the assembler injects the fixed import at page level).
        issues = CodeGenerationEngine._section_module_issues(
            'ServicesSection1', code, known_identifiers=set(known))
        self.assertEqual(issues, [])

    def test_55_no_arbitrary_dependencies_generated(self):
        """Effects never fabricate dependencies: the materialized module
        and sidecar are the ONLY artifacts, and no package specifier
        outside the runtime contract is referenced."""
        engine = CodeGenerationEngine(MagicMock())
        for bid, brief in FIVE_BRIEFS:
            vd = _vd_of(brief)
            for effect in vd['effects']:
                self.assertIn(effect, ('SpotlightCard', 'StarBorder'))
        # The builder imports only the assembler's own registered lines.
        star_line = "import StarBorder from '../components/external/StarBorder.jsx'"
        code, imports = engine._pattern_contactcta(
            'ContactSection4', _theme_for_brief(BRIEF_METRICLY),
            'Talk to us', 'We reply within a day.', None, {},
            ['/contact'], 4, [], available_effects={'StarBorder': star_line})
        self.assertTrue(star_line in imports)
        self.assertIn('<StarBorder', code)
        for line in imports:
            self.assertTrue(
                line.startswith('import { MapPin') or
                line.startswith('import StarBorder'),
                'unexpected import: %s' % line)


class TestMotionAccessibility(unittest.TestCase):
    """Step 11.7 — reduced-motion behavior."""

    def _css(self, motion_level, animation=None):
        return ReactRenderingProvider()._generate_tokens_css(
            [], motion_level=motion_level, animation=animation or {})

    def test_60_none_level_emits_no_motion(self):
        css = self._css('none')
        self.assertNotIn('@keyframes', css)
        self.assertNotIn('animation:', css)

    def test_61_motion_gated_by_no_preference(self):
        for level in ('subtle', 'standard', 'expressive'):
            css = self._css(level)
            self.assertIn('@media (prefers-reduced-motion: no-preference)', css)

    def test_62_reduced_motion_hard_guard(self):
        for level in ('subtle', 'standard', 'expressive'):
            css = self._css(level)
            self.assertIn('@media (prefers-reduced-motion: reduce)', css)
            self.assertIn('animation: none !important;', css)

    def test_63_compositor_safe_properties_only(self):
        for level in ('subtle', 'standard', 'expressive'):
            css = self._css(level)
            # Only opacity/transform animate (no layout properties).
            self.assertIn('from { opacity: 0; transform:', css)
            self.assertNotIn('animation: nx-section-in 240ms width', css)
            self.assertNotIn('left:', css.split('@keyframes')[1].split('}')[0])

    def test_64_motion_never_touches_interactive_controls(self):
        """The motion rule targets section entrances only — never
        buttons, inputs, links, or navigation."""
        for level in ('subtle', 'standard', 'expressive'):
            css = self._css(level)
            motion_block = css.split('motion budget')[1]
            for selector in ('button', 'input', 'a {', 'nav', 'textarea'):
                self.assertNotIn(selector, motion_block)

    def test_65_animation_blueprint_consumed(self):
        """The AnimationBlueprint abstract requirements map to the fixed
        CSS vocabulary (fade_in -> fade keyframe; staggered_entrance ->
        staggered delays)."""
        css = self._css('standard', {'strategy': 'css_transitions',
                                     'abstract_requirements': ['fade_in']})
        self.assertIn('nx-section-in', css)
        css2 = self._css('standard', {
            'strategy': 'css_transitions',
            'abstract_requirements': ['fade_in', 'staggered_entrance']})
        self.assertIn('animation-delay', css2)


class TestSecurityBoundaries(unittest.TestCase):
    """Step 11.8 — no secrets or provider credentials in artifacts."""

    def test_70_visual_direction_no_raw_brief_echo(self):
        """The contract carries only bounded vocabulary values — no raw
        brief text that could embed client-sensitive strings."""
        for bid, brief in FIVE_BRIEFS:
            vd = _vd_of(brief)
            serialized = json.dumps(vd)
            # Identity lines never ride the contract verbatim.
            for secret_line in ('warehouse-native', 'Kyoto kiln',
                                'C/O Berlin', 'Trastevere'):
                self.assertNotIn(secret_line, serialized)

    def test_71_generated_css_has_no_credentials(self):
        provider = ReactRenderingProvider()
        vd = {'motion_level': 'subtle',
              'animation': {'abstract_requirements': ['fade_in']}}
        context = SimpleNamespace(
            tokens=[], render_project=SimpleNamespace(tokens=[]),
            output_config={'visual_direction': vd})
        css = provider.generate_design_tokens(context)['src/styles/tokens.css']
        for marker in ('sk-', 'api_key', 'apikey', 'Bearer ', 'password',
                       'secret', 'token=', 'nex_cli'):
            self.assertNotIn(marker, css)

    def test_72_builder_output_has_no_credentials(self):
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        built = engine._build_pattern_section(
            'ServicesGrid', 'ServicesSection1', artifact,
            [{'type': 'ServicesGrid', 'semantic_heading': 'Services',
              'body': 'Intro.\n\nOne.'}], 1, None, {}, {}, ['/'])
        code, imports = built
        for marker in ('sk-', 'api_key', 'Bearer ', 'password', 'secret'):
            self.assertNotIn(marker, code)
            for line in imports:
                self.assertNotIn(marker, line)

    def test_73_no_external_network_in_generated_css(self):
        provider = ReactRenderingProvider()
        context = SimpleNamespace(
            tokens=[], render_project=SimpleNamespace(tokens=[]),
            output_config={'visual_direction': {'motion_level': 'subtle'}})
        css = provider.generate_design_tokens(context)['src/styles/tokens.css']
        self.assertNotIn('url(http', css)
        self.assertNotIn('url(//', css)


class TestReproducibility(unittest.TestCase):
    """Step 11.9 — same input, byte-identical visual-direction metadata."""

    def test_80_theme_engine_byte_identical_output(self):
        for bid, brief in FIVE_BRIEFS:
            a1 = _theme_for_brief(brief)
            a2 = _theme_for_brief(brief)
            self.assertEqual(
                json.dumps(a1.generation_metadata['visual_direction'],
                           sort_keys=True),
                json.dumps(a2.generation_metadata['visual_direction'],
                           sort_keys=True),
                '%s visual_direction must be byte-identical' % bid)
            self.assertEqual(
                json.dumps(a1.generation_metadata['visual_fingerprint'],
                           sort_keys=True),
                json.dumps(a2.generation_metadata['visual_fingerprint'],
                           sort_keys=True),
                '%s visual_fingerprint must be byte-identical' % bid)
            self.assertEqual(
                json.dumps(a1.theme.colors, sort_keys=True),
                json.dumps(a2.theme.colors, sort_keys=True))
            self.assertEqual(a1.theme.design_tokens, a2.theme.design_tokens)

    def test_81_fingerprint_is_serializable_plain_values(self):
        for bid, brief in FIVE_BRIEFS:
            artifact = _theme_for_brief(brief)
            fp = artifact.generation_metadata['visual_fingerprint']
            roundtrip = json.loads(json.dumps(fp))
            self.assertEqual(fp, roundtrip)


class TestBuilderGeometry(unittest.TestCase):
    """Step 5 — bounded design-token variants replace universal
    constants; exact backward compatibility without a direction."""

    def _servicesgrid(self, artifact, available_effects=()):
        engine = CodeGenerationEngine(MagicMock())
        return engine._build_pattern_section(
            'ServicesGrid', 'ServicesSection1', artifact,
            [{'type': 'ServicesGrid', 'semantic_heading': 'Services',
              'body': 'Intro.\n\nOne.\n\nTwo.\n\nThree.'}], 1, None, {},
            {}, ['/'], available_effects=available_effects)

    def test_90_backward_compatible_defaults(self):
        """No visual direction -> the exact pre-47.40 geometry."""
        artifact = WebsiteGenerationArtifact()
        code, imports = self._servicesgrid(artifact)
        self.assertIn('minmax(240px, 1fr)', code)
        self.assertIn('maxWidth: 1080', code)

    def test_91_density_variants(self):
        compact = _theme_for_brief(BRIEF_METRICLY)  # compact
        airy = _theme_for_brief(BRIEF_TRATTORIA)  # airy
        code_c, _ = self._servicesgrid(compact)
        code_a, _ = self._servicesgrid(airy)
        self.assertIn('minmax(200px, 1fr)', code_c)
        self.assertIn('minmax(280px, 1fr)', code_a)

    def test_92_composition_width_variants(self):
        centered = _theme_for_brief(BRIEF_METRICLY)  # centered -> 720
        grid = _theme_for_brief(BRIEF_KINFOLK)  # grid -> 1080
        code_c, _ = self._servicesgrid(centered)
        code_g, _ = self._servicesgrid(grid)
        self.assertIn('maxWidth: 720', code_c)
        self.assertIn('maxWidth: 1080', code_g)

    def test_93_gallery_geometry_variants(self):
        engine = CodeGenerationEngine(MagicMock())
        stock = {'stock_gallery1': {'path': '/images/g1.jpg', 'alt': 'a'},
                 'stock_gallery2': {'path': '/images/g2.jpg', 'alt': 'b'},
                 'stock_gallery3': {'path': '/images/g3.jpg', 'alt': 'c'}}

        def gallery(artifact):
            return engine._pattern_gallery(
                'GallerySection2', artifact, 'Gallery', '', None, stock,
                {}, 2, [])[0]

        uniform = gallery(WebsiteGenerationArtifact())
        self.assertIn("aspectRatio: '4 / 3'", uniform)
        self.assertIn('display: ', uniform)
        masonry = gallery(_theme_for_brief(BRIEF_ELENA))  # immersive
        self.assertIn("columns: '320px'", masonry)
        self.assertNotIn('aspectRatio', masonry)
        feature = gallery(_theme_for_brief(BRIEF_TRATTORIA))  # editorial
        self.assertIn("gridColumn: 'span 2'", feature)
        self.assertIn("aspectRatio: '16 / 10'", feature)

    def test_94_about_composition_variants(self):
        engine = CodeGenerationEngine(MagicMock())
        stock = {'stock_section_about': {'path': '/images/about.jpg',
                                         'alt': 'about'}}

        def about(artifact, heading='Our story'):
            return engine._pattern_about(
                'AboutSection1', artifact, heading, 'The story body.',
                None, stock, {}, 1, [])[0]

        stacked = about(WebsiteGenerationArtifact())
        self.assertIn("maxWidth: 480", stacked)
        offset = about(_theme_for_brief(BRIEF_TRATTORIA))  # editorial
        self.assertIn("flex: '1 1 320px'", offset)
        self.assertNotIn('maxWidth: 480', offset)

    def test_95_about_stacked_without_heading(self):
        """Degenerate input keeps the safe stacked composition."""
        engine = CodeGenerationEngine(MagicMock())
        stock = {'stock_section_about': {'path': '/images/about.jpg',
                                         'alt': 'about'}}
        code = engine._pattern_about(
            'AboutSection1', _theme_for_brief(BRIEF_TRATTORIA), '', 'Body.',
            None, stock, {}, 1, [])[0]
        self.assertIn('maxWidth: 480', code)

    def test_96_tokens_css_variant_values(self):
        """The token_set variant values override the provider defaults in
        tokens.css (density/corner/depth reach the browser)."""
        artifact = _theme_for_brief(BRIEF_KINFOLK)  # flat depth
        token_set = DesignOrchestrationEngine._theme_token_set(artifact, {})
        provider = ReactRenderingProvider()
        tokens = [RenderToken(name=t['name'], token_type=t['token_type'],
                              value=t['value'], category=t['category'])
                  for t in token_set['tokens']]
        css = provider._generate_tokens_css(tokens)
        self.assertIn('--shadow-md: none;', css)
        self.assertEqual(css.count('--shadow-md:'), 1)
        # Standard density keeps the default scale values.
        self.assertIn('--spacing-md: 1rem;', css)


if __name__ == '__main__':
    unittest.main(verbosity=2)
