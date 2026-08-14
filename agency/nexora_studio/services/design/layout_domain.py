# -*- coding: utf-8 -*-
"""
Phase 11E — AI Layout Intelligence & Responsive Composition Engine (Domain Model)

This module implements the authoritative, provider-neutral, and rendering-neutral Layout Domain Model.
In strict adherence to SOLID principles and Phase 11E architectural constraints:
- Zero references to React, HTML, CSS, Three.js, or Penpot APIs.
- Expresses spatial structures, constraints, content hierarchy, regions, flows, and behaviors cleanly.
- Defines 6 core primitive node types (Container, Grid, Stack, Split, Masonry, Overlay), rule models,
  LayoutTree, LayoutDefinition, and LayoutCatalog.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

_logger = logging.getLogger(__name__)


# =========================================================================
# 1. BEHAVIOR & RULE MODELS
# =========================================================================

VALID_LAYOUT_BEHAVIORS = {
    "sticky",
    "pinned",
    "floating",
    "collapsible",
    "expandable",
    "reorderable",
    "scroll_snap",
    "progressive_reveal",
    "lazy_loaded",
    "virtualized"
}

@dataclass
class LayoutBehavior:
    """
    Provider-neutral representation of dynamic layout behavior.
    Describes behavior only without referencing CSS, HTML, React, Penpot, or Three.js.
    """
    behavior_type: str = "sticky"
    trigger: str = "scroll"       # e.g., 'scroll', 'click', 'hover', 'viewport_enter', 'always'
    duration_ms: int = 300
    offset_px: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.behavior_type not in VALID_LAYOUT_BEHAVIORS:
            _logger.warning("LayoutBehavior initialized with non-standard type: '%s'", self.behavior_type)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutBehavior':
        if not data:
            return cls()
        return cls(
            behavior_type=data.get('behavior_type', 'sticky'),
            trigger=data.get('trigger', 'scroll'),
            duration_ms=int(data.get('duration_ms', 300)),
            offset_px=int(data.get('offset_px', 0)),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'behavior_type': self.behavior_type,
            'trigger': self.trigger,
            'duration_ms': self.duration_ms,
            'offset_px': self.offset_px,
            'metadata': self.metadata
        }


@dataclass
class ConstraintRule:
    """
    Spatial dimension, aspect ratio, and overflow constraint rules for layout nodes.
    """
    min_width_px: Optional[int] = None
    max_width_px: Optional[int] = None
    min_height_px: Optional[int] = None
    max_height_px: Optional[int] = None
    aspect_ratio: Optional[str] = None      # e.g., '16:9', '1:1', '4:3', '21:9'
    overflow_behavior: str = "wrap"         # 'wrap', 'clip', 'scroll', 'expand'
    z_layer_priority: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConstraintRule':
        if not data:
            return cls()
        return cls(
            min_width_px=data.get('min_width_px'),
            max_width_px=data.get('max_width_px'),
            min_height_px=data.get('min_height_px'),
            max_height_px=data.get('max_height_px'),
            aspect_ratio=data.get('aspect_ratio'),
            overflow_behavior=data.get('overflow_behavior', 'wrap'),
            z_layer_priority=int(data.get('z_layer_priority', 0))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'min_width_px': self.min_width_px,
            'max_width_px': self.max_width_px,
            'min_height_px': self.min_height_px,
            'max_height_px': self.max_height_px,
            'aspect_ratio': self.aspect_ratio,
            'overflow_behavior': self.overflow_behavior,
            'z_layer_priority': self.z_layer_priority
        }


@dataclass
class AlignmentRule:
    """
    Horizontal and vertical alignment and content distribution rules.
    """
    horizontal_align: str = "start"         # 'start', 'center', 'end', 'stretch', 'space-between', 'space-around'
    vertical_align: str = "top"             # 'top', 'middle', 'bottom', 'baseline', 'stretch'
    content_distribution: str = "normal"    # 'normal', 'packed', 'evenly'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlignmentRule':
        if not data:
            return cls()
        return cls(
            horizontal_align=data.get('horizontal_align', 'start'),
            vertical_align=data.get('vertical_align', 'top'),
            content_distribution=data.get('content_distribution', 'normal')
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'horizontal_align': self.horizontal_align,
            'vertical_align': self.vertical_align,
            'content_distribution': self.content_distribution
        }


@dataclass
class ContentRegion:
    """
    Named spatial area within a layout (e.g., 'header_region', 'hero_main', 'sidebar_left', 'footer_sitemap').
    Establishes visual priority and default constraints for assigned components.
    """
    region_id: str = "main_region"
    name: str = "Main Content Region"
    priority: int = 1                       # 1 = primary visual hierarchy, 2 = supporting, 3 = tertiary
    allowed_component_categories: List[str] = field(default_factory=list)
    default_constraints: Optional[ConstraintRule] = None
    default_alignment: Optional[AlignmentRule] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentRegion':
        if not data:
            return cls()
        const_data = data.get('default_constraints')
        align_data = data.get('default_alignment')
        return cls(
            region_id=data.get('region_id', 'main_region'),
            name=data.get('name', 'Main Content Region'),
            priority=int(data.get('priority', 1)),
            allowed_component_categories=list(data.get('allowed_component_categories', [])),
            default_constraints=ConstraintRule.from_dict(const_data) if isinstance(const_data, dict) else const_data,
            default_alignment=AlignmentRule.from_dict(align_data) if isinstance(align_data, dict) else align_data
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'region_id': self.region_id,
            'name': self.name,
            'priority': self.priority,
            'allowed_component_categories': self.allowed_component_categories,
            'default_constraints': self.default_constraints.to_dict() if self.default_constraints and hasattr(self.default_constraints, 'to_dict') else None,
            'default_alignment': self.default_alignment.to_dict() if self.default_alignment and hasattr(self.default_alignment, 'to_dict') else None
        }


@dataclass
class SectionFlow:
    """
    Transition and sequencing rules between sections in a layout tree.
    """
    flow_id: str = "flow_standard"
    transition_type: str = "stack_vertical" # 'stack_vertical', 'scroll_snap', 'parallax_overlap', 'split_transition', 'pinned_scroll'
    section_spacing_px: int = 64
    background_continuity: bool = True
    behaviors: List[LayoutBehavior] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SectionFlow':
        if not data:
            return cls()
        behaviors_data = data.get('behaviors', [])
        behaviors = [LayoutBehavior.from_dict(b) if isinstance(b, dict) else b for b in behaviors_data]
        return cls(
            flow_id=data.get('flow_id', 'flow_standard'),
            transition_type=data.get('transition_type', 'stack_vertical'),
            section_spacing_px=int(data.get('section_spacing_px', 64)),
            background_continuity=bool(data.get('background_continuity', True)),
            behaviors=behaviors
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'flow_id': self.flow_id,
            'transition_type': self.transition_type,
            'section_spacing_px': self.section_spacing_px,
            'background_continuity': self.background_continuity,
            'behaviors': [b.to_dict() if hasattr(b, 'to_dict') else b for b in self.behaviors]
        }


# =========================================================================
# 2. LAYOUT PRIMITIVE NODES
# =========================================================================

@dataclass
class LayoutNode:
    """
    Base primitive node in a LayoutTree hierarchy.
    Can represent containers, grids, stacks, splits, masonries, or overlays.
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: str = "container"            # 'container', 'grid', 'stack', 'split', 'masonry', 'overlay'
    name: str = "Layout Node"
    region_id: Optional[str] = None
    component_id: Optional[str] = None      # References ComponentBlueprint.id or definition_id
    constraints: Optional[ConstraintRule] = None
    alignment: Optional[AlignmentRule] = None
    behaviors: List[LayoutBehavior] = field(default_factory=list)
    children: List['LayoutNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def _parse_base_node(cls, data: Dict[str, Any]) -> 'LayoutNode':
        if not data:
            return LayoutNode()
        const_data = data.get('constraints')
        align_data = data.get('alignment')
        behaviors_data = data.get('behaviors', [])
        children_data = data.get('children', [])

        return LayoutNode(
            node_id=data.get('node_id', str(uuid.uuid4())),
            node_type=data.get('node_type', 'container').lower(),
            name=data.get('name', 'Layout Node'),
            region_id=data.get('region_id'),
            component_id=data.get('component_id'),
            constraints=ConstraintRule.from_dict(const_data) if isinstance(const_data, dict) else const_data,
            alignment=AlignmentRule.from_dict(align_data) if isinstance(align_data, dict) else align_data,
            behaviors=[LayoutBehavior.from_dict(b) if isinstance(b, dict) else b for b in behaviors_data],
            children=[LayoutNode.from_dict(c) if isinstance(c, dict) else c for c in children_data],
            metadata=data.get('metadata', {})
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutNode':
        if not data:
            return cls()
        node_type = data.get('node_type', 'container').lower()
        
        # Dispatch to subclass if called directly on LayoutNode
        if cls is LayoutNode:
            if node_type == 'grid':
                return Grid.from_dict(data)
            elif node_type == 'stack':
                return Stack.from_dict(data)
            elif node_type == 'split':
                return Split.from_dict(data)
            elif node_type == 'masonry':
                return Masonry.from_dict(data)
            elif node_type == 'overlay':
                return Overlay.from_dict(data)
            elif node_type == 'container':
                return Container.from_dict(data)

        return cls._parse_base_node(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'node_type': self.node_type,
            'name': self.name,
            'region_id': self.region_id,
            'component_id': self.component_id,
            'constraints': self.constraints.to_dict() if self.constraints and hasattr(self.constraints, 'to_dict') else None,
            'alignment': self.alignment.to_dict() if self.alignment and hasattr(self.alignment, 'to_dict') else None,
            'behaviors': [b.to_dict() if hasattr(b, 'to_dict') else b for b in self.behaviors],
            'children': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.children],
            'metadata': self.metadata
        }


@dataclass
class Container(LayoutNode):
    """
    Basic bounding box container primitive with margin, padding, border radius, and styling.
    """
    node_type: str = "container"
    padding_px: int = 16
    margin_px: int = 0
    border_radius_px: int = 0
    background_style: str = "default"       # 'default', 'subtle', 'highlight', 'transparent', 'elevated'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Container':
        base = LayoutNode._parse_base_node(data)
        return cls(
            node_id=base.node_id,
            node_type="container",
            name=base.name,
            region_id=base.region_id,
            component_id=base.component_id,
            constraints=base.constraints,
            alignment=base.alignment,
            behaviors=base.behaviors,
            children=base.children,
            metadata=base.metadata,
            padding_px=int(data.get('padding_px', 16)),
            margin_px=int(data.get('margin_px', 0)),
            border_radius_px=int(data.get('border_radius_px', 0)),
            background_style=data.get('background_style', 'default')
        )

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            'padding_px': self.padding_px,
            'margin_px': self.margin_px,
            'border_radius_px': self.border_radius_px,
            'background_style': self.background_style
        })
        return res


