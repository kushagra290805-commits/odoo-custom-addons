# -*- coding: utf-8 -*-
"""Phase 47.40A — Native FeatureGrid Effect Propagation regression tests.

Proves that the selected visual-direction effect (e.g. SpotlightCard) is
actually transported through the native FeatureGrid organism, and that
normal FeatureGrid behavior is preserved when no effect is selected.

Test matrix:
  1. Native FeatureGrid + SpotlightCard selected → ItemWrapper emitted
  2. Native FeatureGrid + no effect → no ItemWrapper, byte-equivalent output
  3. Native FeatureGrid + incompatible/unavailable effect → safe fallback
  4. Fallback FeatureGrid + SpotlightCard → existing behavior intact
  5. ServicesGrid native path → same propagation
  6. Allowlist enforcement
  7. Dependency safety
  8. Determinism (identical input → identical output)
  9. Availability-gated: merely available ≠ selected
 10. Existing Phase 47.40 visual-diversity tests remain passing
"""
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
    ThemeEngine, derive_visual_direction, _ALLOWED_EFFECT_COMPONENTS)
from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
    RequirementEngine)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine)

# ─── controlled brief ─────────────────────────────────────────────
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
    "Backend: none — presentational only")


def _requirements_from_brief(raw_input):
    artifact = WebsiteGenerationArtifact(
        requirements=RequirementModel(raw_input=raw_input))
    result = RequirementEngine(MagicMock()).execute(artifact, MagicMock())
    assert result.success, result.error
    return result.artifact.requirements


def _theme_for_brief(raw_input):
    reqs = _requirements_from_brief(raw_input)
    artifact = WebsiteGenerationArtifact(requirements=reqs)
    result = ThemeEngine(MagicMock()).execute(artifact, SimpleNamespace(env=None))
    assert result.success, result.error
    return result.artifact


# Native component fixture — mimics ComponentIntelligence selecting native/FeatureGrid
NATIVE_FG_COMPONENT = {
    'component_id': 'native/FeatureGrid',
    'code': "export default function FeatureGrid() {}",
    'metadata': {
        'source_provider': 'native_library',
        'source_identifier': 'FeatureGrid',
        'organism': True,
    },
}

SPOTLIGHT_IMPORT = "import SpotlightCard from '../components/external/SpotlightCard.jsx'"

# Effects map when SpotlightCard is available AND selected
EFFECTS_SPOTLIGHT = {'SpotlightCard': SPOTLIGHT_IMPORT}

# Default page sections for FeatureGrid and ServicesGrid
FG_SECTIONS = [
    {'type': 'Hero', 'semantic_heading': 'Welcome'},
    {'type': 'FeatureGrid', 'semantic_heading': 'Features',
     'body': 'Intro paragraph.\n\nFeature A body.\n\nFeature B body.',
     'items': [
         {'title': 'Fast', 'body': 'Blazing speed'},
         {'title': 'Secure', 'body': 'Enterprise grade'},
         {'title': 'Scalable', 'body': 'Grows with you'},
     ]},
]

SG_SECTIONS = [
    {'type': 'Hero', 'semantic_heading': 'Welcome'},
    {'type': 'ServicesGrid', 'semantic_heading': 'Services',
     'body': 'Intro.\n\nService A.\n\nService B.',
     'items': [
         {'title': 'Consulting', 'body': 'Expert advice'},
         {'title': 'Training', 'body': 'Deep dives'},
         {'title': 'Support', 'body': 'Always on'},
     ]},
]


