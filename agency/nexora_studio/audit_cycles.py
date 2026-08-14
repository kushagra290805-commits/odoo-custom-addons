import json
from collections import defaultdict

with open('graphify-out/enriched_graph.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = {n['id']: n for n in data['nodes']}
links = data['links']

# Build adj list for python files only (module level imports ideally, or class level)
adj = defaultdict(set)
for l in links:
    src = nodes.get(l['source'])
    tgt = nodes.get(l['target'])
    if src and tgt and src.get('file_type') == 'python' and tgt.get('file_type') == 'python':
        if src['id'] != tgt['id']:
            adj[src['id']].add(tgt['id'])

def find_cycles():
    visited = set()
    path = []
    cycles = []
    
    def dfs(node_id):
        if node_id in path:
            cycle = path[path.index(node_id):] + [node_id]
            cycles.append(cycle)
            return
        if node_id in visited:
            return
            
        visited.add(node_id)
        path.append(node_id)
        for neighbor in adj[node_id]:
            dfs(neighbor)
        path.pop()
        
    for n_id in list(adj.keys()):
        dfs(n_id)
        
    return cycles

cycles = find_cycles()
print(f"Found {len(cycles)} cycles.")
if cycles:
    for c in cycles[:5]: # just show first 5
        names = [nodes[n].get('label', n) for n in c]
        print(" -> ".join(names))
