"""
Connector Dependency Resolver
==============================
Part 5 of Phase 26 — Universal Connector Platform Foundation.

Resolves inter-connector dependency graphs and detects circular dependencies.
Returns an ordered installation sequence (topological sort).
"""
from __future__ import annotations

from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger
from dataclasses import dataclass
from typing import Dict, List, Set

from ..domain.models import (
    ConnectorDependencyType,
    ConnectorManifest,
)

_logger = get_logger(__name__)


@dataclass
class DependencyResolutionResult:
    """Result of a dependency resolution request."""
    success: bool
    install_order: List[str] = None  # type: ignore   # connector_ids in install order
    missing_dependencies: List[str] = None  # type: ignore
    circular_dependencies: List[List[str]] = None  # type: ignore
    errors: List[str] = None  # type: ignore

    def __post_init__(self):
        if self.install_order is None:
            self.install_order = []
        if self.missing_dependencies is None:
            self.missing_dependencies = []
        if self.circular_dependencies is None:
            self.circular_dependencies = []
        if self.errors is None:
            self.errors = []


class ConnectorDependencyResolver:
    """
    Resolves dependency graphs for connector installation.

    Features:
    - Topological sort for correct install order
    - Circular dependency detection
    - Missing dependency detection
    - Optional dependency handling (skipped if not registered)
    - Version constraint validation (semver range check)
    """

    def resolve(
        self,
        root_connector_id: str,
        manifests: Dict[str, ConnectorManifest],
    ) -> DependencyResolutionResult:
        """
        Resolve the full dependency graph for a connector.

        Args:
            root_connector_id: The connector to resolve dependencies for.
            manifests: Dict of all known connector manifests (connector_id → manifest).

        Returns:
            DependencyResolutionResult with install_order (topological sort)
            or error details on failure.
        """
        if root_connector_id not in manifests:
            return DependencyResolutionResult(
                success=False,
                errors=[f"Root connector '{root_connector_id}' manifest not found."]
            )

        missing: List[str] = []
        errors: List[str] = []

        # Collect all nodes in the dependency subgraph
        subgraph: Dict[str, List[str]] = {}
        visited_discovery: Set[str] = set()

        def collect(cid: str) -> None:
            if cid in visited_discovery:
                return
            visited_discovery.add(cid)
            manifest = manifests.get(cid)
            if manifest is None:
                missing.append(cid)
                subgraph[cid] = []
                return
            deps = []
            for dep in manifest.dependencies:
                if dep.dependency_type == ConnectorDependencyType.CONFLICTS_WITH:
                    # Conflict checking — if the conflicting connector exists and is enabled, error
                    if dep.depends_on_connector_id in manifests:
                        errors.append(
                            f"Connector '{cid}' conflicts with '{dep.depends_on_connector_id}' "
                            "which is already registered."
                        )
                    continue
                if dep.dependency_type == ConnectorDependencyType.OPTIONAL:
                    if dep.depends_on_connector_id in manifests:
                        deps.append(dep.depends_on_connector_id)
                    # else skip optional missing dep
                else:  # REQUIRED
                    deps.append(dep.depends_on_connector_id)
            subgraph[cid] = deps
            for dep_id in deps:
                collect(dep_id)

        collect(root_connector_id)

        if errors:
            return DependencyResolutionResult(
                success=False,
                missing_dependencies=missing,
                errors=errors,
            )

        # Topological sort (Kahn's algorithm)
        install_order, cycles = self._topological_sort(subgraph)

        if cycles:
            return DependencyResolutionResult(
                success=False,
                missing_dependencies=missing,
                circular_dependencies=cycles,
                errors=[f"Circular dependency detected: {' → '.join(c)}" for c in cycles],
            )

        return DependencyResolutionResult(
            success=True,
            install_order=install_order,
            missing_dependencies=missing,
        )

    def _topological_sort(
        self,
        graph: Dict[str, List[str]],
    ) -> tuple:
        """
        Kahn's algorithm for topological sort.
        Returns (sorted_list, cycles_list).
        cycles_list is empty if no cycles found.
        """
        in_degree: Dict[str, int] = {node: 0 for node in graph}
        for node, deps in graph.items():
            for dep in deps:
                if dep not in in_degree:
                    in_degree[dep] = 0
                in_degree[dep] += 1

        queue: List[str] = [n for n, deg in in_degree.items() if deg == 0]
        result: List[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dep in graph.get(node, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        if len(result) != len(graph):
            # There are cycles — find them
            remaining = {n for n, deg in in_degree.items() if deg > 0}
            # Simplified cycle report — list remaining nodes
            cycles = [list(remaining)]
            return result, cycles

        return result, []

    def check_version_constraint(
        self,
        installed_version_str: str,
        constraint: str,
    ) -> bool:
        """
        Basic semver constraint check.
        Supports: *, >=X.Y.Z, <=X.Y.Z, ==X.Y.Z, ^X.Y.Z (same major)
        Returns True if the installed version satisfies the constraint.
        """
        if constraint == "*" or not constraint:
            return True

        from ..domain.models import ConnectorVersion
        try:
            installed = ConnectorVersion.parse(installed_version_str)
        except (ValueError, IndexError):
            return False

        if constraint.startswith("^"):
            required = ConnectorVersion.parse(constraint[1:])
            return installed.major == required.major and installed >= required
        elif constraint.startswith(">="):
            required = ConnectorVersion.parse(constraint[2:])
            return installed >= required
        elif constraint.startswith("<="):
            required = ConnectorVersion.parse(constraint[2:])
            return installed <= required
        elif constraint.startswith("=="):
            required = ConnectorVersion.parse(constraint[2:])
            return installed == required
        else:
            # Treat as exact match
            try:
                required = ConnectorVersion.parse(constraint)
                return installed == required
            except Exception:
                return False
