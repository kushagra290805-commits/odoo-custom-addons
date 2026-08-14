import json
import os
from typing import Dict, List, Tuple

class GraphLoader:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.graph_path = os.path.join(workspace_path, "graphify-out", "graph.json")

    def load(self) -> Tuple[List[dict], List[dict], List[dict]]:
        if not os.path.exists(self.graph_path):
            raise FileNotFoundError(f"Graph file not found at {self.graph_path}")
        
        with open(self.graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return data.get("nodes", []), data.get("links", []), data.get("hyperedges", [])
