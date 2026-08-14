from typing import Dict, Any, Optional
from odoo.addons.nexora_studio.services.design_system.component_library import ComponentLibrary

class DesignTranslator:
    """
    Translates raw AI JSON output into strict, validated DesignLanguage Document structures.
    """
    def __init__(self, library: ComponentLibrary):
        self.library = library
        
    def translate_ast_node(self, ai_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Takes a loosely typed AI suggestion and maps it to a rigid ComponentSchema payload.
        """
        if "type" not in ai_output:
            return None
            
        # The AI might output 'HeroSection' but the strict ID is 'core.organisms.hero'
        # In a real scenario, this involves semantic matching or requiring the AI to use exact IDs.
        component_id = ai_output["type"]
        schema = self.library.get_component(component_id)
        
        if not schema:
            return None # Reject invalid elements
            
        strict_node = {
            "component_id": component_id,
            "properties": {},
            "children": []
        }
        
        # Filter and map properties based on schema
        raw_props = ai_output.get("properties", {})
        for k, v in raw_props.items():
            if k in schema.properties:
                strict_node["properties"][k] = v
                
        # Recursively translate children
        for child in ai_output.get("children", []):
            translated_child = self.translate_ast_node(child)
            if translated_child:
                strict_node["children"].append(translated_child)
                
        return strict_node
