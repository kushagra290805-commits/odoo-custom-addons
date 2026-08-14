import json
from collections import defaultdict

def audit_graph():
    with open('graphify-out/enriched_graph.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    nodes = {n['id']: n for n in data['nodes']}
    links = data['links']
    
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    incoming_edges = defaultdict(list)
    outgoing_edges = defaultdict(list)
    
    for l in links:
        src = l['source']
        tgt = l['target']
        if src in nodes and tgt in nodes:
            in_degree[tgt] += 1
            out_degree[src] += 1
            incoming_edges[tgt].append(l)
            outgoing_edges[src].append(l)
            
    print("=== DEPENDENCY HOTSPOTS (High Fan-In) ===")
    hot_in = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:15]
    for n_id, count in hot_in:
        print(f"{count} incoming: {nodes[n_id].get('label')} ({nodes[n_id].get('source_file')})")
        
    print("\n=== DEPENDENCY HOTSPOTS (High Fan-Out) ===")
    hot_out = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:15]
    for n_id, count in hot_out:
        print(f"{count} outgoing: {nodes[n_id].get('label')} ({nodes[n_id].get('source_file')})")
        
    print("\n=== DEAD CODE CANDIDATES (0 Fan-In, not controllers/views) ===")
    dead_code = []
    for n_id, n in nodes.items():
        if n.get('file_type') == 'python' and in_degree[n_id] == 0:
            lbl = n.get('label', '').lower()
            if not lbl.endswith('controller') and not '@http.route' in lbl:
                # ignore top-level modules or generic files
                if n_id.startswith('file_') or n_id.startswith('class_'):
                    dead_code.append(n)
    for n in dead_code[:15]:
        print(f"Possible Dead Code: {n.get('label')} ({n.get('source_file')})")

    print("\n=== LAYER VIOLATIONS (Models calling Controllers) ===")
    for l in links:
        src_node = nodes.get(l['source'])
        tgt_node = nodes.get(l['target'])
        if src_node and tgt_node:
            src_lbl = src_node.get('label', '').lower()
            tgt_lbl = tgt_node.get('label', '').lower()
            src_file = src_node.get('source_file', '').lower()
            tgt_file = tgt_node.get('source_file', '').lower()
            
            if 'models' in src_file and 'controllers' in tgt_file:
                print(f"Violation: Model {src_lbl} calls Controller {tgt_lbl}")
                
    print("\n=== AI ARCHITECTURE COMPLIANCE ===")
    # Find anyone calling Adapters directly instead of ProviderManager
    # Adapters are usually in services/ai/ and end with _adapter.py
    adapters = [n for n_id, n in nodes.items() if 'adapter.py' in n.get('source_file', '')]
    adapter_ids = {n['id']: n for n in adapters}
    
    for l in links:
        if l['target'] in adapter_ids:
            src = nodes.get(l['source'])
            if src:
                src_file = src.get('source_file', '').lower()
                if 'ai_provider_manager' not in src_file and 'adapter' not in src_file and 'base' not in src_file:
                    print(f"Violation: {src.get('label')} ({src_file}) directly calls Adapter {nodes[l['target']].get('label')} ({nodes[l['target']].get('source_file')})")
                    
    # Check if anyone is bypassing AIConfigurationService to read API keys directly
    # Check calls to get_api_key or similar
    for l in links:
        tgt = nodes.get(l['target'])
        if tgt and 'get_api_key' in tgt.get('label', ''):
            src = nodes.get(l['source'])
            if src:
                if 'ai_configuration_service' not in src.get('source_file', '').lower():
                     print(f"Violation: {src.get('label')} directly fetches API key instead of using AIConfigurationService.")

if __name__ == '__main__':
    audit_graph()
