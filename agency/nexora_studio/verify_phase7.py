import json

def audit():
    with open('graphify-out/enriched_graph.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    nodes = {n['id']: n for n in data['nodes']}
    links = data['links']
    
    orphans = 0
    duplicates = 0
    seen_edges = set()
    
    for l in links:
        if l['source'] not in nodes:
            print(f"Orphan source: {l['source']}")
            orphans += 1
        if l['target'] not in nodes:
            print(f"Orphan target: {l['target']}")
            orphans += 1
            
        edge_sig = (l['source'], l['target'], l.get('relation'))
        if edge_sig in seen_edges:
            duplicates += 1
        seen_edges.add(edge_sig)
        
    print(f"Orphan Nodes in Edges: {orphans}")
    print(f"Duplicate Edges: {duplicates}")

if __name__ == "__main__":
    audit()
