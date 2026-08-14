import json

with open('graphify-out/enriched_graph.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = {n['id']: n['label'] for n in data['nodes']}
links = data['links']

print("Builder pipeline edges:")
for l in links:
    if l.get('relation') == 'BUILDER_PIPELINE':
        print(f"{nodes.get(l['source'])} -> {nodes.get(l['target'])}")
        
print("\nDead Code:")
in_degree = {n['id']: 0 for n in data['nodes']}
for l in links:
    if l['target'] in in_degree:
        in_degree[l['target']] += 1

dead_nodes = []
for n in data['nodes']:
    if n.get('file_type') == 'python' and in_degree[n['id']] == 0:
        lbl = n.get('label', '').lower()
        if not lbl.endswith('controller') and not '@http.route' in lbl:
            if n['id'].startswith('file_') or n['id'].startswith('class_'):
                dead_nodes.append(n)
for n in dead_nodes[:20]:
    print(f"Possible Dead Code: {n.get('label')} ({n.get('source_file')})")
