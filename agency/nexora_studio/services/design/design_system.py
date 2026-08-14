# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Union
import json
import uuid

@dataclass
class SpacingScale:
    """Enforces consistent margin, padding, and gap spacing increments across designs."""
    values_px: List[int] = field(default_factory=lambda: [0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128, 160])
    default_gap_px: int = 16
    default_padding_px: int = 24

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpacingScale':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GridSystem:
    """Defines responsive grid columns, gutters, margins, and max container widths."""
    columns: int = 12
    gutter_px: int = 24
    margin_px: int = 32
    max_container_width_px: int = 1280

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridSystem':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IconSystem:
    """Defines icon sizing standards, stroke widths, and accessibility requirements."""
    allowed_sizes_px: List[int] = field(default_factory=lambda: [16, 20, 24, 32, 48])
    default_stroke_width: float = 1.5
    library_name: str = 'lucide-standard'
    require_aria_label: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IconSystem':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThemeSystem:
    """Defines light/dark mode support, surface elevation shadows, and brand palettes."""
    supports_dark_mode: bool = True
    default_theme_id: str = 'light'
    available_themes: List[str] = field(default_factory=lambda: ['light', 'dark', 'system', 'high-contrast'])
    elevation_shadows: Dict[str, str] = field(default_factory=lambda: {
        'sm': '0 1px 2px rgba(0,0,0,0.05)',
        'md': '0 4px 6px rgba(0,0,0,0.1)',
        'lg': '0 10px 15px rgba(0,0,0,0.1)',
        'xl': '0 20px 25px rgba(0,0,0,0.15)'
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThemeSystem':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StateSystem:
    """Defines interactive component state behaviors and styling rules."""
    supported_states: List[str] = field(default_factory=lambda: ['default', 'hover', 'active', 'focus', 'disabled', 'error', 'loading'])
    focus_ring_token_id: str = 'col_prim'
    disabled_opacity: float = 0.5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateSystem':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LayoutRules:
    """Enforces valid layout primitives, alignment options, and sizing modes."""
    allowed_layout_types: List[str] = field(default_factory=lambda: ['flex-row', 'flex-column', 'grid', 'absolute', 'stack'])
    allowed_alignments: List[str] = field(default_factory=lambda: ['start', 'center', 'end', 'space-between', 'space-around', 'stretch'])
    allowed_width_modes: List[str] = field(default_factory=lambda: ['fill', 'hug', 'fixed'])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutRules':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentVariant:
    """Describes stylistic or structural variations of a component definition."""
    id: str
    name: str  # e.g., 'default', 'centered', 'split-screen', 'outline', 'ghost'
    description: str = ''
    layout_override: Optional[str] = None
    token_overrides: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentVariant':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentCapability:
    """
    Provider-neutral ComponentCapability model.
    Describes what a component supports rather than how it is rendered.
    """
    video_background: bool = False
    three_d_scene: bool = False  # Maps to/from '3d_scene' in dict/JSON
    particles: bool = False
    parallax: bool = False
    animation: bool = True
    localization: bool = True
    dark_mode: bool = True
    ai_content: bool = False
    forms: bool = False
    ecommerce: bool = False
    authentication: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentCapability':
        three_d = data.get('3d_scene', data.get('three_d_scene', False))
        return cls(
            video_background=data.get('video_background', False),
            three_d_scene=three_d,
            particles=data.get('particles', False),
            parallax=data.get('parallax', False),
            animation=data.get('animation', True),
            localization=data.get('localization', True),
            dark_mode=data.get('dark_mode', True),
            ai_content=data.get('ai_content', False),
            forms=data.get('forms', False),
            ecommerce=data.get('ecommerce', False),
            authentication=data.get('authentication', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'video_background': self.video_background,
            '3d_scene': self.three_d_scene,
            'particles': self.particles,
            'parallax': self.parallax,
            'animation': self.animation,
            'localization': self.localization,
            'dark_mode': self.dark_mode,
            'ai_content': self.ai_content,
            'forms': self.forms,
            'ecommerce': self.ecommerce,
            'authentication': self.authentication
        }


@dataclass
class AssetRequirements:
    """
    Provider-neutral AssetRequirements model.
    Describes required and optional media/content assets without referencing rendering technologies.
    """
    required_assets: List[str] = field(default_factory=list)  # e.g., ['image', 'logo', 'generic_3d_asset', 'environment_asset']
    optional_assets: List[str] = field(default_factory=list)  # e.g., ['video', 'audio', 'document', 'illustration', 'icon']
    max_file_size_kb: int = 2048
    allowed_aspect_ratios: List[str] = field(default_factory=lambda: ['16:9', '4:3', '1:1', 'auto'])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetRequirements':
        return cls(
            required_assets=data.get('required_assets', []),
            optional_assets=data.get('optional_assets', []),
            max_file_size_kb=data.get('max_file_size_kb', 2048),
            allowed_aspect_ratios=data.get('allowed_aspect_ratios', ['16:9', '4:3', '1:1', 'auto'])
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentDefinition:
    """
    Core reusable intelligent component definition in the Design System library.
    Exposes metadata, inputs, accessibility rules, responsive behaviors, capabilities, and asset requirements.
    """
    id: str  # e.g., 'lib_hero_standard'
    name: str  # e.g., 'Standard Hero'
    category: str  # e.g., 'Hero', 'Navbar', 'Footer', etc.
    description: str = ''
    tags: List[str] = field(default_factory=list)
    required_inputs: Dict[str, Any] = field(default_factory=dict)
    optional_inputs: Dict[str, Any] = field(default_factory=dict)
    accessibility_requirements: Dict[str, Any] = field(default_factory=dict)
    responsive_rules: Dict[str, Any] = field(default_factory=dict)
    design_constraints: Dict[str, Any] = field(default_factory=dict)
    variants: List[ComponentVariant] = field(default_factory=list)
    capabilities: ComponentCapability = field(default_factory=ComponentCapability)
    asset_requirements: AssetRequirements = field(default_factory=AssetRequirements)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentDefinition':
        variants_data = data.get('variants', [])
        variants = [ComponentVariant.from_dict(v) if isinstance(v, dict) else v for v in variants_data]
        
        cap_data = data.get('capabilities', {})
        capabilities = ComponentCapability.from_dict(cap_data) if isinstance(cap_data, dict) else cap_data
        
        asset_data = data.get('asset_requirements', {})
        asset_requirements = AssetRequirements.from_dict(asset_data) if isinstance(asset_data, dict) else asset_data
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Unnamed Component'),
            category=data.get('category', 'General'),
            description=data.get('description', ''),
            tags=data.get('tags', []),
            required_inputs=data.get('required_inputs', {}),
            optional_inputs=data.get('optional_inputs', {}),
            accessibility_requirements=data.get('accessibility_requirements', {}),
            responsive_rules=data.get('responsive_rules', {}),
            design_constraints=data.get('design_constraints', {}),
            variants=variants,
            capabilities=capabilities,
            asset_requirements=asset_requirements
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['variants'] = [v.to_dict() if hasattr(v, 'to_dict') else v for v in self.variants]
        res['capabilities'] = self.capabilities.to_dict() if hasattr(self.capabilities, 'to_dict') else self.capabilities
        res['asset_requirements'] = self.asset_requirements.to_dict() if hasattr(self.asset_requirements, 'to_dict') else self.asset_requirements
        return res


@dataclass
class ComponentLibrary:
    """Repository aggregate managing standard component definitions and variants."""
    id: str
    name: str = 'Core Component Library'
    definitions: Dict[str, ComponentDefinition] = field(default_factory=dict)  # Keyed by ComponentDefinition.id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentLibrary':
        defs_data = data.get('definitions', {})
        definitions = {k: ComponentDefinition.from_dict(v) if isinstance(v, dict) else v for k, v in defs_data.items()}
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Core Component Library'),
            definitions=definitions
        )

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res['definitions'] = {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.definitions.items()}
        return res


@dataclass
class DesignSystem:
    """
    Root Aggregate Domain Model for Nexora Studio Design Systems.
    Sits between Design Blueprint and rendering providers.
    100% provider-neutral and rendering-neutral.
    """
    system_id: str
    name: str
    version: str = '1.0.0'
    library: ComponentLibrary = field(default_factory=ComponentLibrary)
    spacing_scale: SpacingScale = field(default_factory=SpacingScale)
    grid_system: GridSystem = field(default_factory=GridSystem)
    icon_system: IconSystem = field(default_factory=IconSystem)
    theme_system: ThemeSystem = field(default_factory=ThemeSystem)
    state_system: StateSystem = field(default_factory=StateSystem)
    layout_rules: LayoutRules = field(default_factory=LayoutRules)
    motion_tokens: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DesignSystem':
        lib_data = data.get('library', {})
        library = ComponentLibrary.from_dict(lib_data) if isinstance(lib_data, dict) else lib_data
        
        sp_data = data.get('spacing_scale', {})
        spacing_scale = SpacingScale.from_dict(sp_data) if isinstance(sp_data, dict) else sp_data
        
        grid_data = data.get('grid_system', {})
        grid_system = GridSystem.from_dict(grid_data) if isinstance(grid_data, dict) else grid_data
        
        icon_data = data.get('icon_system', {})
        icon_system = IconSystem.from_dict(icon_data) if isinstance(icon_data, dict) else icon_data
        
        theme_data = data.get('theme_system', {})
        theme_system = ThemeSystem.from_dict(theme_data) if isinstance(theme_data, dict) else theme_data
        
        state_data = data.get('state_system', {})
        state_system = StateSystem.from_dict(state_data) if isinstance(state_data, dict) else state_data
        
        layout_data = data.get('layout_rules', {})
        layout_rules = LayoutRules.from_dict(layout_data) if isinstance(layout_data, dict) else layout_data
        
        return cls(
            system_id=data.get('system_id', str(uuid.uuid4())),
            name=data.get('name', 'Nexora Design System'),
            version=data.get('version', '1.0.0'),
            library=library,
            spacing_scale=spacing_scale,
            grid_system=grid_system,
            icon_system=icon_system,
            theme_system=theme_system,
            state_system=state_system,
            layout_rules=layout_rules,
            motion_tokens=data.get('motion_tokens', {}),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'system_id': self.system_id,
            'name': self.name,
            'version': self.version,
            'library': self.library.to_dict() if hasattr(self.library, 'to_dict') else self.library,
            'spacing_scale': self.spacing_scale.to_dict() if hasattr(self.spacing_scale, 'to_dict') else self.spacing_scale,
            'grid_system': self.grid_system.to_dict() if hasattr(self.grid_system, 'to_dict') else self.grid_system,
            'icon_system': self.icon_system.to_dict() if hasattr(self.icon_system, 'to_dict') else self.icon_system,
            'theme_system': self.theme_system.to_dict() if hasattr(self.theme_system, 'to_dict') else self.theme_system,
            'state_system': self.state_system.to_dict() if hasattr(self.state_system, 'to_dict') else self.state_system,
            'layout_rules': self.layout_rules.to_dict() if hasattr(self.layout_rules, 'to_dict') else self.layout_rules,
            'motion_tokens': self.motion_tokens,
            'metadata': self.metadata
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> 'DesignSystem':
        data = json.loads(json_str)
        return cls.from_dict(data)