@dataclass
class Grid(LayoutNode):
    """
    Multi-column/row grid layout primitive.
    """
    node_type: str = "grid"
    columns: int = 12
    rows: int = 1
    gutter_px: int = 24
    column_span_default: int = 12
    sizing_mode: str = "fr"                 # 'fr', 'px', 'auto'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Grid':
        base = LayoutNode._parse_base_node(data)
        return cls(
            node_id=base.node_id,
            node_type="grid",
            name=base.name,
            region_id=base.region_id,
            component_id=base.component_id,
            constraints=base.constraints,
            alignment=base.alignment,
            behaviors=base.behaviors,
            children=base.children,
            metadata=base.metadata,
            columns=int(data.get('columns', 12)),
            rows=int(data.get('rows', 1)),
            gutter_px=int(data.get('gutter_px', 24)),
            column_span_default=int(data.get('column_span_default', 12)),
            sizing_mode=data.get('sizing_mode', 'fr')
        )

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            'columns': self.columns,
            'rows': self.rows,
            'gutter_px': self.gutter_px,
            'column_span_default': self.column_span_default,
            'sizing_mode': self.sizing_mode
        })
        return res


@dataclass
class Stack(LayoutNode):
    """
    Linear vertical or horizontal stack primitive with gap spacing and wrapping.
    """
    node_type: str = "stack"
    orientation: str = "vertical"           # 'vertical', 'horizontal'
    gap_px: int = 16
    wrap_enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Stack':
        base = LayoutNode._parse_base_node(data)
        return cls(
            node_id=base.node_id,
            node_type="stack",
            name=base.name,
            region_id=base.region_id,
            component_id=base.component_id,
            constraints=base.constraints,
            alignment=base.alignment,
            behaviors=base.behaviors,
            children=base.children,
            metadata=base.metadata,
            orientation=data.get('orientation', 'vertical'),
            gap_px=int(data.get('gap_px', 16)),
            wrap_enabled=bool(data.get('wrap_enabled', True))
        )

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            'orientation': self.orientation,
            'gap_px': self.gap_px,
            'wrap_enabled': self.wrap_enabled
        })
        return res


