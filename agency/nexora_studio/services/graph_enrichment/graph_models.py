from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class Node:
    id: str
    label: str
    file_type: str = "unknown"
    source_file: str = "unknown"
    source_location: str = "L1"
    _origin: str = "inferred"
    community: int = -1
    norm_label: str = ""
    extra_properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "label": self.label,
            "file_type": self.file_type,
            "source_file": self.source_file,
            "source_location": self.source_location,
            "_origin": self._origin,
            "community": self.community,
            "norm_label": self.norm_label or self.label.lower(),
        }
        d.update(self.extra_properties)
        return d

@dataclass
class Link:
    source: str
    target: str
    relation: str
    context: str = ""
    confidence: str = "INFERRED"
    source_file: str = "unknown"
    source_location: str = "L1"
    weight: float = 1.0
    confidence_score: float = 0.98
    extra_properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "context": self.context,
            "confidence": self.confidence,
            "source_file": self.source_file,
            "source_location": self.source_location,
            "weight": self.weight,
            "confidence_score": self.confidence_score,
        }
        d.update(self.extra_properties)
        return d
