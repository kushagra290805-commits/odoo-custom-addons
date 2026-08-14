class AssetPreviewPipeline:
    def process(self, asset_url: str) -> dict:
        return {"status": "success", "artifact_url": asset_url, "preview_type": "image"}
