# -*- coding: utf-8 -*-
"""
Phase 11E — AI Layout Intelligence & Responsive Composition Engine (Validator & Quality Scoring)

This module implements the LayoutValidator and LayoutQualityScore models.
In strict adherence to SOLID principles and Phase 11E architectural constraints:
- Enforces 6 core validation rulesets: Nesting Depth, Spacing Consistency, Alignment Compatibility,
  Overflow Risk Detection, Accessibility Reading Order, and Responsive Consistency.
- Computes comprehensive LayoutQualityScore metrics (hierarchy, balance, whitespace, accessibility,
  responsive, performance, and overall scores) alongside validation results.
- Zero references to React, HTML, CSS, Three.js, or Penpot APIs.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Union
from .layout_domain import LayoutTree, LayoutNode, Container, Grid, Stack, Split, Masonry, Overlay, SectionFlow

_logger = logging.getLogger(__name__)

# Standard Spacing Scale increments in pixels (from Design System Phase 11D)
STANDARD_SPACING_SCALE: Set[int] = {0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128, 160}

# Viewport max width bounds in pixels
VIEWPORT_MAX_WIDTH_BOUNDS: Dict[str, int] = {
    "mobile": 767,
    "tablet": 1023,
    "desktop": 1439,
    "wide_desktop": 2560
}


@dataclass
class LayoutQualityScore:
    """
    Quantitative scoring model for layout composition quality.
    All scores range from 0.0 to 100.0.
    """
    hierarchy_score: float = 100.0
    balance_score: float = 100.0
    whitespace_score: float = 100.0
    accessibility_score: float = 100.0
    responsive_score: float = 100.0
    performance_score: float = 100.0
    overall_score: float = 100.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutQualityScore':
        if not data:
            return cls()
        return cls(
            hierarchy_score=float(data.get('hierarchy_score', 100.0)),
            balance_score=float(data.get('balance_score', 100.0)),
            whitespace_score=float(data.get('whitespace_score', 100.0)),
            accessibility_score=float(data.get('accessibility_score', 100.0)),
            responsive_score=float(data.get('responsive_score', 100.0)),
            performance_score=float(data.get('performance_score', 100.0)),
            overall_score=float(data.get('overall_score', 100.0))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'hierarchy_score': round(self.hierarchy_score, 2),
            'balance_score': round(self.balance_score, 2),
            'whitespace_score': round(self.whitespace_score, 2),
            'accessibility_score': round(self.accessibility_score, 2),
            'responsive_score': round(self.responsive_score, 2),
            'performance_score': round(self.performance_score, 2),
            'overall_score': round(self.overall_score, 2)
        }

    def compute_overall(self):
        self.hierarchy_score = max(0.0, min(100.0, self.hierarchy_score))
        self.balance_score = max(0.0, min(100.0, self.balance_score))
        self.whitespace_score = max(0.0, min(100.0, self.whitespace_score))
        self.accessibility_score = max(0.0, min(100.0, self.accessibility_score))
        self.responsive_score = max(0.0, min(100.0, self.responsive_score))
        self.performance_score = max(0.0, min(100.0, self.performance_score))
        
        self.overall_score = round(
            (self.hierarchy_score + self.balance_score + self.whitespace_score +
             self.accessibility_score + self.responsive_score + self.performance_score) / 6.0,
            2
        )


@dataclass
class LayoutValidationResult:
    """
    Structured outcome of layout validation and quality scoring.
    """
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    quality_score: LayoutQualityScore = field(default_factory=LayoutQualityScore)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutValidationResult':
        if not data:
            return cls()
        qs_data = data.get('quality_score')
        return cls(
            is_valid=bool(data.get('is_valid', True)),
            errors=list(data.get('errors', [])),
            warnings=list(data.get('warnings', [])),
            metrics=dict(data.get('metrics', {})),
            quality_score=LayoutQualityScore.from_dict(qs_data) if isinstance(qs_data, dict) else (qs_data or LayoutQualityScore())
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'metrics': self.metrics,
            'quality_score': self.quality_score.to_dict() if self.quality_score and hasattr(self.quality_score, 'to_dict') else None
        }


class LayoutValidator:
    """
    Authoritative validation engine for layout compositions.
    Evaluates trees against 6 core rulesets and computes quality metrics.
    """

    @classmethod
    def validate(cls, blueprint: Any, layout_tree: Optional[LayoutTree] = None) -> LayoutValidationResult:
        """
        Validate a layout tree (or extract layout trees from a DesignBlueprint) and compute quality score.
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        total_nodes_checked = 0
        max_nesting_depth_found = 0
        spacing_violations = 0
        alignment_conflicts = 0
        overflow_risks = 0
        accessibility_warnings = 0
        responsive_anomalies = 0

        # Quality score component deductions
        hierarchy_deduction = 0.0
        balance_deduction = 0.0
        whitespace_deduction = 0.0
        accessibility_deduction = 0.0
        responsive_deduction = 0.0
        performance_deduction = 0.0

        # Collect trees to validate
        trees_to_validate: List[LayoutTree] = []
        if layout_tree:
            if isinstance(layout_tree, dict):
                trees_to_validate.append(LayoutTree.from_dict(layout_tree))
            else:
                trees_to_validate.append(layout_tree)
        elif blueprint:
            # Extract from blueprint pages/sections
            pages = getattr(blueprint, 'pages', []) if not isinstance(blueprint, dict) else blueprint.get('pages', [])
            for p in pages:
                sections = getattr(p, 'sections', []) if not isinstance(p, dict) else p.get('sections', [])
                for s in sections:
                    s_tree = getattr(s, 'layout_tree', None) if not isinstance(s, dict) else s.get('layout_tree')
                    if s_tree:
                        if isinstance(s_tree, dict):
                            trees_to_validate.append(LayoutTree.from_dict(s_tree))
                        elif isinstance(s_tree, LayoutTree):
                            trees_to_validate.append(s_tree)

        if not trees_to_validate:
            warnings.append("[Layout Validation] No layout tree provided or found in blueprint to validate.")
            return LayoutValidationResult(is_valid=True, warnings=warnings)

        for tree in trees_to_validate:
            viewport = tree.viewport
            vp_max_width = VIEWPORT_MAX_WIDTH_BOUNDS.get(viewport, 1439)

            # Check SectionFlow spacing
            if tree.section_flow:
                sf = tree.section_flow
                if sf.section_spacing_px not in STANDARD_SPACING_SCALE:
                    warnings.append(f"[Spacing Consistency] SectionFlow '{sf.flow_id}' specifies non-standard section spacing ({sf.section_spacing_px}px).")
                    spacing_violations += 1
                    whitespace_deduction += 5.0

            # Traverse layout node hierarchy
            def inspect_node(node: LayoutNode, depth: int):
                nonlocal total_nodes_checked, max_nesting_depth_found, spacing_violations, alignment_conflicts
                nonlocal overflow_risks, accessibility_warnings, responsive_anomalies
                nonlocal hierarchy_deduction, balance_deduction, whitespace_deduction, accessibility_deduction
                nonlocal responsive_deduction, performance_deduction

                total_nodes_checked += 1
                if depth > max_nesting_depth_found:
                    max_nesting_depth_found = depth

                # 1. Nesting Depth Ruleset
                if depth > 6:
                    warnings.append(f"[Nesting Depth] Layout node '{node.name}' (ID: {node.node_id}) exceeds maximum recommended nesting depth (depth={depth} > 6).")
                    performance_deduction += 10.0

                # 2. Spacing Consistency Ruleset
                if isinstance(node, Container):
                    if node.padding_px < 0 or node.padding_px not in STANDARD_SPACING_SCALE:
                        warnings.append(f"[Spacing Consistency] Container '{node.name}' specifies non-standard padding ({node.padding_px}px).")
                        spacing_violations += 1
                        whitespace_deduction += 4.0
                    if node.margin_px < 0 or node.margin_px not in STANDARD_SPACING_SCALE:
                        warnings.append(f"[Spacing Consistency] Container '{node.name}' specifies non-standard margin ({node.margin_px}px).")
                        spacing_violations += 1
                        whitespace_deduction += 4.0
                elif isinstance(node, Stack):
                    if node.gap_px < 0 or node.gap_px not in STANDARD_SPACING_SCALE:
                        warnings.append(f"[Spacing Consistency] Stack '{node.name}' specifies non-standard gap ({node.gap_px}px).")
                        spacing_violations += 1
                        whitespace_deduction += 4.0
                elif isinstance(node, Grid):
                    if node.gutter_px < 0 or node.gutter_px not in STANDARD_SPACING_SCALE:
                        warnings.append(f"[Spacing Consistency] Grid '{node.name}' specifies non-standard gutter ({node.gutter_px}px).")
                        spacing_violations += 1
                        whitespace_deduction += 4.0

                # 3. Alignment Compatibility Ruleset
                if node.alignment and node.constraints:
                    if node.alignment.horizontal_align == "stretch" and node.constraints.max_width_px and node.constraints.max_width_px < 300:
                        warnings.append(f"[Alignment Consistency] Node '{node.name}' combines horizontal stretch alignment with a restrictive max_width_px ({node.constraints.max_width_px}px).")
                        alignment_conflicts += 1
                        balance_deduction += 5.0
                if isinstance(node, Stack) and len(node.children) == 1 and node.alignment and node.alignment.content_distribution == "space-between":
                    warnings.append(f"[Alignment Consistency] Stack '{node.name}' uses 'space-between' content distribution with only a single child node.")
                    alignment_conflicts += 1
                    balance_deduction += 3.0

                # 4. Overflow Risk Ruleset
                if node.constraints and node.constraints.min_width_px:
                    if node.constraints.min_width_px > vp_max_width:
                        if not node.constraints.overflow_behavior or node.constraints.overflow_behavior not in ("scroll", "wrap"):
                            errors.append(f"[Overflow Risk] Node '{node.name}' specifies min_width_px={node.constraints.min_width_px}px exceeding viewport '{viewport}' bounds ({vp_max_width}px) without scroll/wrap overflow behavior.")
                            overflow_risks += 1
                            responsive_deduction += 15.0
                            performance_deduction += 5.0

                # 5. Accessibility Reading Order & Flow Ruleset
                if isinstance(node, Overlay):
                    has_focus_trap = False
                    for b in node.behaviors:
                        if b.behavior_type in ("sticky", "pinned", "floating") or b.metadata.get("focus_trap", False):
                            has_focus_trap = True
                    if node.overlay_type in ("modal", "drawer") and not has_focus_trap and not node.metadata.get("focus_trap"):
                        warnings.append(f"[Accessibility Flow] Overlay node '{node.name}' (type '{node.overlay_type}') lacks explicit focus trap or modal pinning behavior.")
                        accessibility_warnings += 1
                        accessibility_deduction += 10.0

                # 6. Responsive Consistency Ruleset
                if isinstance(node, Masonry):
                    cols_map = node.columns_per_breakpoint
                    mob_cols = cols_map.get("mobile", 1)
                    desk_cols = cols_map.get("desktop", 3)
                    if mob_cols > desk_cols:
                        errors.append(f"[Responsive Consistency] Masonry '{node.name}' specifies more columns on mobile ({mob_cols}) than desktop ({desk_cols}).")
                        responsive_anomalies += 1
                        responsive_deduction += 20.0
                elif isinstance(node, Split) and viewport == "mobile":
                    if not node.stack_on_mobile and node.split_ratio != "100-0":
                        warnings.append(f"[Responsive Consistency] Split node '{node.name}' has stack_on_mobile=False on viewport 'mobile', risking horizontal crowding.")
                        responsive_anomalies += 1
                        responsive_deduction += 10.0

                # Recurse children
                for child in node.children:
                    inspect_node(child, depth + 1)

            if tree.root_node:
                inspect_node(tree.root_node, 1)

        # Compute final quality scores
        qs = LayoutQualityScore(
            hierarchy_score=max(0.0, 100.0 - hierarchy_deduction),
            balance_score=max(0.0, 100.0 - balance_deduction),
            whitespace_score=max(0.0, 100.0 - whitespace_deduction),
            accessibility_score=max(0.0, 100.0 - accessibility_deduction),
            responsive_score=max(0.0, 100.0 - responsive_deduction),
            performance_score=max(0.0, 100.0 - performance_deduction)
        )
        qs.compute_overall()

        metrics = {
            "total_nodes_checked": total_nodes_checked,
            "max_nesting_depth_found": max_nesting_depth_found,
            "spacing_violations": spacing_violations,
            "alignment_conflicts": alignment_conflicts,
            "overflow_risks": overflow_risks,
            "accessibility_warnings": accessibility_warnings,
            "responsive_anomalies": responsive_anomalies,
            "error_count": len(errors),
            "warning_count": len(warnings)
        }

        is_valid = len(errors) == 0

        return LayoutValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            quality_score=qs
        )
