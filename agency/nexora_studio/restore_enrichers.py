import os

base_dir = r"d:\ODOO\custom-addons\agency\nexora_studio\services\graph_enrichment"
os.makedirs(base_dir, exist_ok=True)

files = {
    "__init__.py": '"""Graph Enrichment Engine package."""\n',
    "graph_models.py": '''from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class Node:
    id: str
    label: str
    file_type: str = "unknown"
    source_file: str = "unknown"
    source_location: str = "L1"
    _origin: str = "inferred"
    community: int = -1
    norm_label: str = ""
    extra_properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "label": self.label,
            "file_type": self.file_type,
            "source_file": self.source_file,
            "source_location": self.source_location,
            "_origin": self._origin,
            "community": self.community,
            "norm_label": self.norm_label or self.label.lower(),
        }
        d.update(self.extra_properties)
        return d

@dataclass
class Link:
    source: str
    target: str
    relation: str
    context: str = ""
    confidence: str = "INFERRED"
    source_file: str = "unknown"
    source_location: str = "L1"
    weight: float = 1.0
    confidence_score: float = 0.98
    extra_properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "context": self.context,
            "confidence": self.confidence,
            "source_file": self.source_file,
            "source_location": self.source_location,
            "weight": self.weight,
            "confidence_score": self.confidence_score,
        }
        d.update(self.extra_properties)
        return d
''',
    "base_enricher.py": '''from typing import List, Tuple
from graph_models import Node, Link

class BaseEnricher:
    """Base interface for all Nexora Graph Enrichers."""
    
    def __init__(self, workspace_path: str, existing_nodes: List[dict], existing_links: List[dict]):
        self.workspace_path = workspace_path
        self.existing_nodes = existing_nodes
        self.existing_links = existing_links

    def enrich(self) -> Tuple[List[Node], List[Link]]:
        raise NotImplementedError("Enrichers must implement enrich()")
''',
    "graph_loader.py": '''import json
import os
from typing import Dict, List, Tuple

class GraphLoader:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.graph_path = os.path.join(workspace_path, "graphify-out", "graph.json")

    def load(self) -> Tuple[List[dict], List[dict], List[dict]]:
        if not os.path.exists(self.graph_path):
            raise FileNotFoundError(f"Graph file not found at {self.graph_path}")
        
        with open(self.graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return data.get("nodes", []), data.get("links", []), data.get("hyperedges", [])
''',
    "odoo_registry_enricher.py": '''import ast
import os
from typing import Dict, List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class OdooRegistryEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_nodes = []
        new_links = []
        
        class_to_node = {} 
        for n in self.existing_nodes:
            if 'ClassDef' in n.get('label', '') or True:
                class_to_node[n.get('norm_label', '').lower()] = n['id']
                
        python_files = []
        for root, _, files in os.walk(self.workspace_path):
            if 'graphify-out' in root or '.venv' in root:
                continue
            for f in files:
                if f.endswith('.py'):
                    python_files.append(os.path.join(root, f))
                    
        model_map = {} 
        
        for filepath in python_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name) and target.id in ['_name', '_inherit']:
                                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                            model_map[item.value.value] = class_name
            except Exception:
                continue
                
        for filepath in python_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        caller_name = node.name
                        caller_node_id = None
                        for n in self.existing_nodes:
                            if n.get('norm_label') == f".{caller_name}()" or n.get('norm_label') == f"{caller_name}()" or n.get('label') == caller_name:
                                caller_node_id = n['id']
                                break
                                
                        if not caller_node_id:
                            continue
                            
                        for subnode in ast.walk(node):
                            if isinstance(subnode, ast.Subscript):
                                if isinstance(subnode.value, ast.Attribute) and subnode.value.attr == 'env':
                                    if isinstance(subnode.slice, ast.Constant) and isinstance(subnode.slice.value, str):
                                        target_model = subnode.slice.value
                                        if target_model in model_map:
                                            target_class = model_map[target_model]
                                            target_node_id = class_to_node.get(target_class.lower())
                                            if target_node_id:
                                                new_links.append(Link(
                                                    source=caller_node_id,
                                                    target=target_node_id,
                                                    relation="ORM_REFERENCE",
                                                    context="env_lookup",
                                                    confidence="INFERRED",
                                                    source_file=os.path.relpath(filepath, self.workspace_path),
                                                    source_location=f"L{subnode.lineno}"
                                                ))
            except Exception:
                continue
                
        return new_nodes, new_links
''',
    "xml_view_enricher.py": '''import os
import xml.etree.ElementTree as ET
from typing import List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class XMLViewEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_nodes = []
        new_links = []
        
        xml_files = []
        for root, _, files in os.walk(self.workspace_path):
            if 'graphify-out' in root or '.venv' in root:
                continue
            for f in files:
                if f.endswith('.xml'):
                    xml_files.append(os.path.join(root, f))
                    
        import ast
        model_map = {}
        class_to_node = {}
        
        for n in self.existing_nodes:
            class_to_node[n.get('norm_label', '').lower()] = n['id']
            
        for root, _, files in os.walk(self.workspace_path):
            if 'graphify-out' in root or '.venv' in root:
                continue
            for f in files:
                if f.endswith('.py'):
                    try:
                        with open(os.path.join(root, f), 'r', encoding='utf-8') as pf:
                            tree = ast.parse(pf.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.ClassDef):
                                    for item in node.body:
                                        if isinstance(item, ast.Assign):
                                            for target in item.targets:
                                                if isinstance(target, ast.Name) and target.id in ['_name', '_inherit']:
                                                    if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                                        model_map[item.value.value] = node.name
                    except Exception:
                        pass
        
        for filepath in xml_files:
            rel_path = os.path.relpath(filepath, self.workspace_path)
            try:
                tree = ET.parse(filepath)
                root = tree.getroot()
                
                for record in root.findall('.//record'):
                    model = record.get('model')
                    record_id = record.get('id')
                    
                    if not record_id:
                        continue
                        
                    node_id = f"xml_{record_id}"
                    new_nodes.append(Node(
                        id=node_id,
                        label=f"{record_id} ({model})",
                        file_type="xml",
                        source_file=rel_path,
                        _origin="inferred"
                    ))
                    
                    if model in ['ir.ui.view', 'ir.actions.act_window']:
                        for field in record.findall("field[@name='res_model']"):
                            res_model = field.text
                            if res_model and res_model in model_map:
                                target_class = model_map[res_model]
                                target_node_id = class_to_node.get(target_class.lower())
                                if target_node_id:
                                    new_links.append(Link(
                                        source=node_id,
                                        target=target_node_id,
                                        relation="XML_REFERENCE",
                                        context="res_model",
                                        source_file=rel_path
                                    ))
            except Exception:
                continue
                
        return new_nodes, new_links
''',
    "fastapi_enricher.py": '''import ast
import os
from typing import List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class FastAPIEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_nodes = []
        new_links = []
        
        python_files = []
        for root, _, files in os.walk(self.workspace_path):
            if 'graphify-out' in root or '.venv' in root:
                continue
            for f in files:
                if f.endswith('.py'):
                    python_files.append(os.path.join(root, f))
                    
        for filepath in python_files:
            rel_path = os.path.relpath(filepath, self.workspace_path)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        for decorator in node.decorator_list:
                            route_path = None
                            
                            if isinstance(decorator, ast.Call):
                                if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'route':
                                    if isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == 'http':
                                        if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                            route_path = decorator.args[0].value
                                elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                        route_path = f"{decorator.func.attr.upper()} {decorator.args[0].value}"
                                        
                            if route_path:
                                endpoint_id = f"route_{route_path}"
                                new_nodes.append(Node(
                                    id=endpoint_id,
                                    label=route_path,
                                    file_type="route",
                                    source_file=rel_path,
                                    source_location=f"L{node.lineno}",
                                    _origin="inferred"
                                ))
                                
                                handler_node_id = None
                                for n in self.existing_nodes:
                                    if n.get('norm_label') == f".{node.name}()" or n.get('label') == node.name:
                                        handler_node_id = n['id']
                                        break
                                        
                                if handler_node_id:
                                    new_links.append(Link(
                                        source=endpoint_id,
                                        target=handler_node_id,
                                        relation="HTTP_ROUTE",
                                        context="handler",
                                        source_file=rel_path,
                                        source_location=f"L{node.lineno}"
                                    ))
            except Exception:
                continue
                
        return new_nodes, new_links
''',
    "ai_pipeline_enricher.py": '''from typing import List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class AIPipelineEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_links = []
        
        ai_components = {
            "BuilderSessionOrchestrator": None,
            "ProjectPlannerService": None,
            "GenerationOrchestrator": None,
            "AIProviderManager": None,
            "CostRouter": None,
            "AIConfigurationService": None,
            "TestAIAdapter": None,
            "OpenRouterAdapter": None,
            "GitService": None,
        }
        
        for n in self.existing_nodes:
            label = n.get('label')
            if label in ai_components:
                ai_components[label] = n['id']
                
        edges_to_create = [
            ("ProjectPlannerService", "AIConfigurationService", "AI_PIPELINE"),
            ("GenerationOrchestrator", "AIProviderManager", "AI_PIPELINE"),
            ("AIProviderManager", "AIConfigurationService", "AI_PIPELINE"),
            ("AIProviderManager", "CostRouter", "AI_PIPELINE"),
            ("CostRouter", "AIConfigurationService", "AI_PIPELINE"),
            ("CostRouter", "OpenRouterAdapter", "AI_PIPELINE"),
            ("GenerationOrchestrator", "GitService", "AI_PIPELINE"),
        ]
        
        for src, dst, rel in edges_to_create:
            if ai_components.get(src) and ai_components.get(dst):
                new_links.append(Link(
                    source=ai_components[src],
                    target=ai_components[dst],
                    relation=rel,
                    context="semantic_pipeline",
                    confidence="INFERRED",
                ))
                
        return [], new_links
''',
    "builder_pipeline_enricher.py": '''from typing import List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class BuilderPipelineEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_links = []
        
        builder_components = {
            "BuilderSessionOrchestrator": None,
            "BuilderSession": None,
            "ProjectConfiguration": None,
            "WorkspaceFileService": None,
            "GitService": None,
            "PreviewRuntimeService": None
        }
        
        for n in self.existing_nodes:
            label = n.get('label')
            if label in builder_components:
                builder_components[label] = n['id']
                
        edges_to_create = [
            ("BuilderSessionOrchestrator", "BuilderSession", "BUILDER_PIPELINE"),
            ("BuilderSession", "ProjectConfiguration", "BUILDER_PIPELINE"),
            ("BuilderSession", "WorkspaceFileService", "BUILDER_PIPELINE"),
            ("BuilderSession", "GitService", "BUILDER_PIPELINE"),
            ("BuilderSession", "PreviewRuntimeService", "BUILDER_PIPELINE")
        ]
        
        for src, dst, rel in edges_to_create:
            if builder_components.get(src) and builder_components.get(dst):
                new_links.append(Link(
                    source=builder_components[src],
                    target=builder_components[dst],
                    relation=rel,
                    context="semantic_pipeline",
                    confidence="INFERRED",
                ))
                
        return [], new_links
''',
    "graph_merger.py": '''from typing import List
from graph_models import Node, Link

class GraphMerger:
    @staticmethod
    def merge(existing_nodes: List[dict], existing_links: List[dict], new_nodes: List[Node], new_links: List[Link]):
        merged_nodes = list(existing_nodes)
        merged_links = list(existing_links)
        
        existing_ids = {n['id'] for n in existing_nodes}
        for node in new_nodes:
            if node.id not in existing_ids:
                merged_nodes.append(node.to_dict())
                existing_ids.add(node.id)
                
        existing_link_signatures = {(l['source'], l['target'], l.get('relation', l.get('type', ''))) for l in existing_links}
        for link in new_links:
            sig = (link.source, link.target, link.relation)
            if sig not in existing_link_signatures:
                merged_links.append(link.to_dict())
                existing_link_signatures.add(sig)
                
        return merged_nodes, merged_links
''',
    "graph_exporter.py": '''import json
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
            f.write("digraph EnrichedGraph {\\n")
            f.write("    rankdir=LR;\\n")
            for node in merged_nodes:
                label = node.get('label', '').replace('"', '\\\\"')
                f.write(f'    "{node["id"]}" [label="{label}"];\\n')
            for link in merged_links:
                rel = link.get('relation', '')
                f.write(f'    "{link["source"]}" -> "{link["target"]}" [label="{rel}"];\\n')
            f.write("}\\n")
            
        mmd_path = os.path.join(out_dir, "enriched_graph.mmd")
        with open(mmd_path, "w", encoding="utf-8") as f:
            f.write("graph TD\\n")
            for node in merged_nodes:
                label = str(node.get('label', '')).replace('"', '\\\\"').replace("(", "").replace(")", "").replace("[", "").replace("]", "")
                safe_id = str(node['id']).replace('-', '_').replace('.', '_')
                f.write(f'    {safe_id}["{label}"]\\n')
            for link in merged_links:
                safe_src = str(link['source']).replace('-', '_').replace('.', '_')
                safe_dst = str(link['target']).replace('-', '_').replace('.', '_')
                rel = link.get('relation', '')
                f.write(f'    {safe_src} -- "{rel}" --> {safe_dst}\\n')
                
        return json_path, dot_path, mmd_path
''',
    "graph_metrics.py": '''import json
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
''',
    "graph_enrichment_engine.py": '''import os
from typing import List
from graph_loader import GraphLoader
from odoo_registry_enricher import OdooRegistryEnricher
from xml_view_enricher import XMLViewEnricher
from fastapi_enricher import FastAPIEnricher
from ai_pipeline_enricher import AIPipelineEnricher
from builder_pipeline_enricher import BuilderPipelineEnricher
from graph_merger import GraphMerger
from graph_exporter import GraphExporter
from graph_metrics import GraphMetrics

class GraphEnrichmentEngine:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        
    def run(self):
        print("Starting Graph Enrichment Engine...")
        loader = GraphLoader(self.workspace_path)
        try:
            nodes, links, hyperedges = loader.load()
            print(f"Loaded {len(nodes)} nodes and {len(links)} edges from Graphify output.")
        except FileNotFoundError:
            print("graph.json not found. Run Graphify AST extraction first.")
            return
            
        enrichers = [
            OdooRegistryEnricher(self.workspace_path, nodes, links),
            XMLViewEnricher(self.workspace_path, nodes, links),
            FastAPIEnricher(self.workspace_path, nodes, links),
            AIPipelineEnricher(self.workspace_path, nodes, links),
            BuilderPipelineEnricher(self.workspace_path, nodes, links),
        ]
        
        all_new_nodes = []
        all_new_links = []
        
        for enricher in enrichers:
            name = enricher.__class__.__name__
            try:
                new_nodes, new_links = enricher.enrich()
                all_new_nodes.extend(new_nodes)
                all_new_links.extend(new_links)
                print(f"{name}: +{len(new_nodes)} nodes, +{len(new_links)} edges")
            except Exception as e:
                print(f"Error in {name}: {e}")
                
        merged_nodes, merged_links = GraphMerger.merge(nodes, links, all_new_nodes, all_new_links)
        print(f"Merge complete. Total nodes: {len(merged_nodes)}, Total edges: {len(merged_links)}")
        
        metrics = GraphMetrics.generate_metrics(self.workspace_path, all_new_nodes, all_new_links)
        print("Enrichment Metrics:", metrics)
        
        json_path, dot_path, mmd_path = GraphExporter.export(self.workspace_path, merged_nodes, merged_links, hyperedges)
        print(f"Exported enriched graph to:\\n  - {json_path}\\n  - {dot_path}\\n  - {mmd_path}")

if __name__ == "__main__":
    engine = GraphEnrichmentEngine(os.getcwd())
    engine.run()
'''
}

for name, content in files.items():
    with open(os.path.join(base_dir, name), "w", encoding="utf-8") as f:
        f.write(content)

print("Files successfully generated.")
