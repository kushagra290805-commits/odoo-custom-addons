from typing import List
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
