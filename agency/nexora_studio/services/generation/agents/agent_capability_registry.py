from typing import Dict, Set, Type
from enum import Enum

class AgentProfile(Enum):
    """Predefined capability profiles for agents."""
    SYSTEM = "SystemProfile"         # Full access for internal meta-agents
    CODE = "CodeProfile"             # Access to AI, Workspace, Events
    REVIEW = "ReviewProfile"         # Access to AI, Events, State
    PLANNING = "PlannerProfile"      # Access to AI, Events, Tools
    TOOL_EXEC = "ToolExecutionProfile" # Access to AI, Events, Tools
    MINIMAL = "MinimalProfile"       # Access to Events only
    # Phase 18.7 Design Intelligence Profiles
    KNOWLEDGE = "KnowledgeProfile"
    DESIGN_REVIEW = "DesignReviewProfile"
    ACCESSIBILITY = "AccessibilityProfile"
    BRAND = "BrandProfile"

class AgentCapabilityRegistry:
    """
    Registers agents to capability profiles and resolves those profiles
    into concrete GenerationRuntime scopes.
    """
    
    # Map profiles to actual GenerationRuntime capabilities
    _PROFILE_CAPABILITIES = {
        AgentProfile.SYSTEM: {"ai", "workspace", "state", "events", "agent", "metrics", "tools", "knowledge"},
        AgentProfile.CODE: {"ai", "workspace", "events", "tools", "knowledge"},
        AgentProfile.REVIEW: {"ai", "events", "state", "tools", "knowledge"},
        AgentProfile.PLANNING: {"ai", "events", "tools", "knowledge"},
        AgentProfile.TOOL_EXEC: {"ai", "events", "tools"},
        AgentProfile.MINIMAL: {"events"},
        AgentProfile.KNOWLEDGE: {"knowledge", "events", "ai"},
        AgentProfile.DESIGN_REVIEW: {"knowledge", "events", "ai", "workspace"},
        AgentProfile.ACCESSIBILITY: {"knowledge", "events", "ai", "workspace"},
        AgentProfile.BRAND: {"knowledge", "events", "ai"}
    }
    
    def __init__(self):
        self._registry: Dict[str, AgentProfile] = {}
        
    def register(self, agent_class: Type, profile: AgentProfile):
        """Assign an agent class to a capability profile."""
        self._registry[agent_class.__name__] = profile
        
    def get_capabilities(self, agent_class: Type) -> Set[str]:
        """Resolve the allowed capabilities for an agent class."""
        profile = self._registry.get(agent_class.__name__, AgentProfile.MINIMAL)
        return set(self._PROFILE_CAPABILITIES[profile])
    
    def resolve_scope_name(self, agent_name: str) -> str:
        """Helper to derive a scope name for metadata."""
        profile = self._registry.get(agent_name, AgentProfile.MINIMAL)
        return f"{agent_name} ({profile.value}) Scope"