@dataclass
class Split(LayoutNode):
    """
    Proportional multi-pane split layout primitive (e.g., '50-50', '60-40', 'sidebar-main').
    """
    node_type: str = "split"
    split_ratio: str = "50-50"              # '50-50', '60-40', '40-60', '33-67', '67-33', 'sidebar-main', 'main-sidebar'
    divider_enabled: bool = False
    stack_on_mobile: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Split':
        base = LayoutNode._parse_base_node(data)
        return cls(
            node_id=base.node_id,
            node_type="split",
            name=base.name,
            region_id=base.region_id,
            component_id=base.component_id,
            constraints=base.constraints,
            alignment=base.alignment,
            behaviors=base.behaviors,
            children=base.children,
            metadata=base.metadata,
            split_ratio=data.get('split_ratio', '50-50'),
            divider_enabled=bool(data.get('divider_enabled', False)),
            stack_on_mobile=bool(data.get('stack_on_mobile', True))
        )

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            'split_ratio': self.split_ratio,
            'divider_enabled': self.divider_enabled,
            'stack_on_mobile': self.stack_on_mobile
        })
        return res


@dataclass
class Masonry(LayoutNode):
    """
    Dynamic multi-column staggered packing layout primitive for variable-height items.
    """
    node_type: str = "masonry"
    columns_per_breakpoint: Dict[str, int] = field(default_factory=lambda: {"mobile": 1, "tablet": 2, "desktop": 3, "wide_desktop": 4})
    gutter_px: int = 16

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Masonry':
        base = LayoutNode._parse_base_node(data)
        return cls(
            node_id=base.node_id,
            node_type="masonry",
            name=base.name,
            region_id=base.region_id,
            component_id=base.component_id,
            constraints=base.constraints,
            alignment=base.alignment,
            behaviors=base.behaviors,
            children=base.children,
            metadata=base.metadata,
            columns_per_breakpoint=data.get('columns_per_breakpoint', {"mobile": 1, "tablet": 2, "desktop": 3, "wide_desktop": 4}),
            gutter_px=int(data.get('gutter_px', 16))
        )

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            'columns_per_breakpoint': self.columns_per_breakpoint,
            'gutter_px': self.gutter_px
        })
        return res


