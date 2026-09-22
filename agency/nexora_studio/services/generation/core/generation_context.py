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
    CONTENT_GENERATED = "CONTENT_GENERATED"
    WORKSPACE_PREPARED = "WORKSPACE_PREPARED"
    CODE_GENERATION_COMPLETED = "CODE_GENERATION_COMPLETED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    PREVIEW_READY = "PREVIEW_READY"
    BROWSER_VALIDATED = "BROWSER_VALIDATED"
    DEPLOYMENT_READY = "DEPLOYMENT_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"

@dataclass(frozen=True)
class RequirementModel:
    raw_input: str = ""
    current_supervisor_instruction: str = ""

    domain: str = ""
    target_audience: str = ""
    # Phase 47.18 (Part A): brief-extracted business identity. Extracted by
    # the existing RequirementAnalyzer from labeled brief lines and mapped by
    # the existing RequirementEngine — no second requirements model. Empty
    # values simply mean the brief did not state them.
    business_name: str = ""
    business_category: str = ""
    location: str = ""
    # Phase 47.19 (Part D): brief declares a responsive/mobile expectation —
    # activates the bounded mobile viewport validation in the existing
    # browser phase. Deterministic and default-False (desktop-only).
    mobile_expected: bool = False
    goals: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    branding: Dict[str, Any] = field(default_factory=dict)
    seo: Dict[str, Any] = field(default_factory=dict)
    accessibility: Dict[str, Any] = field(default_factory=dict)
    # Phase 47.32 (ADR-0083): project capabilities inferred from the brief.
    # backend_required is a platform-owned decision (deterministic policy).
    capabilities: List[str] = field(default_factory=list)
    backend_required: bool = False



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
    # Phase 47.23 (ADR-0075): the theme's selected webfonts. Materialized
    # deterministically by the rendering provider (Google Fonts link + CSS
    # custom properties) — the canonical theme font contract.
    font_heading: str = "Inter"
    font_body: str = "Inter"

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
    # Phase 47.12 (U9.3): truthful build-acceptance evidence from the
    # validation stage (install / production build / build output). Downstream
    # preview acceptance gates on this, never on unrelated validation issues.
    build_acceptance: Dict[str, Any] = field(default_factory=dict)
    # Phase 47.13 (U9.4): truthful browser-validation evidence from the
    # post-preview validation pass (navigation / console / network / routes)
    # produced by the canonical nexora.provider.playwright owner.
    browser_validation: Dict[str, Any] = field(default_factory=dict)
    # Phase 47.15 (U9.6): ONE deterministic final acceptance decision
    # (accepted / failed) aggregated by the SAME ValidationEngine from the
    # existing build / preview / browser / renderer evidence. No second
    # report model and no separate acceptance owner.
    final_acceptance: Dict[str, Any] = field(default_factory=dict)

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

    def get_supervisor_evidence(self) -> Dict[str, Any]:
        """Phase 48.2: Deterministic bounded evidence projection for Supervisor EVALUATE.
        Never exposes the full repository, secrets, or unbounded logs."""
        return {
            "composition_manifest": self.metadata.get("composition_manifest", {}),
            "validation_issues_count": self.metadata.get("validation_issues_count", 0),
            "build_acceptance": self.metadata.get("build_acceptance", {}),
            "code_fallbacks": self.metadata.get("code_fallbacks", {}),
            "requirements": {
                "business_category": self.artifact.requirements.business_category,
                "business_name": self.artifact.requirements.business_name,
                "domain": self.artifact.requirements.domain,
                "capabilities": self.artifact.requirements.capabilities,
            }
        }

@dataclass(frozen=True)
class SupervisorPrepareContract:
    is_valid: bool = True
    instruction: str = ""
    rejection_reason: str = ""

@dataclass(frozen=True)
class SupervisorEvaluateContract:
    satisfies_requirements: bool = False
    findings: tuple[str, ...] = field(default_factory=tuple)
    improvement_instruction: str = ""
