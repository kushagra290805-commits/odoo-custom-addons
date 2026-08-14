# -*- coding: utf-8 -*-
from typing import Dict, Any
from .domain_models import ComponentPackage

class CompatibilityChecker:
    def validate_context(self, component: ComponentPackage, builder_context: Dict[str, Any]) -> ComponentPackage:
        component.compatibility_report = {
            "is_compatible": True,
            "warnings": []
        }
        return component
