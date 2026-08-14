import logging
from typing import Dict, List, Set
from collections import deque

from .base_provider import ProviderDependencyGraph

_logger = logging.getLogger(__name__)

class OdooProviderDependencyGraph(ProviderDependencyGraph):
    """
    Kahn's Topological Sort implementation for resolving Provider startup order.
    Detects circular dependencies and aborts module initialization.
    """

    def __init__(self):
        self._graph: Dict[str, List[str]] = {}
        self._in_degree: Dict[str, int] = {}
        self._nodes: Set[str] = set()

    def add_dependency(self, provider_id: str, requires: List[str]) -> None:
        """
        Add a provider and its dependencies to the graph.
        `requires` is a list of provider_ids that must be started before `provider_id`.
        """
        self._nodes.add(provider_id)
        if provider_id not in self._in_degree:
            self._in_degree[provider_id] = 0

        for req in requires:
            self._nodes.add(req)
            if req not in self._graph:
                self._graph[req] = []
            if req not in self._in_degree:
                self._in_degree[req] = 0
            
            # req must come before provider_id
            if provider_id not in self._graph[req]:
                self._graph[req].append(provider_id)
                self._in_degree[provider_id] += 1

    def detect_cycles(self) -> bool:
        """
        Returns True if a circular dependency cycle exists.
        """
        # We can just check if resolve_startup_order returns all nodes
        # But we implement a separate cycle check for clarity.
        try:
            order = self.resolve_startup_order()
            return len(order) != len(self._nodes)
        except ValueError:
            return True

    def resolve_startup_order(self) -> List[str]:
        """
        Resolve the provider startup order using Kahn's algorithm (BFS).
        Raises ValueError if a circular dependency is detected.
        """
        queue = deque()
        for node in self._nodes:
            if self._in_degree.get(node, 0) == 0:
                queue.append(node)

        resolved_order = []
        in_degree_copy = self._in_degree.copy()

        while queue:
            current = queue.popleft()
            resolved_order.append(current)

            for neighbor in self._graph.get(current, []):
                in_degree_copy[neighbor] -= 1
                if in_degree_copy[neighbor] == 0:
                    queue.append(neighbor)

        if len(resolved_order) != len(self._nodes):
            # Find the nodes that are part of the cycle
            cycle_nodes = [node for node in self._nodes if in_degree_copy.get(node, 0) > 0]
            _logger.error(f"Circular dependency detected among providers: {cycle_nodes}")
            raise ValueError(f"Circular dependency detected in provider graph: {cycle_nodes}")

        return resolved_order
