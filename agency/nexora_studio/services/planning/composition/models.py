from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

@dataclass
class CapabilityMetadata:
    id: str
    required_inputs: List[str] = field(default_factory=list)
    produced_outputs: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    optional_prerequisites: List[str] = field(default_factory=list)
    compatible_with: List[str] = field(default_factory=lambda: ["*"])
    incompatible_with: List[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_latency: float = 0.0
    execution_type: str = "read"
    side_effects: bool = False
    confidence_weight: float = 1.0

@dataclass
class CapabilityNode:
    metadata: CapabilityMetadata
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

@dataclass
class ConfidenceScore:
    coverage: float = 0.0
    completeness: float = 0.0
    provider_availability: float = 0.0
    execution_risk: float = 0.0
    cost_confidence: float = 0.0
    overall: float = 0.0

@dataclass
class CompositionDiagnostic:
    missing_capabilities: List[str] = field(default_factory=list)
    conflicting_capabilities: List[str] = field(default_factory=list)
    suggested_alternatives: Dict[str, List[str]] = field(default_factory=dict)
    unreachable_outputs: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

@dataclass
class CompositionResult:
    success: bool
    plan: Optional[Any] = None  # Will be ExecutionPlan
    diagnostics: CompositionDiagnostic = field(default_factory=CompositionDiagnostic)
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore)
