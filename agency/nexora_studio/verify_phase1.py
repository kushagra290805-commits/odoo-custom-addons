import json
import sys

def verify_compatibility(base_path, enriched_path):
    print("Loading base graph...")
    with open(base_path, 'r', encoding='utf-8') as f:
        base = json.load(f)
        
    print("Loading enriched graph...")
    with open(enriched_path, 'r', encoding='utf-8') as f:
        enriched = json.load(f)
        
    # Check top-level keys
    print(f"Base keys: {list(base.keys())}")
    print(f"Enriched keys: {list(enriched.keys())}")
    
    assert "nodes" in enriched and "links" in enriched
    
    # Check node schema
    if base["nodes"]:
        sample_node_keys = set(base["nodes"][0].keys())
        print(f"Base node keys (sample): {sample_node_keys}")
        
    for i, n in enumerate(enriched["nodes"]):
        if "id" not in n:
            print(f"Node {i} missing 'id': {n}")
            return False
            
    # Check link schema
    if base["links"]:
        sample_link_keys = set(base["links"][0].keys())
        print(f"Base link keys (sample): {sample_link_keys}")
        
    for i, l in enumerate(enriched["links"]):
        if "source" not in l or "target" not in l:
            print(f"Link {i} missing source/target: {l}")
            return False
            
    print("Phase 1: Schema compatibility verified.")
    return True

if __name__ == '__main__':
    verify_compatibility('graphify-out/graph.json', 'graphify-out/enriched_graph.json')
