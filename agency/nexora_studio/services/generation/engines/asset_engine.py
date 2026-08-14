import logging
from typing import Any, List, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Assets
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet

_logger = logging.getLogger(__name__)

class AssetEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing AssetEngine (Deterministic)...")
        
        req = artifact.requirements
        
        # 1. Deterministic calculation of required assets from architecture
        required_images = []
        required_icons = set()
        
        for comp in artifact.component_tree.nodes:
            ctype = comp.get("component_id", "").lower()
            if ctype == "hero": required_images.append(f"hero_bg_{req.domain.lower()}")
            if ctype == "features":
                required_icons.add("zap")
                required_icons.add("shield")
            if ctype == "nav":
                required_icons.add("menu")
                
        images = []
        icons = []
        seen_assets = set()
        features = ProviderFeatureSet(supports_json_mode=False)
        
        # 2. Re-use existing / Deduplicate / Optimize
        for img_id in required_images:
            if img_id in seen_assets: continue
            seen_assets.add(img_id)
            
            # Use Asset Bridge Provider
            try:
                # In production, this might fetch from an internal stock library or generate
                res = self.orchestrator.execute(ProviderCategory.ASSET, "optimize_asset", {"content": f"<svg id='{img_id}'></svg>"}, features)
                content = res.data.get("content", f"<svg id='{img_id}'></svg>") if res.success else f"<svg id='{img_id}'></svg>"
                
                images.append({
                    "id": img_id,
                    "format": "svg",
                    "content": content,
                    "metadata": {"alt": f"{img_id.replace('_', ' ')}", "ownership": "nexora_generated"}
                })
            except Exception as e:
                _logger.warning(f"Asset bridge failure for {img_id}: {str(e)}")
                
        for icon in required_icons:
            if icon in seen_assets: continue
            seen_assets.add(icon)
            
            icons.append({
                "id": icon,
                "format": "svg",
                "content": f"<svg data-lucide='{icon}'></svg>",
                "metadata": {"ownership": "lucide-react"}
            })
            
        model = Assets(
            images=images,
            icons=icons,
            fonts=[{"family": "Inter", "weights": [400, 500, 700], "metadata": {"ownership": "google_fonts"}}]
        )
        return EngineExecutionResult(success=True, artifact=artifact.evolve(assets=model), metadata={}, error=None)
