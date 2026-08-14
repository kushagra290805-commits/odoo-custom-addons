import logging
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, ArchitectureModel

_logger = logging.getLogger(__name__)

class ArchitectureEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ArchitectureEngine (Validating and Normalizing upstream modular blueprint)...")
        
        # 1. Consume Canonical Modular Blueprint
        modular_blueprint_dict = artifact.generation_metadata.get("modular_blueprint")
        if not modular_blueprint_dict:
            _logger.error("Modular WebsiteBlueprint missing from generation_metadata. Upstream PlanningEngine failed.")
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error="Missing modular blueprint")
            
        try:
            layout_bp = modular_blueprint_dict.get("layout", {})
            technology_bp = modular_blueprint_dict.get("technology", {})
            design_bp = modular_blueprint_dict.get("design", {})
            
            layout_strategy = layout_bp.get("strategy", "grid")
            hierarchy = layout_bp.get("hierarchy", ["/"])
            
            # 2. Deterministic Responsive Behavior derived from modular_blueprint
            responsive_behavior = {
                "mobile": "stack",
                "tablet": "wrap",
                "desktop": "grid_or_flex" if layout_strategy in ["grid", "bento"] else "block",
                "breakpoints": {
                    "sm": "640px",
                    "md": "768px",
                    "lg": "1024px",
                    "xl": "1280px"
                }
            }
            
            # 3. Design System Boundaries
            tech_stack = technology_bp.get("allowed_stacks", [])
            design_system = " + ".join(tech_stack) if tech_stack else "TailwindCSS + React"
            
            # 4. Component Hierarchy (Normalized from flat route hierarchy)
            component_hierarchy = {}
            relationships = []
            
            # Root layout wrapper
            component_hierarchy["layout_root"] = {
                "type": "wrapper",
                "children": ["site_header", "page_content", "site_footer"]
            }
            
            for path in hierarchy:
                # Handle layout_root which may be in hierarchy
                if path == "layout_root": continue
                page_id = f"page_{path.replace('/', '_').strip('_') or 'home'}"
                
                # We no longer rely on legacy content_map. The CodeGenerationEngine 
                # will use ComponentIntelligence to decide sections. We just scaffold pages.
                component_hierarchy[page_id] = {
                    "type": "page",
                    "path": path,
                    "sections": ["Hero", "Content"] # Abstract placeholder for file generation planner
                }
                relationships.append({
                    "from": "layout_root",
                    "to": page_id,
                    "type": "contains"
                })
                
            model = ArchitectureModel(
                layout_strategy=layout_strategy,
                responsive_behavior=responsive_behavior,
                design_system=design_system,
                component_hierarchy=component_hierarchy,
                relationships=relationships
            )
            return EngineExecutionResult(success=True, artifact=artifact.evolve(architecture=model), metadata={"architecture_normalized": True}, error=None)
            
        except Exception as e:
            _logger.error(f"ArchitectureEngine failed to normalize modular blueprint: {str(e)}", exc_info=True)
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=f"Architecture normalization failed: {str(e)}")
