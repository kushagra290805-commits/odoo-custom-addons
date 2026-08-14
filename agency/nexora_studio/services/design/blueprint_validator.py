# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, Optional, List, Union, Set
from .design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint,
    NavigationNode, ColorToken, TypographyToken, ExperienceBlueprint
)

_logger = logging.getLogger(__name__)

class ValidationResult:
    """Encapsulates the outcome of a DesignBlueprint semantic and integrity validation."""
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str], metrics: Dict[str, Any]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.metrics = metrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics
        }


class BlueprintValidator:
    """
    Exhaustive Semantic and Integrity Validator for DesignBlueprints.
    
    Verifies 7 core rulesets:
    1. Duplicate Pages (slugs, IDs, names)
    2. Navigation Integrity (target routing resolution)
    3. Component Hierarchy (depth bounds, layout primitives)
    4. Responsive Breakpoints (logical width ordering)
    5. Accessibility Metadata (WCAG contrast grades, alt text)
    6. Token Consistency (referential integrity of design tokens)
    7. Experience Consistency (reduced motion, AAA contrast, performance budgets)
    """

    MAX_COMPONENT_DEPTH = 10
    VALID_LAYOUT_TYPES = {'flex-row', 'flex-column', 'grid', 'absolute', 'stack'}
    VALID_ALIGNMENTS = {'start', 'center', 'end', 'space-between', 'space-around', 'stretch'}

    @classmethod
    def validate(cls, blueprint: Union[DesignBlueprint, Dict[str, Any]]) -> ValidationResult:
        if isinstance(blueprint, dict):
            blueprint = DesignBlueprint.from_dict(blueprint)

        errors: List[str] = []
        warnings: List[str] = []
        metrics: Dict[str, Any] = {
            "page_count": len(blueprint.pages),
            "section_count": 0,
            "component_count": 0,
            "token_count": 0,
            "placeholder_count": len(blueprint.placeholders),
            "animation_count": len(blueprint.animations)
        }

        # 1. Duplicate Pages
        cls._validate_duplicate_pages(blueprint, errors)

        # 2. Token Consistency Setup
        valid_token_ids: Set[str] = set()
        if blueprint.token_set:
            if blueprint.token_set.color_palette:
                for ct in blueprint.token_set.color_palette.tokens:
                    valid_token_ids.add(ct.id)
                if blueprint.token_set.color_palette.background_token_id:
                    valid_token_ids.add(blueprint.token_set.color_palette.background_token_id)
            if blueprint.token_set.typography_scale:
                for tt in blueprint.token_set.typography_scale.tokens:
                    valid_token_ids.add(tt.id)
            metrics["token_count"] = len(valid_token_ids)

        # 3. Component Hierarchy & Token Consistency inside Pages/Sections
        valid_targets: Set[str] = set()
        for page in blueprint.pages:
            valid_targets.add(page.slug)
            valid_targets.add(page.id)
            for sec in page.sections:
                metrics["section_count"] += 1
                valid_targets.add(sec.id)
                valid_targets.add(f"#{sec.id}")
                if sec.background_token_id and sec.background_token_id not in valid_token_ids and valid_token_ids:
                    errors.append(f"Section '{sec.name}' references non-existent background token: '{sec.background_token_id}'")
                for comp in sec.components:
                    cls._validate_component(comp, 1, errors, warnings, valid_token_ids, blueprint.placeholders, blueprint.animations, metrics)

        # 4. Navigation Integrity
        if blueprint.navigation and blueprint.navigation.root_nodes:
            for node in blueprint.navigation.root_nodes:
                cls._validate_navigation_node(node, valid_targets, errors, warnings)

        # 5. Responsive Breakpoints
        cls._validate_breakpoints(blueprint.breakpoints, errors, warnings)

        # 6. Accessibility Metadata
        cls._validate_accessibility(blueprint, errors, warnings)

        # 7. Experience Consistency
        cls._validate_experience_consistency(blueprint.experience, blueprint, errors, warnings)

        is_valid = len(errors) == 0
        if not is_valid:
            _logger.warning("DesignBlueprint '%s' validation failed with %d errors and %d warnings.", blueprint.project_name, len(errors), len(warnings))
        else:
            _logger.info("DesignBlueprint '%s' validation succeeded (%d warnings).", blueprint.project_name, len(warnings))

        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings, metrics=metrics)

    @classmethod
    def _validate_duplicate_pages(cls, blueprint: DesignBlueprint, errors: List[str]):
        slugs = set()
        ids = set()
        for page in blueprint.pages:
            if page.slug in slugs:
                errors.append(f"Duplicate page slug detected: '{page.slug}'")
            slugs.add(page.slug)
            
            if page.id in ids:
                errors.append(f"Duplicate page ID detected: '{page.id}'")
            ids.add(page.id)

    @classmethod
    def _validate_navigation_node(cls, node: NavigationNode, valid_targets: Set[str], errors: List[str], warnings: List[str]):
        if not node.is_external and node.target_slug_or_id not in valid_targets and not node.target_slug_or_id.startswith('http'):
            errors.append(f"Navigation node '{node.label}' targets non-existent route or section: '{node.target_slug_or_id}'")
        for child in node.children:
            cls._validate_navigation_node(child, valid_targets, errors, warnings)

    @classmethod
    def _validate_component(cls, comp: ComponentBlueprint, depth: int, errors: List[str], warnings: List[str],
                            valid_token_ids: Set[str], placeholders: Dict[str, Any], animations: Dict[str, Any], metrics: Dict[str, Any]):
        metrics["component_count"] += 1
        if depth > cls.MAX_COMPONENT_DEPTH:
            errors.append(f"Component '{comp.name}' exceeds maximum allowed nesting depth of {cls.MAX_COMPONENT_DEPTH}")
            return

        if comp.layout_type not in cls.VALID_LAYOUT_TYPES:
            warnings.append(f"Component '{comp.name}' uses non-standard layout_type: '{comp.layout_type}'")
        if comp.alignment not in cls.VALID_ALIGNMENTS:
            warnings.append(f"Component '{comp.name}' uses non-standard alignment: '{comp.alignment}'")

        if valid_token_ids:
            for ref in comp.token_references:
                if ref not in valid_token_ids:
                    errors.append(f"Component '{comp.name}' references non-existent design token ID: '{ref}'")

        for ph_id in comp.asset_placeholders:
            if ph_id not in placeholders:
                errors.append(f"Component '{comp.name}' references non-existent asset placeholder ID: '{ph_id}'")

        for anim_id in comp.animation_rule_ids:
            if anim_id not in animations:
                errors.append(f"Component '{comp.name}' references non-existent animation rule ID: '{anim_id}'")

        for child in comp.children:
            cls._validate_component(child, depth + 1, errors, warnings, valid_token_ids, placeholders, animations, metrics)

    @classmethod
    def _validate_breakpoints(cls, breakpoints: List[Any], errors: List[str], warnings: List[str]):
        if not breakpoints:
            warnings.append("No responsive breakpoints defined in DesignBlueprint.")
            return

        last_width = -1
        for bp in breakpoints:
            if bp.min_width_px <= last_width:
                errors.append(f"Responsive breakpoint '{bp.label}' min_width_px ({bp.min_width_px}px) is not strictly greater than previous threshold ({last_width}px).")
            last_width = bp.min_width_px

    @classmethod
    def _validate_accessibility(cls, blueprint: DesignBlueprint, errors: List[str], warnings: List[str]):
        if blueprint.token_set and blueprint.token_set.color_palette:
            for token in blueprint.token_set.color_palette.tokens:
                if token.wcag_grade.upper() == 'FAIL':
                    errors.append(f"Color token '{token.name}' ({token.hex_value}) fails WCAG contrast requirements.")
                elif token.contrast_ratio_on_background < 4.5 and token.role in ('primary', 'text', 'content'):
                    warnings.append(f"Color token '{token.name}' has contrast ratio {token.contrast_ratio_on_background}, below standard WCAG AA 4.5 for text.")

        for ph_id, ph in blueprint.placeholders.items():
            if not ph.alt_text and ph.aria_role == 'img':
                warnings.append(f"Asset placeholder '{ph.name}' lacks descriptive alt_text for screen readers.")

    @classmethod
    def _validate_experience_consistency(cls, exp: Optional[ExperienceBlueprint], blueprint: DesignBlueprint, errors: List[str], warnings: List[str]):
        if not exp:
            return

        a11y_prefs = exp.accessibility_preferences or {}
        reduced_motion = a11y_prefs.get('prefers_reduced_motion', False)
        wcag_target = str(a11y_prefs.get('wcag_target', 'AA')).upper()

        if reduced_motion:
            if exp.animation_intensity.lower() == 'expressive':
                errors.append("Experience Consistency Error: 'prefers_reduced_motion' is enabled in accessibility preferences, but animation_intensity is set to 'expressive'.")
            if exp.parallax_level.lower() in ('medium', 'high'):
                errors.append(f"Experience Consistency Error: 'prefers_reduced_motion' is enabled, but parallax_level is set to '{exp.parallax_level}'.")

        if wcag_target == 'AAA' and blueprint.token_set and blueprint.token_set.color_palette:
            for token in blueprint.token_set.color_palette.tokens:
                if token.role in ('primary', 'text', 'content') and token.contrast_ratio_on_background < 7.0:
                    warnings.append(f"Experience Consistency Warning: wcag_target is set to AAA, but color token '{token.name}' has contrast ratio {token.contrast_ratio_on_background} (< 7.0).")

        budget = exp.performance_budget or {}
        if exp.rendering_preference.upper() in ('3D', 'HYBRID'):
            max_payload = budget.get('max_asset_payload_kb', 2048)
            if max_payload < 1024:
                warnings.append(f"Experience Consistency Warning: rendering_preference is '{exp.rendering_preference}', but max_asset_payload_kb budget ({max_payload}KB) is very restrictive for 3D/hybrid assets.")
