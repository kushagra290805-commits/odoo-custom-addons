import uuid
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class RawRequirement:
    intent: str
    constraints: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DesignBlueprint:
    language: str = "minimal"
    color_system: Dict[str, str] = field(default_factory=dict)
    typography: Dict[str, str] = field(default_factory=dict)

@dataclass
class LayoutBlueprint:
    strategy: str = "fluid"
    hierarchy: List[str] = field(default_factory=list)

@dataclass
class ComponentBlueprint:
    abstract_components: List[str] = field(default_factory=list)
    
@dataclass
class AnimationBlueprint:
    strategy: str = "none"
    abstract_requirements: List[str] = field(default_factory=list)

@dataclass
class RenderingBlueprint:
    strategy: str = "none"  # none, css_3d, canvas, webgl, immersive
    budget_polygon_count: int = 0

@dataclass
class PerformanceBlueprint:
    max_bundle_size_kb: int = 200
    max_texture_budget_mb: int = 0
    max_animation_budget_ms: int = 16
    core_web_vitals_lcp_ms: int = 2500

@dataclass
class AccessibilityBlueprint:
    wcag_level: str = "AA"
    required_features: List[str] = field(default_factory=list)

@dataclass
class ResponsiveBlueprint:
    breakpoints: List[str] = field(default_factory=lambda: ["mobile", "tablet", "desktop"])
    mobile_first: bool = True

@dataclass
class SEOBlueprint:
    semantic_html_required: bool = True
    meta_tags: List[str] = field(default_factory=list)

@dataclass
class TechnologyBlueprint:
    allowed_stacks: List[str] = field(default_factory=list)
    disallowed_stacks: List[str] = field(default_factory=list)

@dataclass
class WebsiteBlueprint:
    blueprint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    schema_version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    
    intent: str = ""
    
    design: DesignBlueprint = field(default_factory=DesignBlueprint)
    layout: LayoutBlueprint = field(default_factory=LayoutBlueprint)
    component: ComponentBlueprint = field(default_factory=ComponentBlueprint)
    animation: AnimationBlueprint = field(default_factory=AnimationBlueprint)
    rendering: RenderingBlueprint = field(default_factory=RenderingBlueprint)
    performance: PerformanceBlueprint = field(default_factory=PerformanceBlueprint)
    accessibility: AccessibilityBlueprint = field(default_factory=AccessibilityBlueprint)
    responsive: ResponsiveBlueprint = field(default_factory=ResponsiveBlueprint)
    seo: SEOBlueprint = field(default_factory=SEOBlueprint)
    technology: TechnologyBlueprint = field(default_factory=TechnologyBlueprint)
    
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
