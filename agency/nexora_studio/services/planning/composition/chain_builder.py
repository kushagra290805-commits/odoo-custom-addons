from typing import List, Dict, Set
from ..plan_models import ExecutionPlan, ExecutionStep, ExecutionContext
from ..execution_graph import ExecutionGraphBuilder
from .models import CapabilityNode

class CapabilityChainBuilder:
    """
    Transforms a valid capability sequence into an executable ExecutionPlan graph.
    """
    
    def build_chain(self, objective: str, sequence: List[CapabilityNode]) -> ExecutionPlan:
        builder = ExecutionGraphBuilder()
        
        step_ids = {}
        for idx, node in enumerate(sequence):
            step_id = f"step_{idx}_{node.metadata.id.replace('.', '_')}"
            step_ids[node.metadata.id] = step_id
            
            # Simple payload template binding
            # In a real system, we'd map intent vars to required_inputs
            payload = {"args": {}}
            for req in node.metadata.required_inputs:
                if req == "query":
                    payload["args"]["query"] = objective
                    if node.metadata.id == "search.web":
                        payload["args"]["mcp_tool"] = "tavily_search"
                    elif node.metadata.id == "documentation.search":
                        payload["args"]["mcp_tool"] = "resolve-library-id"
                    elif node.metadata.id == "animation.reference":
                        payload["args"]["mcp_tool"] = "get_doc"
                elif req == "url":
                    payload["args"]["url"] = "https://example.com"
                    payload["args"]["mcp_tool"] = "crawl"
            
            if node.metadata.id == "repo.read":
                 payload["args"]["mcp_tool"] = "get_me"
                 
            step = ExecutionStep(
                capability=node.metadata.id,
                step_id=step_id,
                name=f"Execute {node.metadata.id}",
                payload_template=payload
            )
            builder.add_step(step)
            
        # Add dependencies based on the sequence
        # For ADR-0049 simple BFS sequence, we just wire them sequentially
        # Alternatively, we can wire them based on the actual graph dependencies
        for i in range(len(sequence) - 1):
            builder.add_dependency(step_ids[sequence[i].metadata.id], step_ids[sequence[i+1].metadata.id])
            
        plan = ExecutionPlan(
            objective=objective,
            graph=builder.build(),
            context=ExecutionContext(intent=objective)
        )
        
        return plan
