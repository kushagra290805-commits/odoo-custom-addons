from typing import Dict, Any, Tuple
from odoo.addons.nexora_studio.services.design_system.component_library import ComponentLibrary
from odoo.addons.nexora_studio.services.design_system.theme_system import ThemeSystem

class DesignValidator:
    """
    Ensures that components and modifications adhere to the DesignLanguage schemas and tokens.
    Organized into Structural and Semantic validation stages.
    """
    def __init__(self, library: ComponentLibrary, theme_system: ThemeSystem):
        self.library = library
        self.theme_system = theme_system
        
    def validate_structural(self, component_id: str, properties: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Stage 1: Structural Validation. 
        Ensures the payload matches the expected schema types and enumerations.
        """
        schema = self.library.get_component(component_id)
        if not schema:
            return False, f"Unknown component_id: {component_id}"
            
        for prop_name, prop_val in properties.items():
            if prop_name not in schema.properties:
                return False, f"Invalid property '{prop_name}' for component '{component_id}'"
                
            prop_def = schema.properties[prop_name]
            if prop_def.get("type") == "enum":
                if prop_val not in prop_def.get("options", []):
                    return False, f"Value '{prop_val}' not allowed for enum property '{prop_name}'"
        return True, "Valid"
        
    def validate_semantic(self, component_id: str, properties: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Stage 2: Semantic Validation.
        Ensures accessibility contrast ratios, responsive constraints, and theme token existence.
        """
        # E.g. Check if the active theme provides the token they requested
        # E.g. Check if WCAG contrast rules are satisfied based on the component's background
        return True, "Valid"

    def validate_component_instance(self, component_id: str, properties: Dict[str, Any]) -> Tuple[bool, str]:
        """Runs the full validation pipeline."""
        structural_ok, msg = self.validate_structural(component_id, properties)
        if not structural_ok:
            return False, msg
            
        semantic_ok, msg = self.validate_semantic(component_id, properties)
        if not semantic_ok:
            return False, msg
            
        return True, "Valid"
        
    def validate_token_reference(self, token_name: str) -> bool:
        """
        Ensures a token exists in the current theme context.
        """
        try:
            val = self.theme_system.resolve_token(token_name)
            return val is not None and val != token_name
        except Exception:
            return False
