import json
import os

class GraphExporter:
    @staticmethod
    def export(workspace_path: str, merged_nodes: list, merged_links: list, hyperedges: list):
        out_dir = os.path.join(workspace_path, "graphify-out")
        os.makedirs(out_dir, exist_ok=True)
        
        graph_data = {
            "nodes": merged_nodes,
            "links": merged_links,
            "hyperedges": hyperedges
        }
        json_path = os.path.join(out_dir, "enriched_graph.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False)
            
        dot_path = os.path.join(out_dir, "enriched_graph.dot")
        with open(dot_path, "w", encoding="utf-8") as f:
            f.write("digraph EnrichedGraph {\n")
            f.write("    rankdir=LR;\n")
            for node in merged_nodes:
                label = node.get('label', '').replace('"', '\\"')
                f.write(f'    "{node["id"]}" [label="{label}"];\n')
            for link in merged_links:
                rel = link.get('relation', '')
                f.write(f'    "{link["source"]}" -> "{link["target"]}" [label="{rel}"];\n')
            f.write("}\n")
            
        mmd_path = os.path.join(out_dir, "enriched_graph.mmd")
        with open(mmd_path, "w", encoding="utf-8") as f:
            f.write("graph TD\n")
            for node in merged_nodes:
                label = str(node.get('label', '')).replace('"', '\\"').replace("(", "").replace(")", "").replace("[", "").replace("]", "")
                safe_id = str(node['id']).replace('-', '_').replace('.', '_')
                f.write(f'    {safe_id}["{label}"]\n')
            for link in merged_links:
                safe_src = str(link['source']).replace('-', '_').replace('.', '_')
                safe_dst = str(link['target']).replace('-', '_').replace('.', '_')
                rel = link.get('relation', '')
                f.write(f'    {safe_src} -- "{rel}" --> {safe_dst}\n')
                
        return json_path, dot_path, mmd_path
