import json

with open('graphify-out/enriched_graph.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = {n['id']: n for n in data['nodes']}
links = data['links']

target_id = None
for n_id, n in nodes.items():
    if n.get('label') == 'GenerationOrchestrator':
        target_id = n_id
        break

if target_id:
    print(f"Callers of GenerationOrchestrator:")
    for l in links:
        if l['target'] == target_id:
            src = nodes.get(l['source'])
            print(f"  {src.get('label')} ({src.get('source_file')}) via {l.get('relation')}")
