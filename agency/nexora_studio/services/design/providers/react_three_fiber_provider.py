# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
import logging
from .react_provider import ReactRenderingProvider
from .rendering_provider import ProviderMetadata, RenderingContext

_logger = logging.getLogger(__name__)

class ReactThreeFiberProvider(ReactRenderingProvider):
    """
    Renders React Three Fiber components.
    Overrides standard React provider metadata and applies strict R3F validations.
    """

    def get_metadata(self) -> ProviderMetadata:
        from .provider_registry import RenderingProviderRegistry
        # Retrieve the pre-defined metadata stub for react_three_fiber
        return RenderingProviderRegistry.get_provider_metadata("react_three_fiber")

    def validate_project(self, context: RenderingContext, project_structure: Dict[str, str]) -> Dict[str, Any]:
        """
        Extends the standard React validate_project to ensure R3F compliance.
        """
        # First, run the base React validation (which now checks the provider mode)
        base_result = super().validate_project(context, project_structure)
        errors = base_result.get("errors", [])
        
        # Verify valid R3F imports, reject invalid ones
        has_r3f = False
        has_three = False
        for filepath, code in project_structure.items():
            if not (filepath.endswith('.jsx') or filepath.endswith('.js')):
                continue
            
            code_lower = code.lower()
            if "import " in code_lower:
                if "@react-three/fiber" in code_lower:
                    has_r3f = True
                if "three" in code_lower and "three" not in filepath.lower():
                    has_three = True
                # Safeguard: reject known unapproved 3D engines (peers like Spline are allowed)
                if "playcanvas" in code_lower or "babylon" in code_lower:
                    errors.append(f"Unapproved 3D dependency found in {filepath}. Only three, @react-three/fiber, @react-three/drei are permitted in R3F mode.")

        # In R3F mode, we expect at least some 3D dependencies to be present in package.json or source
        pkg_json = project_structure.get('package.json', '')
        if pkg_json and ('"three"' not in pkg_json and '"@react-three/fiber"' not in pkg_json):
            errors.append("package.json is missing required R3F dependencies ('three' or '@react-three/fiber').")

        return {
            "valid": len(errors) == 0,
            "files_checked": len(project_structure),
            "errors": errors,
        }
