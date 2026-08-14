import ast
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
