from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any
from abc import ABC, abstractmethod

class RuntimeType(Enum):
    CORE = "core"
    AGENT = "agent"
    TOOL = "tool"
    KNOWLEDGE = "knowledge"
    ORCHESTRATION = "orchestration"

class RuntimeStartupPolicy(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    DISABLED = "disabled"

@dataclass
class RuntimeDescriptor:
    runtime_id: str
    name: str
    version: str
    runtime_type: RuntimeType
    startup_policy: RuntimeStartupPolicy = RuntimeStartupPolicy.REQUIRED
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    supported_workflows: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class RuntimeLifecycleEvent(Enum):
    INITIALIZING = "RuntimeInitializing"
    INITIALIZED = "RuntimeInitialized"
    FAILED = "RuntimeFailed"
    STOPPING = "RuntimeStopping"
    STOPPED = "RuntimeStopped"

class Runtime(ABC):
    """
    Common interface for all Core AI Runtimes.
    """
    @property
    @abstractmethod
    def descriptor(self) -> RuntimeDescriptor:
        pass
        
    @abstractmethod
    def initialize(self) -> None:
        pass
        
    @abstractmethod
    def shutdown(self) -> None:
        pass
        
    @abstractmethod
    def health_status(self) -> Dict[str, Any]:
        pass
