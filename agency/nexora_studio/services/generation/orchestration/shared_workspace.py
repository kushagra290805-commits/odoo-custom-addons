import logging
from typing import Dict, Any, List, Optional
import copy

from odoo.addons.nexora_studio.services.generation.orchestration.models import AgentMessage, AgentRole

_logger = logging.getLogger(__name__)

class SharedWorkspace:
    """
    The Orchestration Blackboard.
    Mutatable ONLY by the MultiAgentOrchestrator. 
    Agents receive read-only deep copies of segments of this workspace.
    """
    def __init__(self, generation_id: str):
        self._generation_id = generation_id
        self._messages: List[AgentMessage] = []
        self._state: Dict[str, Any] = {}
        
    def add_message(self, message: AgentMessage) -> None:
        """Called by Orchestrator after processing AgentExecutionResult"""
        self._messages.append(message)
        _logger.debug(f"Workspace appended message from {message.source_role} to {message.target_role}")
        
    def update_state(self, key: str, value: Any) -> None:
        """Called by Orchestrator after processing AgentExecutionResult"""
        self._state[key] = value
        
    def get_messages_for_role(self, target_role: AgentRole) -> List[AgentMessage]:
        """Fetch all historical messages directed at this role."""
        return [msg for msg in self._messages if msg.target_role == target_role]
        
    def hydrate_agent_context(self, target_role: AgentRole) -> Dict[str, Any]:
        """
        Creates a clean, isolated state dictionary for an agent to boot up with.
        Prevents bleeding of other agents' internal scratchpads.
        """
        relevant_messages = self.get_messages_for_role(target_role)
        
        # Deep copy the shared structural state so agents can't mutate the master reference
        safe_state = copy.deepcopy(self._state)
        
        return {
            "inbox": relevant_messages,
            "shared_state": safe_state
        }

class MessageRouter:
    """
    Helper used by Orchestrator to route messages from the AgentExecutionResult
    onto the SharedWorkspace safely.
    """
    def route(self, messages: List[AgentMessage], workspace: SharedWorkspace) -> None:
        for msg in messages:
            workspace.add_message(msg)
