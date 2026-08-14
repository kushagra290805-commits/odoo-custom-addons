from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class AssetPlan:
    type: str
    description: str
    
@dataclass
class ComponentPlan:
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class PagePlan:
    name: str
    route: str
    components: List[ComponentPlan] = field(default_factory=list)
    
@dataclass
class WebsitePlan:
    site_type: str
    industry: str
    pages: List[PagePlan] = field(default_factory=list)
    global_assets: List[AssetPlan] = field(default_factory=list)
    theme_requirements: Dict[str, Any] = field(default_factory=dict)