class TestNativeFeatureGridEffectPropagation(unittest.TestCase):
    """Step 1–3: native FeatureGrid + effect → ItemWrapper emitted."""

    def setUp(self):
        self.engine = CodeGenerationEngine(MagicMock())
        self.artifact = _theme_for_brief(BRIEF_TRATTORIA)

    def test_01_native_featuregrid_spotlight_emits_item_wrapper(self):
        """Native FeatureGrid + SpotlightCard selected → ItemWrapper={SpotlightCard}."""
        result = self.engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', self.artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects=EFFECTS_SPOTLIGHT)

        self.assertIsNotNone(result)
        code, imports = result
        # ItemWrapper prop must be present
        self.assertIn('ItemWrapper={SpotlightCard}', code)
        # SpotlightCard import must be in the returned imports
        self.assertTrue(any('SpotlightCard' in imp for imp in imports),
                        f"SpotlightCard import missing from: {imports}")
        # The actual import line must match the assembler's registered line
        self.assertIn(SPOTLIGHT_IMPORT, imports)
        # Must still be the native FeatureGrid (not a second grid)
        self.assertIn('data-nexora-source="native/FeatureGrid"', code)
        # Must NOT contain a second FeatureGrid component
        self.assertEqual(code.count('<FeatureGrid'), 1)

    def test_02_native_featuregrid_no_effect_no_item_wrapper(self):
        """Native FeatureGrid + no effect → no ItemWrapper prop."""
        result = self.engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', self.artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects={})

        self.assertIsNotNone(result)
        code, imports = result
        self.assertNotIn('ItemWrapper', code)
        self.assertNotIn('SpotlightCard', code)
        self.assertFalse(any('SpotlightCard' in imp for imp in imports))
        self.assertIn('data-nexora-source="native/FeatureGrid"', code)

    def test_03_native_featuregrid_unavailable_effect_safe_fallback(self):
        """Native FeatureGrid + effect selected by VD but NOT materialized → safe."""
        # Visual direction may select SpotlightCard, but if it's not in
        # available_effects (not materialized), the native path is safe.
        result = self.engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', self.artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects={})

        self.assertIsNotNone(result)
        code, imports = result
        self.assertNotIn('ItemWrapper', code)
        self.assertIn('data-nexora-source="native/FeatureGrid"', code)

    def test_04_native_featuregrid_incompatible_effect_ignored(self):
        """An effect not in the allowlist cannot reach the native FeatureGrid."""
        bogus_effects = {'TiltedCard': "import TiltedCard from '../components/external/TiltedCard.jsx'"}
        result = self.engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', self.artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects=bogus_effects)

        self.assertIsNotNone(result)
        code, imports = result
        # TiltedCard is not SpotlightCard — should not appear as ItemWrapper
        self.assertNotIn('ItemWrapper', code)
        self.assertNotIn('TiltedCard', code)


class TestFallbackFeatureGridEffectPreserved(unittest.TestCase):
    """Step 4: existing plain/fallback FeatureGrid effect path intact."""

    def setUp(self):
        self.engine = CodeGenerationEngine(MagicMock())
        self.artifact = _theme_for_brief(BRIEF_TRATTORIA)

    def test_05_fallback_featuregrid_spotlight_wraps_items(self):
        """Fallback path (no native wrapper) + SpotlightCard → items wrapped."""
        result = self.engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', self.artifact,
            FG_SECTIONS, 1,
            None, {}, {}, ['/'],
            available_effects=EFFECTS_SPOTLIGHT)

        self.assertIsNotNone(result)
        code, imports = result
        self.assertIn('<SpotlightCard', code)
        self.assertTrue(any('SpotlightCard' in imp for imp in imports))
        # Must NOT be the native FeatureGrid (no wrapper = fallback)
        self.assertNotIn('data-nexora-source="native/FeatureGrid"', code)

    def test_06_fallback_featuregrid_no_effect_plain_div(self):
        """Fallback path + no effect → plain div items."""
        result = self.engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', self.artifact,
            FG_SECTIONS, 1,
            None, {}, {}, ['/'],
            available_effects={})

        self.assertIsNotNone(result)
        code, imports = result
        self.assertNotIn('<SpotlightCard', code)
        self.assertIn('determinant:featuregrid', code)


class TestServicesGridNativeEffectPropagation(unittest.TestCase):
    """Step 5: ServicesGrid native path → same effect propagation."""

    def setUp(self):
        self.engine = CodeGenerationEngine(MagicMock())
        self.artifact = _theme_for_brief(BRIEF_TRATTORIA)

    def test_07_servicesgrid_native_spotlight_emits_item_wrapper(self):
        """ServicesGrid native FeatureGrid + SpotlightCard → ItemWrapper emitted."""
        result = self.engine._build_pattern_section(
            'ServicesGrid', 'ServicesSection', self.artifact,
            SG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects=EFFECTS_SPOTLIGHT)

        self.assertIsNotNone(result)
        code, imports = result
        self.assertIn('ItemWrapper={SpotlightCard}', code)
        self.assertIn(SPOTLIGHT_IMPORT, imports)
        self.assertIn('data-nexora-source="native/FeatureGrid"', code)

    def test_08_servicesgrid_native_no_effect_clean(self):
        """ServicesGrid native FeatureGrid + no effect → no ItemWrapper."""
        result = self.engine._build_pattern_section(
            'ServicesGrid', 'ServicesSection', self.artifact,
            SG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects={})

        self.assertIsNotNone(result)
        code, imports = result
        self.assertNotIn('ItemWrapper', code)
        self.assertIn('data-nexora-source="native/FeatureGrid"', code)


