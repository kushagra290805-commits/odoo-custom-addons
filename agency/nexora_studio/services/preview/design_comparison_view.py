class DesignComparisonView:
    def process(self, before_url: str, after_url: str) -> dict:
        return {"status": "success", "comparison_type": "slider", "left": before_url, "right": after_url}
