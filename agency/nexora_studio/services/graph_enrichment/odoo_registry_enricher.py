import ast
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
