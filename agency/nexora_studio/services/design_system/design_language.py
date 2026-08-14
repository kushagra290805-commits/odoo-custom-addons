from odoo.addons.nexora_studio.services.design_system.design_system import DesignSystem
from odoo.addons.nexora_studio.services.design_system.component_library import ComponentLibrary
from odoo.addons.nexora_studio.services.design_system.design_validator import DesignValidator
from odoo.addons.nexora_studio.services.design_system.design_translator import DesignTranslator

class DesignLanguage:
    """
    The unified canonical entry point for all design configuration in Nexora Studio.
    Aggregates the DesignSystem, Library, Validator, and Translator.
    """
    def __init__(
        self, 
        design_system: DesignSystem, 
        library: ComponentLibrary, 
        validator: DesignValidator,
        translator: DesignTranslator
    ):
        self.system = design_system
        self.library = library
        self.validator = validator
        self.translator = translator
