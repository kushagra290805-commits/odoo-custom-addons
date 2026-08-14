from typing import List, Dict, Set, Optional
from .graph import CapabilityGraph
from .models import CompositionResult, CompositionDiagnostic, ConfidenceScore, CapabilityNode
from .chain_builder import CapabilityChainBuilder

class CapabilityCompositionEngine:
    def __init__(self, registry_path: str):
        self.graph = CapabilityGraph(registry_path)
        self.chain_builder = CapabilityChainBuilder()
        
    def _bfs_path(self, target_outputs: List[str]) -> Optional[List[CapabilityNode]]:
        # In this simple implementation for ADR-0049, we attempt to find a path that satisfies the targets.
        # Since ADR-0049 requires deterministic traversal, we will just find all nodes that produce the targets
        # and recursively find their dependencies until we reach nodes with no dependencies.
        # Then we topological sort them.
        
        required_nodes: Set[str] = set()
        queue = []
        
        # 1. Find nodes producing targets
        for out in target_outputs:
            for node in self.graph.get_all_nodes():
                if out in node.metadata.produced_outputs:
                    queue.append(node.metadata.id)
                    break
                    
        # 2. Traverse backwards to find all dependencies
        visited = set()
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            required_nodes.add(curr)
            
            node = self.graph.get_node(curr)
            if node:
                for dep in node.dependencies:
                    queue.append(dep)
                    
        if not required_nodes:
            return None
            
        # 3. Topologically sort the required nodes to form the sequence
        # We can do this by building an in-degree map
        in_degree = {n: 0 for n in required_nodes}
        for n in required_nodes:
            node = self.graph.get_node(n)
            for dep in node.dependencies:
                if dep in required_nodes:
                    in_degree[n] += 1
                    
        sequence_ids = []
        ready = [n for n, deg in in_degree.items() if deg == 0]
        
        while ready:
            curr = ready.pop(0)
            sequence_ids.append(curr)
            
            node = self.graph.get_node(curr)
            for dep in node.dependents:
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        ready.append(dep)
                        
        if len(sequence_ids) != len(required_nodes):
            # Cycle detected in subgraph
            return None
            
        return [self.graph.get_node(nid) for nid in sequence_ids]

    def _detect_conflicts(self, sequence: List[CapabilityNode]) -> List[str]:
        conflicts = []
        seq_ids = [n.metadata.id for n in sequence]
        
        for node in sequence:
            for inc in node.metadata.incompatible_with:
                if inc in seq_ids:
                    conflicts.append(f"{node.metadata.id} is incompatible with {inc}")
        return conflicts

    def _calculate_confidence(self, sequence: List[CapabilityNode]) -> ConfidenceScore:
        if not sequence:
            return ConfidenceScore()
            
        # Simplistic scoring
        avg_conf = sum(n.metadata.confidence_weight for n in sequence) / len(sequence)
        
        return ConfidenceScore(
            coverage=1.0,
            completeness=1.0,
            provider_availability=1.0,
            execution_risk=1.0 - avg_conf,
            cost_confidence=1.0,
            overall=avg_conf
        )

    def compose(self, intent: str, target_outputs: List[str]) -> CompositionResult:
        sequence = self._bfs_path(target_outputs)
        
        diagnostic = CompositionDiagnostic()
        if not sequence:
            diagnostic.messages.append(f"Failed to find a path for outputs: {target_outputs}")
            return CompositionResult(success=False, diagnostics=diagnostic)
            
        conflicts = self._detect_conflicts(sequence)
        if conflicts:
            diagnostic.conflicting_capabilities = conflicts
            diagnostic.messages.append("Conflicts detected in capability chain.")
            return CompositionResult(success=False, diagnostics=diagnostic)
            
        confidence = self._calculate_confidence(sequence)
        
        plan = self.chain_builder.build_chain(intent, sequence)
        
        return CompositionResult(
            success=True,
            plan=plan,
            diagnostics=diagnostic,
            confidence=confidence
        )
