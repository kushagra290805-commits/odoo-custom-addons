# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from .domain_models import ComponentPackage

class DependencyResolver:
    def resolve_graph(self, component: ComponentPackage) -> ComponentPackage:
        component.dependencies.append({"resolved": True})
        return component
