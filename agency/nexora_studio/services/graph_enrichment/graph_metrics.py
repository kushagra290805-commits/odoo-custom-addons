import json
import os

class GraphMetrics:
    @staticmethod
    def generate_metrics(workspace_path: str, new_nodes: list, new_links: list):
        metrics = {
            "total_inferred_nodes": len(new_nodes),
            "total_inferred_edges": len(new_links),
            "edge_breakdown": {}
        }
        
        for link in new_links:
            rel = link.relation
            metrics["edge_breakdown"][rel] = metrics["edge_breakdown"].get(rel, 0) + 1
            
        out_dir = os.path.join(workspace_path, "graphify-out")
        os.makedirs(out_dir, exist_ok=True)
        metrics_path = os.path.join(out_dir, "enrichment_metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
            
        return metrics