@dataclass
class Overlay(LayoutNode):
    """
    Absolute or floating positioning layer for modals, drawers, tooltips, floating navbars, or badges.
    """
    node_type: str = "overlay"
    overlay_type: str = "modal"             # 'modal', 'drawer', 'floating_nav', 'tooltip', 'badge'
    anchor_point: str = "center"            # 'center', 'top-right', 'bottom-left', 'bottom', 'top'
    backdrop_dim: bool = True
    z_index: int = 1000

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Overlay':
        base = LayoutNode._parse_base_node(data)
        return cls(
            node_id=base.node_id,
            node_type="overlay",
            name=base.name,
            region_id=base.region_id,
            component_id=base.component_id,
            constraints=base.constraints,
            alignment=base.alignment,
            behaviors=base.behaviors,
            children=base.children,
            metadata=base.metadata,
            overlay_type=data.get('overlay_type', 'modal'),
            anchor_point=data.get('anchor_point', 'center'),
            backdrop_dim=bool(data.get('backdrop_dim', True)),
            z_index=int(data.get('z_index', 1000))
        )

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            'overlay_type': self.overlay_type,
            'anchor_point': self.anchor_point,
            'backdrop_dim': self.backdrop_dim,
            'z_index': self.z_index
        })
        return res


# =========================================================================
# 3. LAYOUT TREE & CATALOG DEFINITIONS
# =========================================================================

