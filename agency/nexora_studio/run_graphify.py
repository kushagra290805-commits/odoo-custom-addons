import json, sys
from pathlib import Path

# Fix path to graphify
try:
    from graphify.detect import detect
    from graphify.extract import collect_files, extract as ast_extract
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.report import generate
    from graphify.export import to_json
except ImportError:
    print("Graphify not installed in this environment.")
    sys.exit(1)

out_dir = Path("graphify-out")
out_dir.mkdir(exist_ok=True)

print("1. Detecting files...")
detection = detect(Path("."))
out_dir.joinpath(".graphify_detect.json").write_text(json.dumps(detection, ensure_ascii=False), encoding="utf-8")

print("2. AST Extraction...")
code_files = []
for f in detection.get('files', {}).get('code', []):
    code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])

if code_files:
    ast_result = ast_extract(code_files, cache_root=Path("."))
else:
    ast_result = {'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}

print(f"AST: {len(ast_result['nodes'])} nodes, {len(ast_result['edges'])} edges")

print("3. Skipping Semantic Extraction (Mock)...")
sem_result = {'nodes':[],'edges':[],'hyperedges':[],'input_tokens':0,'output_tokens':0}

print("4. Merging...")
merged_nodes = list(ast_result['nodes'])
merged_edges = ast_result['edges']
merged = {
    'nodes': merged_nodes,
    'edges': merged_edges,
    'hyperedges': [],
    'input_tokens': 0,
    'output_tokens': 0,
}
out_dir.joinpath(".graphify_extract.json").write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")

print("5. Building Graph...")
G = build_from_json(merged, root='.', directed=False)
if G.number_of_nodes() == 0:
    print('ERROR: Graph is empty')
    sys.exit(1)

communities = cluster(G)
cohesion = score_all(G, communities)
gods = god_nodes(G)
surprises = surprising_connections(G, communities)
labels = {cid: 'Community ' + str(cid) for cid in communities}
questions = suggest_questions(G, communities, labels)

to_json(G, communities, 'graphify-out/graph.json')

analysis = {
    'communities': {str(k): v for k, v in communities.items()},
    'cohesion': {str(k): v for k, v in cohesion.items()},
    'gods': gods,
    'surprises': surprises,
    'questions': questions,
}
out_dir.joinpath(".graphify_analysis.json").write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

report = generate(G, communities, cohesion, labels, gods, surprises, detection, {'input':0, 'output':0}, '.', suggested_questions=questions)
out_dir.joinpath("GRAPH_REPORT.md").write_text(report, encoding="utf-8")

print("Done! Graph built at graphify-out/graph.json")

print('6. Running Graph Enrichment...')
import sys, os
sys.path.append(os.path.join(os.getcwd(), 'services', 'graph_enrichment'))
from graph_enrichment_engine import GraphEnrichmentEngine
engine = GraphEnrichmentEngine('.')
engine.run()
