from typing import List, Dict, Any
from odoo.addons.nexora_studio.services.generation.execution.generation_node import GenerationNode, NodeType

class PageGenerator:
    """
    Translates a PagePlan into a sequence of ComponentPlan and AssetPlan tasks.
    Creates corresponding nodes in the GenerationGraph.
    """
    def generate_nodes_for_page(self, page_plan: Any, page_id: str) -> List[GenerationNode]:
        nodes = []
        
        # In reality, this inspects the PagePlan and creates nodes.
        # For each component in page_plan.components:
        for idx, comp in enumerate(getattr(page_plan, 'components', [])):
            comp_node = GenerationNode(
                node_id=f"{page_id}_comp_{idx}",
                node_type=NodeType.COMPONENT,
                metadata={"type": comp.type, "properties": comp.properties},
                dependencies=[page_id]
            )
            nodes.append(comp_node)
            
        return nodes
