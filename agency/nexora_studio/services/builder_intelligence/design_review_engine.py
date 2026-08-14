# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict
from odoo.addons.nexora_studio.services.design.design_blueprint import DesignBlueprint
from odoo.addons.nexora_studio.services.design.design_system_validator import DesignSystemValidator
from odoo.addons.nexora_studio.services.design.layout_validator import LayoutValidator

_logger = logging.getLogger(__name__)

class DesignReviewEngine:
    """
    Automatic review after every modification.
    Transforms WorkspaceGraphService into DesignBlueprint and runs validators.
    """

    def evaluate_graph(self, graph_service: Any) -> Dict[str, Any]:
        _logger.info("DesignReviewEngine evaluating graph via DesignBlueprint.")
        
        # Translate JSON components to Blueprint structure
        pages = []
        for node in graph_service.component_tree.get("nodes", []):
            if node.get("type", "").lower() == "page":
                pages.append({"page_id": node.get("id"), "components": graph_service.get_children(node.get("id"))})
                
        # If no explicit page nodes exist, assume all root nodes belong to a default page
        if not pages:
            pages.append({
                "page_id": "default", 
                "components": [n for n in graph_service.component_tree.get("nodes", []) if not n.get("parent_id")]
            })
            
        bp_dict = {
            "project_name": "Review Blueprint",
            "project_id": "review",
            "theme": graph_service.theme,
            "pages": pages
        }
        
        # Parse deeply and load into DesignBlueprint
        bp = DesignBlueprint.from_dict(bp_dict)
        
        ds_val = DesignSystemValidator.validate(bp)
        ly_val = LayoutValidator.validate(bp)
        
        return {
            "is_valid": ds_val.is_valid and ly_val.is_valid,
            "accessibility_score": getattr(ly_val.quality_score, 'accessibility_score', 100) if getattr(ly_val, 'quality_score', None) else 100,
            "responsive_score": getattr(ly_val.quality_score, 'responsive_score', 100) if getattr(ly_val, 'quality_score', None) else 100,
            "errors": ds_val.errors + ly_val.errors,
            "warnings": ds_val.warnings + ly_val.warnings
        }
