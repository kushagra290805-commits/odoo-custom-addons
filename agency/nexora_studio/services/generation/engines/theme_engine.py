import logging
from typing import Any, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Theme

_logger = logging.getLogger(__name__)

def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3: hex_color = ''.join(c + c for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def luminance(r: int, g: int, b: int) -> float:
    a = [v / 255 for v in (r, g, b)]
    a = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in a]
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722

def contrast_ratio(hex1: str, hex2: str) -> float:
    try:
        l1 = luminance(*hex_to_rgb(hex1))
        l2 = luminance(*hex_to_rgb(hex2))
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
    except:
        return 1.0

class ThemeEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ThemeEngine (Delegating to DesignIntelligenceEngine)...")
        # In Phase B, the modular blueprint is created upstream by PlanningEngine 
        # and stored in generation_metadata.
        modular_blueprint_dict = artifact.generation_metadata.get("modular_blueprint", {})
        
        try:
            # We construct a mock object or extract dict fields to satisfy Theme mapping
            # (Until ThemeEngine itself is fully migrated)
            design = modular_blueprint_dict.get("design", {})
            design_lang = design.get("language", "minimal")
            
            metadata = {}
            # Simple translation logic
            colors = {
                "primary": "#3b82f6",
                "secondary": "#64748b",
                "background": "#000000" if design_lang in ["dark_neon", "premium_minimal"] else "#ffffff",
                "text": "#ffffff" if design_lang in ["dark_neon", "premium_minimal"] else "#0f172a",
                "accent": "#f59e0b"
            }
            
            model = Theme(
                design_tokens={"version": "1.0", "prefix": "nx-"},
                typography_scale={
                    "h1": "2.25rem", "h2": "1.875rem", "h3": "1.5rem", "h4": "1.25rem",
                    "body": "1rem", "small": "0.875rem"
                },
                spacing_system={
                    "0": "0", "1": "0.25rem", "2": "0.5rem", "4": "1rem", "8": "2rem", "16": "4rem"
                },
                colors=colors,
                radius="0.375rem",
                shadows="0 4px 6px -1px rgb(0 0 0 / 0.1)",
                motion={
                    "fast": "150ms ease-in-out",
                    "normal": "300ms ease-in-out",
                    "slow": "500ms ease-in-out"
                }
            )
            
            return EngineExecutionResult(success=True, artifact=artifact.evolve(theme=model), metadata=metadata, error=None)
            
        except Exception as e:
            _logger.error(f"ThemeEngine delegation failed: {e}")
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=str(e))
