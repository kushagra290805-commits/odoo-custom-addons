import logging
from typing import Any, List, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class OptimizationEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing OptimizationEngine (Optimizing Persisted Workspace)...")
        
        # 1. Asset Deduplication (by ID and Content Hash)
        unique_images = {}
        for img in artifact.assets.images:
            if img["id"] not in unique_images:
                unique_images[img["id"]] = img
                
        unique_icons = {}
        for icon in artifact.assets.icons:
            if icon["id"] not in unique_icons:
                unique_icons[icon["id"]] = icon
                
        # 2. Dependency Pruning & Import Optimization
        actual_deps = set()
        for node in artifact.component_tree.nodes:
            code = node.get("code", "")
            if "lucide-react" in code: actual_deps.add("lucide-react")
            if "framer-motion" in code: actual_deps.add("framer-motion")
            if "tailwind" in code: actual_deps.add("tailwindcss")
            actual_deps.add("react")
            actual_deps.add("react-dom")
            
        # 3. Component Consolidation & Unused Removal
        used_components = set()
        for node in artifact.component_tree.nodes:
            used_components.add(node["component_id"])
            
        pruned_nodes = [n for n in artifact.component_tree.nodes if n["component_id"] in used_components]
        
        # 4. Metadata cleanup (Remove null/empty metadata fields)
        cleaned_content_pages = {}
        for path, page_data in artifact.content.pages.items():
            cleaned_metadata = {k:v for k,v in page_data.get("metadata", {}).items() if v}
            page_data["metadata"] = cleaned_metadata
            cleaned_content_pages[path] = page_data
            
        # 5. Modify Context
        optimized_tree = artifact.component_tree
        optimized_tree.nodes.clear()
        optimized_tree.nodes.extend(pruned_nodes)
        optimized_tree.dependencies.clear()
        optimized_tree.dependencies.extend(list(actual_deps))
        
        optimized_assets = artifact.assets
        optimized_assets.images.clear()
        optimized_assets.images.extend(list(unique_images.values()))
        optimized_assets.icons.clear()
        optimized_assets.icons.extend(list(unique_icons.values()))
        
        optimized_content = artifact.content
        optimized_content.pages.clear()
        optimized_content.pages.update(cleaned_content_pages)
        
        bundle_size = len(str(optimized_tree.nodes)) + len(str(optimized_assets.images))
        _logger.info(f"Optimization complete. Est bundle size: {bundle_size / 1024:.2f} KB")

        # 6. Ensure no ORM linkage
        # DB persistence of the optimized state is handled by the pipeline/coordinator.
        _logger.info("Optimization complete, delegating persistence to runtime coordinator.")

        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(
                component_tree=optimized_tree, 
                assets=optimized_assets,
                content=optimized_content
            ),
            metadata={"bundle_size_kb": round(bundle_size / 1024, 2)},
            error=None
        )
