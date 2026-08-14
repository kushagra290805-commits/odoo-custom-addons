from typing import Dict
from odoo.addons.nexora_studio.services.design_system.design_tokens import DesignTokens

class ThemeSystem:
    """
    Manages the hot-swappable context of DesignTokens (e.g. Light vs Dark mode).
    """
    def __init__(self, base_tokens: DesignTokens):
        self._base_tokens = base_tokens
        self._themes: Dict[str, Dict[str, str]] = {}
        self._active_theme: str = "light"
        
    def register_theme(self, theme_name: str, overrides: Dict[str, str]) -> None:
        """
        Registers a theme as a set of overrides over the base tokens.
        """
        self._themes[theme_name] = overrides
        
    def set_active_theme(self, theme_name: str) -> None:
        if theme_name not in self._themes and theme_name != "base":
            raise ValueError(f"Theme '{theme_name}' is not registered.")
        self._active_theme = theme_name
        
    def resolve_token(self, token_name: str) -> str:
        """
        Resolves a token against the active theme. Falls back to base tokens.
        """
        if self._active_theme in self._themes:
            overrides = self._themes[self._active_theme]
            if token_name in overrides:
                return overrides[token_name]
                
        # Fallback to base
        return self._base_tokens.resolve(token_name)
