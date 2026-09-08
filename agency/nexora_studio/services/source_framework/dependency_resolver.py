# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from .domain_models import ComponentPackage

class DependencyResolver:
    def resolve_graph(self, component: ComponentPackage) -> ComponentPackage:
        # Dependency acquisition is source-owned. Preserve factual package
        # dependencies; do not append synthetic entries during federation.
        return component
