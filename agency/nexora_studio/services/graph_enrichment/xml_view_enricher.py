import os
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
