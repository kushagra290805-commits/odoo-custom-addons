from typing import Dict, Any
from odoo.addons.nexora_studio.services.generation.workflows.planning.models import WebsitePlan, PagePlan, ComponentPlan, AssetPlan

class PlanningWorkflow:
    """
    Generates Site Architecture, Navigation, Page Hierarchy.
    """
    def plan(self, analyzed_requirements: Dict[str, Any]) -> WebsitePlan:
        # Mock mapping requirements to a Plan
        pages = []
        for p in analyzed_requirements.get("required_pages", []):
            pages.append(PagePlan(name=p, route=f"/{p}", components=[
                ComponentPlan(type="header"),
                ComponentPlan(type="hero")
            ]))
            
        return WebsitePlan(
            site_type=analyzed_requirements.get("website_type", "unknown"),
            industry=analyzed_requirements.get("industry", "unknown"),
            pages=pages,
            theme_requirements={"color_scheme": "dark"}
        )
