# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Union
import json
import uuid

@dataclass
class ResponsiveBreakpoint:
    """Defines screen width thresholds and responsive layout parameters."""
    id: str
    label: str  # e.g., 'mobile', 'tablet', 'desktop'
    min_width_px: int
    max_width_px: Optional[int] = None
    columns: int = 12
    margin_px: int = 24

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResponsiveBreakpoint':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ColorToken:
    """Defines a single color token with contrast and accessibility grades."""
    id: str
    name: str
    hex_value: str
    role: str = 'primary'  # e.g., 'primary', 'secondary', 'neutral', 'surface', 'error'
    contrast_ratio_on_background: float = 4.5
    wcag_grade: str = 'AA'  # e.g., 'AA', 'AAA', 'Fail'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorToken':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ColorPalette:
    """Aggregates a collection of color tokens for a design project."""
    id: str
    name: str
    tokens: List[ColorToken] = field(default_factory=list)
    background_token_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorPalette':
        tokens_data = data.get('tokens', [])
        tokens = [ColorToken.from_dict(t) if isinstance(t, dict) else t for t in tokens_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Default Palette'),
            tokens=tokens,
            background_token_id=data.get('background_token_id')
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['tokens'] = [t.to_dict() if hasattr(t, 'to_dict') else t for t in self.tokens]
        return res


@dataclass
class TypographyToken:
    """Defines typography font styling tokens."""
    id: str
    name: str  # e.g., 'heading-1', 'body-regular', 'caption'
    font_family: str
    font_size_px: int
    font_weight: int = 400
    line_height_ratio: float = 1.5
    letter_spacing_em: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TypographyToken':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TypographyScale:
    """Aggregates typography styling tokens into a cohesive scale."""
    id: str
    name: str
    tokens: List[TypographyToken] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TypographyScale':
        tokens_data = data.get('tokens', [])
        tokens = [TypographyToken.from_dict(t) if isinstance(t, dict) else t for t in tokens_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Default Scale'),
            tokens=tokens
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['tokens'] = [t.to_dict() if hasattr(t, 'to_dict') else t for t in self.tokens]
        return res


@dataclass
class DesignTokenSet:
    """The complete design token repository covering colors, typography, spacing, and elevation."""
    id: str
    name: str
    color_palette: Optional[ColorPalette] = None
    typography_scale: Optional[TypographyScale] = None
    spacing_scale_px: List[int] = field(default_factory=lambda: [4, 8, 12, 16, 24, 32, 48, 64, 96])
    elevation_levels: List[Dict[str, Any]] = field(default_factory=list)
    custom_tokens: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DesignTokenSet':
        palette_data = data.get('color_palette')
        typo_data = data.get('typography_scale')
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Default Token Set'),
            color_palette=ColorPalette.from_dict(palette_data) if isinstance(palette_data, dict) else palette_data,
            typography_scale=TypographyScale.from_dict(typo_data) if isinstance(typo_data, dict) else typo_data,
            spacing_scale_px=data.get('spacing_scale_px', [4, 8, 12, 16, 24, 32, 48, 64, 96]),
            elevation_levels=data.get('elevation_levels', []),
            custom_tokens=data.get('custom_tokens', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.color_palette and hasattr(self.color_palette, 'to_dict'):
            res['color_palette'] = self.color_palette.to_dict()
        if self.typography_scale and hasattr(self.typography_scale, 'to_dict'):
            res['typography_scale'] = self.typography_scale.to_dict()
        return res


@dataclass
class AssetPlaceholder:
    """Describes required media assets and image placeholders."""
    id: str
    name: str
    asset_type: str = 'image'  # e.g., 'image', 'video', 'icon', 'illustration'
    width_px: int = 800
    height_px: int = 600
    alt_text: str = ''
    aria_role: str = 'img'
    aspect_ratio: str = '4:3'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetPlaceholder':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnimationRule:
    """Describes micro-animations, motion behaviors, and transition timing."""
    id: str
    name: str
    trigger: str = 'on-scroll'  # e.g., 'on-hover', 'on-scroll', 'on-mount', 'on-click'
    duration_ms: int = 300
    easing: str = 'ease-out'
    target_property: str = 'opacity'
    intensity: str = 'subtle'  # e.g., 'none', 'subtle', 'expressive'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnimationRule':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NavigationNode:
    """Recursive navigation tree node describing site structure and routing."""
    id: str
    label: str
    target_slug_or_id: str
    is_external: bool = False
    children: List['NavigationNode'] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NavigationNode':
        children_data = data.get('children', [])
        children = [NavigationNode.from_dict(c) if isinstance(c, dict) else c for c in children_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            label=data.get('label', 'Link'),
            target_slug_or_id=data.get('target_slug_or_id', '/'),
            is_external=data.get('is_external', False),
            children=children
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['children'] = [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.children]
        return res


@dataclass
class NavigationTree:
    """Root aggregate for navigation structure."""
    id: str
    name: str
    root_nodes: List[NavigationNode] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NavigationTree':
        nodes_data = data.get('root_nodes', [])
        nodes = [NavigationNode.from_dict(n) if isinstance(n, dict) else n for n in nodes_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Main Navigation'),
            root_nodes=nodes
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['root_nodes'] = [n.to_dict() if hasattr(n, 'to_dict') else n for n in self.root_nodes]
        return res


@dataclass
class ComponentBlueprint:
    """Describes reusable design components, layout primitives, and token associations."""
    id: str
    name: str
    category: str = 'card'  # e.g., 'card', 'button', 'navbar', 'hero-content', 'grid-item'
    layout_type: str = 'flex-column'  # e.g., 'flex-row', 'flex-column', 'grid', 'absolute'
    alignment: str = 'start'  # e.g., 'start', 'center', 'end', 'space-between'
    width_mode: str = 'fill'  # e.g., 'fill', 'hug', 'fixed'
    height_mode: str = 'hug'
    definition_id: Optional[str] = None  # Reference to Design System ComponentDefinition.id
    variant: str = 'default'  # Reference to ComponentVariant.name
    token_references: List[str] = field(default_factory=list)  # Referenced ColorToken/TypographyToken IDs
    asset_placeholders: List[str] = field(default_factory=list)  # Referenced AssetPlaceholder IDs
    animation_rule_ids: List[str] = field(default_factory=list)  # Referenced AnimationRule IDs
    children: List['ComponentBlueprint'] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentBlueprint':
        children_data = data.get('children', [])
        children = [ComponentBlueprint.from_dict(c) if isinstance(c, dict) else c for c in children_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Component'),
            category=data.get('category', 'card'),
            layout_type=data.get('layout_type', 'flex-column'),
            alignment=data.get('alignment', 'start'),
            width_mode=data.get('width_mode', 'fill'),
            height_mode=data.get('height_mode', 'hug'),
            definition_id=data.get('definition_id'),
            variant=data.get('variant', 'default'),
            token_references=data.get('token_references', []),
            asset_placeholders=data.get('asset_placeholders', []),
            animation_rule_ids=data.get('animation_rule_ids', []),
            children=children
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['children'] = [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.children]
        return res


@dataclass
class SectionBlueprint:
    """Describes page sections containing layout containers and components."""
    id: str
    name: str
    section_type: str = 'hero'  # e.g., 'hero', 'features', 'testimonials', 'footer', 'cta'
    layout_container: str = 'grid-12'  # e.g., 'grid-12', 'flex-center', 'sidebar-layout'
    background_token_id: Optional[str] = None
    components: List[ComponentBlueprint] = field(default_factory=list)
    min_height_px: Optional[int] = None
    layout_definition_id: Optional[str] = None  # Reference to LayoutDefinition.definition_id (Phase 11E)
    layout_tree: Optional[Dict[str, Any]] = None  # Serialized LayoutTree (Phase 11E)
    responsive_layout_trees: Optional[Dict[str, Dict[str, Any]]] = None  # Viewport adapted trees (Phase 11E)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SectionBlueprint':
        comps_data = data.get('components', [])
        comps = [ComponentBlueprint.from_dict(c) if isinstance(c, dict) else c for c in comps_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Section'),
            section_type=data.get('section_type', 'hero'),
            layout_container=data.get('layout_container', 'grid-12'),
            background_token_id=data.get('background_token_id'),
            components=comps,
            min_height_px=data.get('min_height_px'),
            layout_definition_id=data.get('layout_definition_id'),
            layout_tree=data.get('layout_tree'),
            responsive_layout_trees=data.get('responsive_layout_trees')
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['components'] = [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.components]
        return res


@dataclass
class PageBlueprint:
    """Describes site pages, SEO metadata, and ordered sections."""
    id: str
    name: str
    slug: str
    seo_title: str = ''
    seo_description: str = ''
    sections: List[SectionBlueprint] = field(default_factory=list)
    layout_definition_id: Optional[str] = None  # Reference to LayoutDefinition.definition_id (Phase 11E)
    layout_tree: Optional[Dict[str, Any]] = None  # Serialized LayoutTree (Phase 11E)
    responsive_layout_trees: Optional[Dict[str, Dict[str, Any]]] = None  # Viewport adapted trees (Phase 11E)
    archetype: str = 'landing'  # e.g., 'landing', 'saas_dashboard', 'blog', 'ecommerce', 'contact', 'auth'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PageBlueprint':
        secs_data = data.get('sections', [])
        secs = [SectionBlueprint.from_dict(s) if isinstance(s, dict) else s for s in secs_data]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Home'),
            slug=data.get('slug', '/'),
            seo_title=data.get('seo_title', ''),
            seo_description=data.get('seo_description', ''),
            sections=secs,
            layout_definition_id=data.get('layout_definition_id'),
            layout_tree=data.get('layout_tree'),
            responsive_layout_trees=data.get('responsive_layout_trees'),
            archetype=data.get('archetype', 'landing')
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['sections'] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.sections]
        return res


@dataclass
class ExperienceBlueprint:
    """
    First-class domain object defining user experience, interaction dynamics, and performance budgets.
    Provider-neutral and rendering-neutral: describes design intent without referencing any rendering technology.
    """
    visual_style: str = 'modern'  # e.g., 'modern', 'minimalist', 'glassmorphism', 'corporate', 'editorial'
    interaction_style: str = 'dynamic'  # e.g., 'subtle', 'dynamic', 'playful', 'static'
    animation_intensity: str = 'subtle'  # e.g., 'none', 'subtle', 'expressive'
    scrolling_behavior: str = 'smooth'  # e.g., 'standard', 'smooth', 'snapping', 'infinite'
    section_transitions: str = 'fade'  # e.g., 'fade', 'slide', 'seamless', 'none'
    parallax_level: str = 'none'  # e.g., 'none', 'low', 'medium', 'high'
    cursor_behavior: str = 'default'  # e.g., 'default', 'custom-follower', 'interactive', 'magnetic'
    rendering_preference: str = '2D'  # e.g., '2D', '3D', 'Hybrid'
    performance_budget: Dict[str, Any] = field(default_factory=lambda: {
        'max_asset_payload_kb': 2048,
        'target_fps': 60,
        'max_animation_simultaneous': 5
    })
    accessibility_preferences: Dict[str, Any] = field(default_factory=lambda: {
        'prefers_reduced_motion': False,
        'wcag_target': 'AA',
        'screen_reader_optimized': True
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExperienceBlueprint':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DesignBlueprint:
    """
    Root Aggregate Domain Model for Nexora Studio Design Blueprints.
    
    Acts as the single source of truth between Builder Sessions and Design Orchestrators.
    Completely provider-agnostic and rendering-agnostic.
    """
    blueprint_id: str
    project_name: str
    version: str = '1.0.0'
    pages: List[PageBlueprint] = field(default_factory=list)
    token_set: Optional[DesignTokenSet] = None
    navigation: Optional[NavigationTree] = None
    breakpoints: List[ResponsiveBreakpoint] = field(default_factory=list)
    experience: Optional[ExperienceBlueprint] = None
    placeholders: Dict[str, AssetPlaceholder] = field(default_factory=dict)
    animations: Dict[str, AnimationRule] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DesignBlueprint':
        pages_data = data.get('pages', [])
        pages = [PageBlueprint.from_dict(p) if isinstance(p, dict) else p for p in pages_data]
        
        token_data = data.get('token_set')
        token_set = DesignTokenSet.from_dict(token_data) if isinstance(token_data, dict) else token_data
        
        nav_data = data.get('navigation')
        navigation = NavigationTree.from_dict(nav_data) if isinstance(nav_data, dict) else nav_data
        
        bps_data = data.get('breakpoints', [])
        breakpoints = [ResponsiveBreakpoint.from_dict(b) if isinstance(b, dict) else b for b in bps_data]
        
        exp_data = data.get('experience')
        experience = ExperienceBlueprint.from_dict(exp_data) if isinstance(exp_data, dict) else exp_data
        
        phs_data = data.get('placeholders', {})
        placeholders = {k: AssetPlaceholder.from_dict(v) if isinstance(v, dict) else v for k, v in phs_data.items()}
        
        anims_data = data.get('animations', {})
        animations = {k: AnimationRule.from_dict(v) if isinstance(v, dict) else v for k, v in anims_data.items()}
        
        return cls(
            blueprint_id=data.get('blueprint_id', str(uuid.uuid4())),
            project_name=data.get('project_name', 'Unnamed Project'),
            version=data.get('version', '1.0.0'),
            pages=pages,
            token_set=token_set,
            navigation=navigation,
            breakpoints=breakpoints,
            experience=experience or ExperienceBlueprint(),
            placeholders=placeholders,
            animations=animations,
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        res = {
            'blueprint_id': self.blueprint_id,
            'project_name': self.project_name,
            'version': self.version,
            'pages': [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.pages],
            'token_set': self.token_set.to_dict() if self.token_set and hasattr(self.token_set, 'to_dict') else None,
            'navigation': self.navigation.to_dict() if self.navigation and hasattr(self.navigation, 'to_dict') else None,
            'breakpoints': [b.to_dict() if hasattr(b, 'to_dict') else b for b in self.breakpoints],
            'experience': self.experience.to_dict() if self.experience and hasattr(self.experience, 'to_dict') else None,
            'placeholders': {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.placeholders.items()},
            'animations': {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.animations.items()},
            'metadata': self.metadata
        }
        return res

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> 'DesignBlueprint':
        data = json.loads(json_str)
        return cls.from_dict(data)