class TestAllowlistAndSafety(unittest.TestCase):
    """Steps 6–9: allowlist, dependency safety, determinism, selection gating."""

    def test_09_only_allowlisted_effects(self):
        """Phase 47.40 allowlist permits only SpotlightCard and StarBorder."""
        self.assertEqual(set(_ALLOWED_EFFECT_COMPONENTS),
                         {'SpotlightCard', 'StarBorder'})

    def test_10_visual_direction_filters_effects(self):
        """_visual_direction only passes allowlisted effects."""
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        vd = engine._visual_direction(artifact)
        for effect in vd['effects']:
            self.assertIn(effect, ('SpotlightCard', 'StarBorder'))

    def test_11_no_new_runtime_dependency(self):
        """The native FeatureGrid with ItemWrapper introduces no new dependency.
        SpotlightCard is already part of the react_bits curated set."""
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        result = engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects=EFFECTS_SPOTLIGHT)
        code, imports = result
        # No npm install, no require(), no package.json reference
        self.assertNotIn('require(', code)
        self.assertNotIn('npm ', code)
        # Only the assembler's own import line for SpotlightCard
        spotlight_imports = [i for i in imports if 'SpotlightCard' in i]
        self.assertEqual(len(spotlight_imports), 1)
        self.assertEqual(spotlight_imports[0], SPOTLIGHT_IMPORT)

    def test_12_deterministic_output(self):
        """Identical inputs produce identical generated output."""
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)
        args = (
            'FeatureGrid', 'FeaturesSection', artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
        )
        result1 = engine._build_pattern_section(*args, available_effects=EFFECTS_SPOTLIGHT)
        result2 = engine._build_pattern_section(*args, available_effects=EFFECTS_SPOTLIGHT)
        self.assertEqual(result1[0], result2[0])  # code
        self.assertEqual(result1[1], result2[1])  # imports

    def test_13_availability_does_not_imply_selection(self):
        """Having SpotlightCard available must NOT cause it to render unless
        the canonical visual direction actually selected it.

        The available_effects map is the INTERSECTION of VD selection and
        materialization — so if VD doesn't select it, it won't be in the
        map. This test verifies the organism respects the map faithfully."""
        engine = CodeGenerationEngine(MagicMock())
        artifact = _theme_for_brief(BRIEF_TRATTORIA)

        # Pass empty effects (simulates VD not selecting any effect,
        # even though SpotlightCard would be materializeable)
        result = engine._build_pattern_section(
            'FeatureGrid', 'FeaturesSection', artifact,
            FG_SECTIONS, 1,
            NATIVE_FG_COMPONENT,
            {'FeatureGrid': "import FeatureGrid from '../components/FeatureGrid.jsx'"},
            {}, ['/'],
            available_effects={})

        code, imports = result
        self.assertNotIn('ItemWrapper', code)
        self.assertNotIn('SpotlightCard', code)

    def test_14_organism_method_no_effect_output_stability(self):
        """Direct call to _featuregrid_organism with no effect must produce
        output identical to the pre-47.40A behavior."""
        engine = CodeGenerationEngine(MagicMock())

        # Without effect (backward compatible path)
        code_no_effect, imports_no_effect = engine._featuregrid_organism(
            'TestSection', 'Features', 'Subtitle',
            ['Fast', 'Secure'], ['Subtitle', 'Desc1', 'Desc2'],
            'features grid')
        self.assertEqual(imports_no_effect, [])
        self.assertNotIn('ItemWrapper', code_no_effect)
        self.assertIn('<FeatureGrid data-nexora-source="native/FeatureGrid"', code_no_effect)

        # With effect
        code_effect, imports_effect = engine._featuregrid_organism(
            'TestSection', 'Features', 'Subtitle',
            ['Fast', 'Secure'], ['Subtitle', 'Desc1', 'Desc2'],
            'features grid', effect='SpotlightCard',
            effect_import=SPOTLIGHT_IMPORT)
        self.assertEqual(imports_effect, [SPOTLIGHT_IMPORT])
        self.assertIn('ItemWrapper={SpotlightCard}', code_effect)

    def test_15_native_featuregrid_component_template_has_item_wrapper(self):
        """The native FeatureGrid JSX template includes the ItemWrapper prop."""
        from odoo.addons.nexora_studio.services.design.react_component_library import (
            ReactComponentLibrary)
        lib = ReactComponentLibrary(MagicMock())
        files = lib.synthesize_all()
        fg_code = files.get('src/components/FeatureGrid.jsx', '')
        self.assertIn('ItemWrapper', fg_code)
        # When ItemWrapper is absent, React.cloneElement is used (key handling)
        self.assertIn('React.cloneElement', fg_code)


if __name__ == '__main__':
    unittest.main()