@dataclass
class LayoutTree:
    """
    Complete hierarchical layout representation of a page across responsive viewports.
    """
    tree_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_name: str = "Unnamed Project Layout"
    viewport: str = "desktop"               # 'mobile', 'tablet', 'desktop', 'wide_desktop'
    root_node: Optional[LayoutNode] = None
    section_flow: Optional[SectionFlow] = None
    regions: Dict[str, ContentRegion] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutTree':
        if not data:
            return cls()
        root_data = data.get('root_node')
        flow_data = data.get('section_flow')
        regions_data = data.get('regions', {})
        regions = {k: ContentRegion.from_dict(v) if isinstance(v, dict) else v for k, v in regions_data.items()}

        return cls(
            tree_id=data.get('tree_id', str(uuid.uuid4())),
            project_name=data.get('project_name', 'Unnamed Project Layout'),
            viewport=data.get('viewport', 'desktop'),
            root_node=LayoutNode.from_dict(root_data) if isinstance(root_data, dict) else root_data,
            section_flow=SectionFlow.from_dict(flow_data) if isinstance(flow_data, dict) else flow_data,
            regions=regions,
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tree_id': self.tree_id,
            'project_name': self.project_name,
            'viewport': self.viewport,
            'root_node': self.root_node.to_dict() if self.root_node and hasattr(self.root_node, 'to_dict') else None,
            'section_flow': self.section_flow.to_dict() if self.section_flow and hasattr(self.section_flow, 'to_dict') else None,
            'regions': {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.regions.items()},
            'metadata': self.metadata
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class LayoutDefinition:
    """
    Specification of a reusable, intelligent layout archetype in the catalog.
    """
    definition_id: str = "layout_landing_standard"
    name: str = "Standard Landing Page Layout"
    category: str = "landing"               # e.g., 'landing', 'dashboard', 'ecommerce', 'blog', 'authentication', 'forms', 'contact', 'pricing', 'faq'
    description: str = "High-conversion landing page layout with hero, feature grid, and social proof stack."
    supported_viewports: List[str] = field(default_factory=lambda: ["mobile", "tablet", "desktop", "wide_desktop"])
    default_tree: Optional[LayoutTree] = None
    responsive_trees: Dict[str, LayoutTree] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutDefinition':
        if not data:
            return cls()
        def_tree_data = data.get('default_tree')
        resp_data = data.get('responsive_trees', {})
        resp_trees = {k: LayoutTree.from_dict(v) if isinstance(v, dict) else v for k, v in resp_data.items()}

        return cls(
            definition_id=data.get('definition_id', 'layout_landing_standard'),
            name=data.get('name', 'Standard Landing Page Layout'),
            category=data.get('category', 'landing'),
            description=data.get('description', ''),
            supported_viewports=list(data.get('supported_viewports', ["mobile", "tablet", "desktop", "wide_desktop"])),
            default_tree=LayoutTree.from_dict(def_tree_data) if isinstance(def_tree_data, dict) else def_tree_data,
            responsive_trees=resp_trees,
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'definition_id': self.definition_id,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'supported_viewports': self.supported_viewports,
            'default_tree': self.default_tree.to_dict() if self.default_tree and hasattr(self.default_tree, 'to_dict') else None,
            'responsive_trees': {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.responsive_trees.items()},
            'metadata': self.metadata
        }


class LayoutCatalog:
    """
    Authoritative repository of out-of-the-box reusable layout definitions for Nexora Studio.
    Contains 9 core layout archetypes.
    """
    def __init__(self):
        self.definitions: Dict[str, LayoutDefinition] = {}
        self._populate_standard_catalog()

    def get_definition(self, definition_id: str) -> Optional[LayoutDefinition]:
        return self.definitions.get(definition_id)

    def get_by_category(self, category: str) -> List[LayoutDefinition]:
        cat_lower = category.lower()
        return [d for d in self.definitions.values() if d.category.lower() == cat_lower or cat_lower in d.name.lower()]

    def get_all(self) -> Dict[str, LayoutDefinition]:
        return self.definitions

    def _populate_standard_catalog(self):
        # 1. Landing Standard
        self.definitions["layout_landing_standard"] = LayoutDefinition(
            definition_id="layout_landing_standard",
            name="Standard Landing Page Layout",
            category="landing",
            description="High-conversion landing page with vertical stack flow, hero region, features grid, and footer sitemap.",
            default_tree=LayoutTree(
                tree_id="tree_landing_def",
                project_name="Standard Landing Page",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_landing", transition_type="stack_vertical", section_spacing_px=80),
                regions={
                    "header_region": ContentRegion("header_region", "Header Navigation", priority=1, allowed_component_categories=["Navbar"]),
                    "hero_main": ContentRegion("hero_main", "Hero Showcase", priority=1, allowed_component_categories=["Hero"]),
                    "features_section": ContentRegion("features_section", "Value Propositions", priority=2, allowed_component_categories=["Features", "Pricing", "Testimonials"]),
                    "footer_region": ContentRegion("footer_region", "Sitemap Footer", priority=3, allowed_component_categories=["Footer"])
                },
                root_node=Stack(
                    node_id="root_landing_stack",
                    name="Landing Main Stack",
                    orientation="vertical",
                    gap_px=80,
                    children=[
                        Container(node_id="c_head", name="Header Container", region_id="header_region", padding_px=0, margin_px=0),
                        Container(node_id="c_hero", name="Hero Container", region_id="hero_main", padding_px=40, margin_px=0),
                        Grid(node_id="g_feat", name="Features Grid", region_id="features_section", columns=12, gutter_px=32),
                        Container(node_id="c_foot", name="Footer Container", region_id="footer_region", padding_px=48, margin_px=0)
                    ]
                )
            )
        )

        # 2. SaaS Dashboard
        self.definitions["layout_saas_dashboard"] = LayoutDefinition(
            definition_id="layout_saas_dashboard",
            name="SaaS Analytics Dashboard Layout",
            category="dashboard",
            description="Multi-pane enterprise layout with left collapsible sidebar navigation and main KPI metric grid.",
            default_tree=LayoutTree(
                tree_id="tree_dash_def",
                project_name="SaaS Dashboard",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_dash", transition_type="stack_vertical", section_spacing_px=24),
                regions={
                    "sidebar_left": ContentRegion("sidebar_left", "Sidebar Navigation", priority=1, allowed_component_categories=["Navbar"]),
                    "kpi_main": ContentRegion("kpi_main", "Analytics KPI Area", priority=1, allowed_component_categories=["Dashboard", "Features"])
                },
                root_node=Split(
                    node_id="root_dash_split",
                    name="Dashboard Sidebar Split",
                    split_ratio="sidebar-main", # e.g. 20-80
                    divider_enabled=True,
                    stack_on_mobile=True,
                    children=[
                        Container(node_id="c_sidebar", name="Sidebar Panel", region_id="sidebar_left", padding_px=24, behaviors=[LayoutBehavior("pinned", "scroll")]),
                        Grid(node_id="g_kpi", name="KPI Metric Grid", region_id="kpi_main", columns=12, gutter_px=24)
                    ]
                )
            )
        )

        # 3. Ecommerce Catalog
        self.definitions["layout_ecom_catalog"] = LayoutDefinition(
            definition_id="layout_ecom_catalog",
            name="Ecommerce Product Catalog Layout",
            category="ecommerce",
            description="Product showcase layout with category filter sidebar and multi-column masonry/grid catalog.",
            default_tree=LayoutTree(
                tree_id="tree_ecom_def",
                project_name="Ecommerce Catalog",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_ecom", transition_type="stack_vertical", section_spacing_px=48),
                regions={
                    "filter_sidebar": ContentRegion("filter_sidebar", "Product Filters", priority=2, allowed_component_categories=["Forms"]),
                    "product_grid": ContentRegion("product_grid", "Product Showcase", priority=1, allowed_component_categories=["Ecommerce"])
                },
                root_node=Split(
                    node_id="root_ecom_split",
                    name="Catalog Filter Split",
                    split_ratio="25-75",
                    divider_enabled=True,
                    children=[
                        Container(node_id="c_filters", name="Filter Container", region_id="filter_sidebar", padding_px=24),
                        Masonry(node_id="m_products", name="Product Masonry Grid", region_id="product_grid", columns_per_breakpoint={"mobile": 1, "tablet": 2, "desktop": 3, "wide_desktop": 4}, gutter_px=24)
                    ]
                )
            )
        )

        # 4. Blog Editorial
        self.definitions["layout_blog_editorial"] = LayoutDefinition(
            definition_id="layout_blog_editorial",
            name="Editorial Blog & News Layout",
            category="blog",
            description="Article showcase layout with prominent featured article hero and masonry blog article cards.",
            default_tree=LayoutTree(
                tree_id="tree_blog_def",
                project_name="Blog Editorial",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_blog", transition_type="stack_vertical", section_spacing_px=64),
                regions={
                    "featured_post": ContentRegion("featured_post", "Featured Headline", priority=1, allowed_component_categories=["Blog", "Hero"]),
                    "article_masonry": ContentRegion("article_masonry", "Article Feed", priority=2, allowed_component_categories=["Blog", "Gallery"])
                },
                root_node=Stack(
                    node_id="root_blog_stack",
                    name="Editorial Stack",
                    orientation="vertical",
                    gap_px=64,
                    children=[
                        Container(node_id="c_feat_post", name="Featured Post Container", region_id="featured_post", padding_px=32),
                        Masonry(node_id="m_articles", name="Articles Masonry", region_id="article_masonry", columns_per_breakpoint={"mobile": 1, "tablet": 2, "desktop": 3, "wide_desktop": 3}, gutter_px=32)
                    ]
                )
            )
        )

        # 5. Authentication Portal
        self.definitions["layout_auth_portal"] = LayoutDefinition(
            definition_id="layout_auth_portal",
            name="Secure Authentication Portal Layout",
            category="authentication",
            description="Split-screen authentication portal with branding/promotion on left and login/SSO credentials on right.",
            default_tree=LayoutTree(
                tree_id="tree_auth_def",
                project_name="Auth Portal",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_auth", transition_type="split_transition", section_spacing_px=0),
                regions={
                    "brand_promo": ContentRegion("brand_promo", "Brand Promotional Area", priority=2, allowed_component_categories=["Hero", "Features"]),
                    "auth_form": ContentRegion("auth_form", "Authentication Form Area", priority=1, allowed_component_categories=["Authentication"])
                },
                root_node=Split(
                    node_id="root_auth_split",
                    name="Auth Brand Split",
                    split_ratio="50-50",
                    divider_enabled=False,
                    stack_on_mobile=True,
                    children=[
                        Container(node_id="c_brand", name="Brand Container", region_id="brand_promo", padding_px=48, background_style="highlight"),
                        Container(node_id="c_auth", name="Auth Form Container", region_id="auth_form", padding_px=48, alignment=AlignmentRule("center", "middle"))
                    ]
                )
            )
        )

        # 6. Contact Split
        self.definitions["layout_contact_split"] = LayoutDefinition(
            definition_id="layout_contact_split",
            name="Split Inquiry & Location Contact Layout",
            category="contact",
            description="Two-pane contact layout with inquiry submission form on one side and interactive location details on the other.",
            default_tree=LayoutTree(
                tree_id="tree_contact_def",
                project_name="Contact Split",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_contact", transition_type="stack_vertical", section_spacing_px=48),
                regions={
                    "form_region": ContentRegion("form_region", "Inquiry Submission Area", priority=1, allowed_component_categories=["Contact", "Forms"]),
                    "info_region": ContentRegion("info_region", "Office & Location Details", priority=2, allowed_component_categories=["Contact", "Features"])
                },
                root_node=Split(
                    node_id="root_contact_split",
                    name="Contact Split Area",
                    split_ratio="60-40",
                    divider_enabled=True,
                    children=[
                        Container(node_id="c_form", name="Inquiry Form Container", region_id="form_region", padding_px=32),
                        Container(node_id="c_info", name="Location Details Container", region_id="info_region", padding_px=32, background_style="subtle")
                    ]
                )
            )
        )

        # 7. Pricing Comparison
        self.definitions["layout_pricing_comparison"] = LayoutDefinition(
            definition_id="layout_pricing_comparison",
            name="Tiered Pricing Comparison Layout",
            category="pricing",
            description="Centered pricing showcase with billing toggle, 3-tier pricing cards grid, and FAQ accordion helper.",
            default_tree=LayoutTree(
                tree_id="tree_pricing_def",
                project_name="Pricing Comparison",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_pricing", transition_type="stack_vertical", section_spacing_px=64),
                regions={
                    "pricing_tiers": ContentRegion("pricing_tiers", "Tier Comparison Cards", priority=1, allowed_component_categories=["Pricing"]),
                    "pricing_faq": ContentRegion("pricing_faq", "Billing FAQ Helper", priority=2, allowed_component_categories=["FAQ"])
                },
                root_node=Stack(
                    node_id="root_pricing_stack",
                    name="Pricing Showcase Stack",
                    orientation="vertical",
                    gap_px=64,
                    children=[
                        Grid(node_id="g_tiers", name="Pricing Tiers Grid", region_id="pricing_tiers", columns=12, gutter_px=24),
                        Container(node_id="c_faq", name="FAQ Helper Container", region_id="pricing_faq", padding_px=32)
                    ]
                )
            )
        )

        # 8. FAQ Accordion
        self.definitions["layout_faq_accordion"] = LayoutDefinition(
            definition_id="layout_faq_accordion",
            name="Categorized FAQ Accordion Layout",
            category="faq",
            description="Support layout featuring category tabs and interactive question-and-answer accordion lists.",
            default_tree=LayoutTree(
                tree_id="tree_faq_def",
                project_name="FAQ Accordion",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_faq_sec", transition_type="stack_vertical", section_spacing_px=40),
                regions={
                    "faq_main": ContentRegion("faq_main", "Accordion Question Area", priority=1, allowed_component_categories=["FAQ", "Contact"])
                },
                root_node=Container(
                    node_id="root_faq_container",
                    name="FAQ Main Container",
                    region_id="faq_main",
                    padding_px=48,
                    alignment=AlignmentRule("center", "top"),
                    constraints=ConstraintRule(max_width_px=960, overflow_behavior="wrap")
                )
            )
        )

        # 9. Forms Wizard
        self.definitions["layout_forms_wizard"] = LayoutDefinition(
            definition_id="layout_forms_wizard",
            name="Multi-Step Guided Wizard Form Layout",
            category="forms",
            description="Guided step-by-step form workflow with top progress indicator and sidebar helpful tips.",
            default_tree=LayoutTree(
                tree_id="tree_forms_def",
                project_name="Forms Wizard",
                viewport="desktop",
                section_flow=SectionFlow(flow_id="flow_forms", transition_type="split_transition", section_spacing_px=32),
                regions={
                    "wizard_steps": ContentRegion("wizard_steps", "Step Form Workflow", priority=1, allowed_component_categories=["Forms", "Authentication"]),
                    "wizard_tips": ContentRegion("wizard_tips", "Helper Tips & Guidance", priority=2, allowed_component_categories=["FAQ", "Features"])
                },
                root_node=Split(
                    node_id="root_wizard_split",
                    name="Wizard Workflow Split",
                    split_ratio="70-30",
                    divider_enabled=True,
                    children=[
                        Container(node_id="c_wizard", name="Wizard Step Container", region_id="wizard_steps", padding_px=40),
                        Container(node_id="c_tips", name="Helper Tips Sidebar", region_id="wizard_tips", padding_px=24, background_style="subtle")
                    ]
                )
            )
        )
