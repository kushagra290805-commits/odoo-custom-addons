from dataclasses import dataclass, field, replace
from typing import Dict, Any, List, Optional
from enum import Enum
import time

class GenerationState(Enum):
    PENDING = "PENDING"
    REQUIREMENTS_CAPTURED = "REQUIREMENTS_CAPTURED"
    BUSINESS_RESEARCH_COMPLETED = "BUSINESS_RESEARCH_COMPLETED"
    KNOWLEDGE_ENRICHMENT_COMPLETED = "KNOWLEDGE_ENRICHMENT_COMPLETED"
    PLANNING_COMPLETED = "PLANNING_COMPLETED"
    ARCHITECTURE_COMPLETED = "ARCHITECTURE_COMPLETED"
    COMPONENTS_DISCOVERED = "COMPONENTS_DISCOVERED"
    COMPONENTS_RANKED = "COMPONENTS_RANKED"
    COMPONENTS_ENRICHED = "COMPONENTS_ENRICHED"
    DESIGN_COMPLETED = "DESIGN_COMPLETED"
    TEMPLATE_RESOLVED = "TEMPLATE_RESOLVED"
    DESIGN_ORCHESTRATED = "DESIGN_ORCHESTRATED"
    ASSETS_GENERATED = "ASSETS_GENERATED"
    WORKSPACE_PREPARED = "WORKSPACE_PREPARED"
    CODE_GENERATION_COMPLETED = "CODE_GENERATION_COMPLETED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    PREVIEW_READY = "PREVIEW_READY"
    DEPLOYMENT_READY = "DEPLOYMENT_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"

@dataclass(frozen=True)
class RequirementModel:
    raw_input: str = ""
    domain: str = ""
    target_audience: str = ""
    goals: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    branding: Dict[str, Any] = field(default_factory=dict)
    seo: Dict[str, Any] = field(default_factory=dict)
    accessibility: Dict[str, Any] = field(default_factory=dict)



@dataclass(frozen=True)
class ArchitectureModel:
    layout_strategy: str = ""
    responsive_behavior: Dict[str, Any] = field(default_factory=dict)
    design_system: str = ""
    component_hierarchy: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)

@dataclass(frozen=True)
class ComponentTree:
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class Theme:
    design_tokens: Dict[str, Any] = field(default_factory=dict)
    typography_scale: Dict[str, Any] = field(default_factory=dict)
    spacing_system: Dict[str, Any] = field(default_factory=dict)
    colors: Dict[str, Any] = field(default_factory=dict)
    radius: str = ""
    shadows: str = ""
    motion: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Assets:
    images: List[Dict[str, Any]] = field(default_factory=list)
    icons: List[Dict[str, Any]] = field(default_factory=list)
    fonts: List[Dict[str, Any]] = field(default_factory=list)

@dataclass(frozen=True)
class Content:
    pages: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ValidationReport:
    passed: bool = False
    accessibility_score: int = 0
    seo_score: int = 0
    performance_score: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)

@dataclass(frozen=True)
class PreviewArtifacts:
    desktop_url: str = ""
    tablet_url: str = ""
    mobile_url: str = ""
    dom_snapshot: str = ""

@dataclass(frozen=True)
class Workspace:
    session_id: str = ""
    project_path: str = ""
    is_ready: bool = False

@dataclass(frozen=True)
class TemplateResolution:
    template_id: int = 0
    template_name: str = ""
    template_path: str = ""
    template_source: str = ""
    template_metadata: Dict[str, Any] = field(default_factory=dict)
    template_capabilities: List[str] = field(default_factory=list)
    template_variables: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class GenerationProgress:
    percentage: float = 0.0
    current_step: str = ""
    messages: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

@dataclass(frozen=True)
class WebsiteGenerationArtifact:
    """The canonical, immutable artifact containing the entire generated website state."""
    requirements: RequirementModel = field(default_factory=RequirementModel)
    research: Dict[str, Any] = field(default_factory=dict)
    knowledge: Dict[str, Any] = field(default_factory=dict)

    architecture: ArchitectureModel = field(default_factory=ArchitectureModel)
    component_tree: ComponentTree = field(default_factory=ComponentTree)
    theme: Theme = field(default_factory=Theme)
    assets: Assets = field(default_factory=Assets)
    content: Content = field(default_factory=Content)
    template: TemplateResolution = field(default_factory=TemplateResolution)
    design: Dict[str, Any] = field(default_factory=dict)
    validation: ValidationReport = field(default_factory=ValidationReport)
    previews: PreviewArtifacts = field(default_factory=PreviewArtifacts)
    workspace: Workspace = field(default_factory=Workspace)
    generation_metadata: Dict[str, Any] = field(default_factory=dict)

    def evolve(self, **kwargs) -> 'WebsiteGenerationArtifact':
        return replace(self, **kwargs)

@dataclass(frozen=True)
class GenerationContext:
    """Mutable execution context wrapping the immutable generation artifact."""
    context_id: str
    artifact: WebsiteGenerationArtifact = field(default_factory=WebsiteGenerationArtifact)
    metadata: Dict[str, Any] = field(default_factory=dict)
    progress: GenerationProgress = field(default_factory=GenerationProgress)
    state: GenerationState = GenerationState.PENDING
    
    def evolve(self, **kwargs) -> 'GenerationContext':
        return replace(self, **kwargs)
