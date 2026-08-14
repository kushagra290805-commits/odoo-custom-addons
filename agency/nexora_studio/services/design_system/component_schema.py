from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

@dataclass(frozen=True)
class ComponentSchema:
    """
    Strict JSON contract defining a component's capabilities, properties, and constraints.
    """
    component_id: str
    version: str
    category: str # Atom, Molecule, Organism, Template, Layout
    capabilities: List[str] = field(default_factory=list)
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    slots: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    design_tokens: Dict[str, str] = field(default_factory=dict)
    validation_rules: List[str] = field(default_factory=list)
    ai_metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict) # Tracks source_ecosystem, original_component_name, provider, version, license, imported_at
