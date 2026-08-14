from dataclasses import dataclass, field
import time
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class PipelineEvent:
    """Base immutable event for the generation pipeline."""
    session_id: str
    generation_id: str
    correlation_id: str
    current_state: str
    next_state: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    artifact_ref: Optional[Any] = None
    timestamp: float = field(default_factory=time.time)
    event_version: str = "1.0"
    event_category: str = "Base"
    event_type: str = "PipelineEvent"

# -------------------------------------------------------------------
# GENERATION EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class GenerationEvent(PipelineEvent):
    event_category: str = "Generation"

@dataclass(frozen=True)
class GenerationStarted(GenerationEvent):
    event_type: str = "GenerationStarted"

@dataclass(frozen=True)
class GenerationCompleted(GenerationEvent):
    event_type: str = "GenerationCompleted"

@dataclass(frozen=True)
class GenerationFailed(GenerationEvent):
    event_type: str = "GenerationFailed"
    error: Optional[str] = None

# -------------------------------------------------------------------
# PIPELINE EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class PipelineLifecycleEvent(PipelineEvent):
    event_category: str = "Pipeline"

@dataclass(frozen=True)
class StateTransitionStarted(PipelineLifecycleEvent):
    event_type: str = "StateTransitionStarted"

@dataclass(frozen=True)
class StateTransitionCompleted(PipelineLifecycleEvent):
    event_type: str = "StateTransitionCompleted"

@dataclass(frozen=True)
class EngineStarted(PipelineLifecycleEvent):
    event_type: str = "EngineStarted"
    engine_name: str = ""

@dataclass(frozen=True)
class EngineCompleted(PipelineLifecycleEvent):
    event_type: str = "EngineCompleted"
    engine_name: str = ""

@dataclass(frozen=True)
class EngineFailed(PipelineLifecycleEvent):
    event_type: str = "EngineFailed"
    engine_name: str = ""
    error: Optional[str] = None

# -------------------------------------------------------------------
# LIFECYCLE STAGE EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class RequirementsCaptured(PipelineLifecycleEvent):
    event_type: str = "RequirementsCaptured"

@dataclass(frozen=True)
class PlanningCompleted(PipelineLifecycleEvent):
    event_type: str = "PlanningCompleted"

@dataclass(frozen=True)
class ArchitectureCompleted(PipelineLifecycleEvent):
    event_type: str = "ArchitectureCompleted"

@dataclass(frozen=True)
class DesignCompleted(PipelineLifecycleEvent):
    event_type: str = "DesignCompleted"

@dataclass(frozen=True)
class CodeGenerationStarted(PipelineLifecycleEvent):
    event_type: str = "CodeGenerationStarted"

@dataclass(frozen=True)
class CodeGenerationCompleted(PipelineLifecycleEvent):
    event_type: str = "CodeGenerationCompleted"

# -------------------------------------------------------------------
# WORKSPACE EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class WorkspaceEvent(PipelineEvent):
    event_category: str = "Workspace"

@dataclass(frozen=True)
class WorkspacePrepared(WorkspaceEvent):
    event_type: str = "WorkspacePrepared"

@dataclass(frozen=True)
class PatchGenerated(WorkspaceEvent):
    event_type: str = "PatchGenerated"

@dataclass(frozen=True)
class PatchApplied(WorkspaceEvent):
    event_type: str = "PatchApplied"

# -------------------------------------------------------------------
# VALIDATION EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class ValidationEvent(PipelineEvent):
    event_category: str = "Validation"

@dataclass(frozen=True)
class ValidationStarted(ValidationEvent):
    event_type: str = "ValidationStarted"

@dataclass(frozen=True)
class ValidationCompleted(ValidationEvent):
    event_type: str = "ValidationCompleted"

# -------------------------------------------------------------------
# PREVIEW EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class PreviewEvent(PipelineEvent):
    event_category: str = "Preview"

@dataclass(frozen=True)
class PreviewStarted(PreviewEvent):
    event_type: str = "PreviewStarted"

@dataclass(frozen=True)
class PreviewReady(PreviewEvent):
    event_type: str = "PreviewReady"

# -------------------------------------------------------------------
# AGENT EVENTS
# -------------------------------------------------------------------
@dataclass(frozen=True)
class AgentEvent(PipelineEvent):
    event_category: str = "Agent"
    agent_id: str = ""

@dataclass(frozen=True)
class AgentCreated(AgentEvent):
    event_type: str = "AgentCreated"

@dataclass(frozen=True)
class AgentInitialized(AgentEvent):
    event_type: str = "AgentInitialized"

@dataclass(frozen=True)
class AgentPlanning(AgentEvent):
    event_type: str = "AgentPlanning"

@dataclass(frozen=True)
class AgentExecuting(AgentEvent):
    event_type: str = "AgentExecuting"

@dataclass(frozen=True)
class AgentObserving(AgentEvent):
    event_type: str = "AgentObserving"

@dataclass(frozen=True)
class AgentReviewing(AgentEvent):
    event_type: str = "AgentReviewing"

@dataclass(frozen=True)
class AgentCompleted(AgentEvent):
    event_type: str = "AgentCompleted"

@dataclass(frozen=True)
class AgentFailed(AgentEvent):
    event_type: str = "AgentFailed"
    error: Optional[str] = None

@dataclass(frozen=True)
class AgentCancelled(AgentEvent):
    event_type: str = "AgentCancelled"

