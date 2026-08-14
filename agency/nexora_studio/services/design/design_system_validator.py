# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from .design_blueprint import DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint
from .design_system import DesignSystem, ComponentDefinition, ComponentLibrary
from .component_intelligence import ComponentIntelligence

@dataclass
class DesignSystemValidationResult:
    """Structured validation report from the Design System Validator."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics
        }


class DesignSystemValidator:
    """
    Design System Validation Engine.
    Verifies token usage, spacing consistency, typography hierarchy, layout consistency,
    accessibility compliance, and responsive compatibility against the active Design System.
    100% provider-neutral and rendering-neutral.
    """

    @classmethod
    def validate(cls, blueprint: Union[DesignBlueprint, Dict[str, Any]], design_system: Optional[DesignSystem] = None) -> DesignSystemValidationResult:
        """Execute all 6 core Design System validation rulesets against a DesignBlueprint."""
        if isinstance(blueprint, dict):
            bp = DesignBlueprint.from_dict(blueprint)
        else:
            bp = blueprint

        sys = design_system or DesignSystem(
            system_id="sys_default",
            name="Default Design System",
            library=ComponentIntelligence.get_default_library()
        )

        errors: List[str] = []
        warnings: List[str] = []
        
        # Build index of available tokens from blueprint's token_set if present
        valid_color_ids = set()
        valid_typo_ids = set()
        if bp.token_set:
            if bp.token_set.color_palette:
                for t in bp.token_set.color_palette.tokens:
                    valid_color_ids.add(t.id)
            if bp.token_set.typography_scale:
                for t in bp.token_set.typography_scale.tokens:
                    valid_typo_ids.add(t.id)

        all_token_ids = valid_color_ids | valid_typo_ids

        # Build index of asset placeholders
        valid_placeholder_ids = {ph.id for ph in (bp.placeholders.values() if isinstance(bp.placeholders, dict) else bp.placeholders)} if bp.placeholders else set()

        # Metrics trackers
        total_components_checked = 0
        library_defined_components = 0
        spacing_violations_count = 0

        # Traverse pages and sections
        for page in bp.pages:
            h1_count = 0
            for sec in page.sections:
                if sec.background_token_id and (not all_token_ids or sec.background_token_id not in all_token_ids):
                    errors.append(f"[Token Usage] Section '{sec.name}' references non-existent background token: '{sec.background_token_id}'.")

                # Recursively check components in section
                def check_comp(comp: ComponentBlueprint, depth: int):
                    nonlocal total_components_checked, library_defined_components, spacing_violations_count, h1_count
                    total_components_checked += 1

                    # 1. Token Usage Ruleset
                    for tok_ref in comp.token_references:
                        if not all_token_ids or tok_ref not in all_token_ids:
                            errors.append(f"[Token Usage] Component '{comp.name}' (ID: {comp.id}) references non-existent token: '{tok_ref}'.")

                    # 2. Layout Consistency Ruleset
                    if comp.layout_type not in sys.layout_rules.allowed_layout_types:
                        warnings.append(f"[Layout Consistency] Component '{comp.name}' uses non-standard layout_type: '{comp.layout_type}'. Allowed: {sys.layout_rules.allowed_layout_types}.")
                    if comp.alignment not in sys.layout_rules.allowed_alignments:
                        warnings.append(f"[Layout Consistency] Component '{comp.name}' uses non-standard alignment: '{comp.alignment}'. Allowed: {sys.layout_rules.allowed_alignments}.")
                    if comp.width_mode not in sys.layout_rules.allowed_width_modes:
                        warnings.append(f"[Layout Consistency] Component '{comp.name}' uses non-standard width_mode: '{comp.width_mode}'. Allowed: {sys.layout_rules.allowed_width_modes}.")

                    # 3. Spacing Consistency Ruleset
                    # If component or definition specifies padding/gap in design constraints or responsive rules, check against spacing scale
                    if comp.definition_id and comp.definition_id in sys.library.definitions:
                        library_defined_components += 1
                        def_obj = sys.library.definitions[comp.definition_id]

                        # Check responsive padding against SpacingScale
                        for bp_key, r_rule in def_obj.responsive_rules.items():
                            if isinstance(r_rule, dict):
                                p_val = r_rule.get("padding_px")
                                if p_val is not None and p_val not in sys.spacing_scale.values_px:
                                    spacing_violations_count += 1
                                    warnings.append(f"[Spacing Consistency] Definition '{def_obj.name}' ({bp_key}) uses padding_px={p_val}, not in SpacingScale {sys.spacing_scale.values_px}.")
                                g_val = r_rule.get("gap_px")
                                if g_val is not None and g_val not in sys.spacing_scale.values_px:
                                    spacing_violations_count += 1
                                    warnings.append(f"[Spacing Consistency] Definition '{def_obj.name}' ({bp_key}) uses gap_px={g_val}, not in SpacingScale {sys.spacing_scale.values_px}.")

                        # 4. Typography Hierarchy Ruleset
                        a11y_req = def_obj.accessibility_requirements
                        h_lvl = a11y_req.get("heading_level")
                        if h_lvl is not None:
                            if h_lvl == 1:
                                h1_count += 1
                            elif not (1 <= h_lvl <= 6):
                                errors.append(f"[Typography Hierarchy] Definition '{def_obj.name}' specifies invalid heading_level: {h_lvl}.")

                        # 5. Accessibility Compliance Ruleset
                        min_wcag = a11y_req.get("minimum_wcag_grade")
                        if min_wcag == "AA" and bp.token_set and bp.token_set.color_palette:
                            for tok_id in comp.token_references:
                                for c_tok in bp.token_set.color_palette.tokens:
                                    if c_tok.id == tok_id and str(c_tok.wcag_grade).upper() == "FAIL":
                                        errors.append(f"[Accessibility Compliance] Component '{comp.name}' uses color token '{tok_id}' which has wcag_grade='Fail', violating definition minimum AA.")

                        # Check asset placeholder requirements against definition's AssetRequirements
                        if def_obj.asset_requirements and def_obj.asset_requirements.required_assets:
                            for req_asset in def_obj.asset_requirements.required_assets:
                                # Check if any placeholder assigned to comp matches this required asset type
                                found_match = False
                                for ph_id in comp.asset_placeholders:
                                    if bp.placeholders:
                                        ph_items = bp.placeholders.values() if isinstance(bp.placeholders, dict) else bp.placeholders
                                        for ph in ph_items:
                                            if ph.id == ph_id and (ph.asset_type == req_asset or req_asset in ph.name.lower()):
                                                found_match = True
                                                break
                                if not found_match and len(comp.asset_placeholders) == 0:
                                    warnings.append(f"[Asset Requirements] Component '{comp.name}' (definition '{def_obj.id}') lacks required asset type '{req_asset}'.")

                    for child in comp.children:
                        check_comp(child, depth + 1)

                for comp in sec.components:
                    check_comp(comp, 1)

            # Check single H1 rule per page
            if h1_count > 1:
                warnings.append(f"[Typography Hierarchy] Page '{page.name}' ({page.slug}) contains {h1_count} H1 headings. SEO best practice is exactly 1 H1 per page.")

        # 6. Responsive Compatibility Ruleset
        if bp.breakpoints:
            for brk in bp.breakpoints:
                if brk.min_width_px > sys.grid_system.max_container_width_px and brk.label == "desktop":
                    warnings.append(f"[Responsive Compatibility] Desktop breakpoint min_width_px ({brk.min_width_px}) exceeds GridSystem max_container_width_px ({sys.grid_system.max_container_width_px}).")

        is_valid = len(errors) == 0
        metrics = {
            "total_components_checked": total_components_checked,
            "library_defined_components": library_defined_components,
            "spacing_violations_count": spacing_violations_count,
            "error_count": len(errors),
            "warning_count": len(warnings)
        }

        return DesignSystemValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metrics=metrics
        )
