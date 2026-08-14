# -*- coding: utf-8 -*-
import logging
import json
from typing import Any, Dict
from .workspace_graph_service import WorkspaceGraphService

_logger = logging.getLogger(__name__)

class DifferenceEngine:
    """
    A structural diff engine that generates both a machine-readable ChangeSet
    and a human-readable Change Summary.
    """

    def generate_changeset(self, current_version: Any, proposed_state: Dict[str, Any]) -> Dict[str, Any]:
        _logger.info("DifferenceEngine generating deep structural changeset.")
        
        current_graph = WorkspaceGraphService(current_version)
        current_tree = current_graph.component_tree
        proposed_tree = proposed_state.get('component_tree_data', {})
        if isinstance(proposed_tree, str):
            proposed_tree = json.loads(proposed_tree)
            
        current_nodes = {n.get("component_id") or n.get("id"): n for n in current_tree.get("nodes", [])}
        proposed_nodes = {n.get("component_id") or n.get("id"): n for n in proposed_tree.get("nodes", [])}
        
        added = [k for k in proposed_nodes if k not in current_nodes]
        removed = [k for k in current_nodes if k not in proposed_nodes]
        updated = [k for k in proposed_nodes if k in current_nodes and proposed_nodes[k] != current_nodes[k]]
        
        current_theme = current_graph.theme
        proposed_theme = proposed_state.get('theme_data', {})
        if isinstance(proposed_theme, str):
            proposed_theme = json.loads(proposed_theme)
            
        theme_changed = current_theme != proposed_theme
        
        # Build human-readable summary
        summary_lines = []
        if added:
            summary_lines.append(f"Added {len(added)} components: {', '.join(added[:3])}{'...' if len(added)>3 else ''}")
        if removed:
            summary_lines.append(f"Removed {len(removed)} components: {', '.join(removed[:3])}{'...' if len(removed)>3 else ''}")
        if updated:
            summary_lines.append(f"Updated {len(updated)} components: {', '.join(updated[:3])}{'...' if len(updated)>3 else ''}")
        if theme_changed:
            summary_lines.append("Modified Global Theme settings.")
            
        if not summary_lines:
            summary_lines.append("No structural changes detected.")
            
        human_summary = " | ".join(summary_lines)
        
        return {
            "changeset": {
                "added_components": added,
                "removed_components": removed,
                "updated_components": updated,
                "theme_changed": theme_changed
            },
            "summary": human_summary
        }
