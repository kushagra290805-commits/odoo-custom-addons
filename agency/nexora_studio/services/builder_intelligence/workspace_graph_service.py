# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict, Any, List, Optional

_logger = logging.getLogger(__name__)

class WorkspaceGraphService:
    """
    Provides reusable traversal and mutation across the builder workspace version payloads
    for Builder Intelligence engines.
    """
    def __init__(self, workspace_version_record: Any = None):
        self.version = workspace_version_record
        if workspace_version_record:
            try:
                self.component_tree = json.loads(self.version.component_tree_data or '{}')
                self.theme = json.loads(self.version.theme_data or '{}')
                self.assets = json.loads(self.version.assets_data or '{}')
                self.content = json.loads(self.version.content_data or '{}')
                self.layout = json.loads(self.version.layout_data or '{}')
            except Exception as e:
                _logger.error(f"Failed to parse workspace version JSON: {e}")
                self._init_empty()
        else:
            self._init_empty()

    def _init_empty(self):
        self.component_tree = {"nodes": [], "dependencies": []}
        self.theme = {}
        self.assets = {}
        self.content = {}
        self.layout = {}

    def get_component_node(self, component_id: str) -> Optional[Dict[str, Any]]:
        nodes = self.component_tree.get("nodes", [])
        for node in nodes:
            if node.get("component_id") == component_id or node.get("id") == component_id:
                return node
        return None

    def get_components_by_type(self, component_type: str) -> List[Dict[str, Any]]:
        nodes = self.component_tree.get("nodes", [])
        return [n for n in nodes if component_type in n.get("component_id", "").lower() or component_type in n.get("type", "").lower()]

    def get_dependencies(self) -> List[str]:
        return self.component_tree.get("dependencies", [])

    def get_parent(self, node_id: str) -> Optional[Dict[str, Any]]:
        node = self.get_component_node(node_id)
        if not node:
            return None
        parent_id = node.get("parent_id")
        if not parent_id:
            return None
        return self.get_component_node(parent_id)

    def get_children(self, parent_id: str) -> List[Dict[str, Any]]:
        nodes = self.component_tree.get("nodes", [])
        return [n for n in nodes if n.get("parent_id") == parent_id]
        
    def traverse_subtree(self, root_id: str) -> List[Dict[str, Any]]:
        result = []
        children = self.get_children(root_id)
        for child in children:
            result.append(child)
            result.extend(self.traverse_subtree(child.get("id") or child.get("component_id")))
        return result

    def get_asset_by_id(self, asset_id: str) -> Optional[Dict[str, Any]]:
        for cat in ["images", "icons", "fonts", "videos"]:
            for asset in self.assets.get(cat, []):
                if asset.get("id") == asset_id:
                    return asset
        return None

    def get_layout_hierarchy(self) -> Dict[str, Any]:
        return self.layout.get("hierarchy", {})

    def get_page_content(self, path: str) -> Optional[Dict[str, Any]]:
        return self.content.get("pages", {}).get(path)
        
    def serialize(self) -> Dict[str, str]:
        return {
            'component_tree_data': json.dumps(self.component_tree),
            'theme_data': json.dumps(self.theme),
            'assets_data': json.dumps(self.assets),
            'content_data': json.dumps(self.content),
            'layout_data': json.dumps(self.layout)
        }
        
    def add_node(self, node: Dict[str, Any]):
        if "nodes" not in self.component_tree:
            self.component_tree["nodes"] = []
        self.component_tree["nodes"].append(node)
        
    def remove_node(self, node_id: str):
        if "nodes" in self.component_tree:
            self.component_tree["nodes"] = [n for n in self.component_tree["nodes"] if n.get("component_id") != node_id and n.get("id") != node_id]
            
    def update_node(self, node_id: str, new_node: Dict[str, Any]):
        for idx, n in enumerate(self.component_tree.get("nodes", [])):
            if n.get("component_id") == node_id or n.get("id") == node_id:
                self.component_tree["nodes"][idx] = new_node
                break

