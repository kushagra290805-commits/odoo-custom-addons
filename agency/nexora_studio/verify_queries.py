import json

with open("graphify-out/enriched_graph.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = {n["id"]: n for n in data["nodes"]}
links = data["links"]

def find_node_by_label(label):
    for n in data["nodes"]:
        if n.get("label") == label:
            return n
    return None

def get_edges(node_id):
    incoming = []
    outgoing = []
    for l in links:
        if l["source"] == node_id:
            outgoing.append(l)
        if l["target"] == node_id:
            incoming.append(l)
    return incoming, outgoing

print("--- AIProviderManager ---")
ai_mgr = find_node_by_label("AIProviderManager")
if ai_mgr:
    inc, out = get_edges(ai_mgr["id"])
    print(f"Incoming ({len(inc)}):")
    for l in inc:
        src = nodes.get(l['source'], {}).get('label', l['source'])
        print(f"  {src} --[{l.get('relation')}]-->")
    print(f"Outgoing ({len(out)}):")
    for l in out:
        dst = nodes.get(l['target'], {}).get('label', l['target'])
        print(f"  --[{l.get('relation')}]--> {dst}")
else:
    print("AIProviderManager not found.")
