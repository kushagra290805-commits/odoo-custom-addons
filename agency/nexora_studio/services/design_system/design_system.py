from odoo.addons.nexora_studio.services.design_system.design_tokens import DesignTokens
from odoo.addons.nexora_studio.services.design_system.theme_system import ThemeSystem
from typing import Dict, Any

class DesignSystem:
    """
    Manages the global aesthetic rules of a project.
    Aggregates Tokens, Themes, and Global Rules.
    """
    def __init__(self, tokens: DesignTokens, theme_system: ThemeSystem):
        self.tokens = tokens
        self.themes = theme_system
        self._global_rules: Dict[str, Any] = {
            "typography": {},
            "breakpoints": {
                "mobile": 320,
                "tablet": 768,
                "desktop": 1024
            }
        }
        
    def set_global_rule(self, rule_key: str, config: Any) -> None:
        self._global_rules[rule_key] = config
        
    def get_global_rule(self, rule_key: str) -> Any:
        return self._global_rules.get(rule_key)
        
    def resolve_style(self, token_name: str) -> str:
        """Helper to get the current themed value for a given token."""
        return self.themes.resolve_token(token_name)
