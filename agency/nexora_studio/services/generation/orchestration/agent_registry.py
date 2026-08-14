import logging
from typing import Dict, Type, Any, Optional

from odoo.addons.nexora_studio.services.generation.orchestration.agent_role_model import AgentRole

_logger = logging.getLogger(__name__)

class AgentRegistry:
    """
    Decouples AgentRoles from concrete Agent Class implementations.
    Allows dynamic overriding and plugin injection.
    """
    def __init__(self):
        self._registry: Dict[AgentRole, Type[Any]] = {}
        
    def register(self, role: AgentRole, agent_class: Type[Any]) -> None:
        """Register an implementation for a specific role."""
        self._registry[role] = agent_class
        _logger.debug(f"Registered Agent Implementation for Role: {role.value} -> {agent_class.__name__}")
        
    def resolve(self, role: AgentRole) -> Optional[Type[Any]]:
        """Retrieve the class to instantiate for a role."""
        return self._registry.get(role)
