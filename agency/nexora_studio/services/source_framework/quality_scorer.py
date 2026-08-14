# -*- coding: utf-8 -*-
from typing import Dict, Any
from .domain_models import ComponentPackage

class QualityScorer:
    def score_component(self, component: ComponentPackage) -> float:
        return 0.95
