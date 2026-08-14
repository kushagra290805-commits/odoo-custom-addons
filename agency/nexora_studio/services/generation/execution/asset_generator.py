from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.provider_registry import ProviderRegistry

class AssetGenerator:
    """
    Generates media (Images, Icons). Interfaces with ProviderRegistry and AssetPipeline.
    """
    def __init__(self, provider_registry: ProviderRegistry, asset_pipeline: Any):
        self.providers = provider_registry
        self.pipeline = asset_pipeline
        
    def generate_asset(self, asset_type: str, prompt: str) -> str:
        """Returns the asset://UUID"""
        if asset_type in ["image", "illustration", "logo"]:
            provider = self.providers.get_provider("image_generation")
            if not provider:
                raise RuntimeError("No image generation provider registered.")
                
            raw_data = provider.generate_image(prompt)
            metadata = {
                "provider": "image_generation",
                "source": "ai",
                "checksum": "mock_hash",
                "mime_type": "image/png",
                "dimensions": "1024x1024",
                "license": "generated",
                "version": "1.0",
                "generated_by": "nexora_ai",
                "created_at": "now",
                "content_hash": "hash"
            }
            asset_id = self.pipeline.upload_asset(raw_data, asset_type, metadata)
            return asset_id
        return ""
