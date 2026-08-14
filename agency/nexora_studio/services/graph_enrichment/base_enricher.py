from typing import List, Tuple
from graph_models import Node, Link

class BaseEnricher:
    """Base interface for all Nexora Graph Enrichers."""
    
    def __init__(self, workspace_path: str, existing_nodes: List[dict], existing_links: List[dict]):
        self.workspace_path = workspace_path
        self.existing_nodes = existing_nodes
        self.existing_links = existing_links

    def enrich(self) -> Tuple[List[Node], List[Link]]:
        raise NotImplementedError("Enrichers must implement enrich()")
