# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from .domain_models import ComponentPackage

class MetadataNormalizer:
    def normalize_list(self, raw_components: List[ComponentPackage]) -> List[ComponentPackage]:
        return raw_components
