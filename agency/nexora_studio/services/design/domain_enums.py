# -*- coding: utf-8 -*-
"""
Domain Enums — Authoritative definitions for Component Categories and Page Archetypes.

Centralizes string definitions across planning, rendering, and validation layers to
prevent duplication and enforce strict type safety while maintaining backwards
compatibility with legacy string inputs.
"""
from enum import Enum
from typing import Optional, Any


class ComponentCategory(str, Enum):
    """
    Authoritative enumeration of UI section and component categories.
    """
    # Core UI Sections
    HERO = "hero"
    NAVBAR = "navbar"
    FOOTER = "footer"
    PRICING = "pricing"
    FEATURES = "features"
    TESTIMONIALS = "testimonials"
    FAQ = "faq"
    
    # Archetype-Specific Sections
    DASHBOARD = "dashboard"
    FORMS = "forms"
    BLOG = "blog"
    ECOMMERCE = "ecommerce"
    CONTACT = "contact"
    AUTH = "auth"
    
    # Interactive / Organism Components
    MODAL = "modal"
    ACCORDION = "accordion"
    TABS = "tabs"
    CARD = "card"
    BUTTON = "button"
    
    # Token / System / General Categories
    GENERAL = "general"
    BRAND = "brand"
    NEUTRAL = "neutral"
    SYSTEM = "system"
    LAYOUT = "layout"
    COLOR = "color"
    TYPOGRAPHY = "typography"
    SPACING = "spacing"
    CUSTOM = "custom"

    @classmethod
    def from_str(cls, value: Any, default: Optional['ComponentCategory'] = None) -> 'ComponentCategory':
        """
        Safely parse any string or enum input into a valid ComponentCategory member.
        Returns default (or GENERAL) if input does not match any known category.
        """
        if isinstance(value, cls):
            return value
        if not value:
            return default or cls.GENERAL
        
        val_str = str(value).lower().strip()
        for member in cls:
            if member.value == val_str or member.name.lower() == val_str:
                return member
                
        return default or cls.GENERAL


class PageArchetype(str, Enum):
    """
    Authoritative enumeration of the 6 canonical application page archetypes.
    """
    LANDING = "landing"
    SAAS_DASHBOARD = "saas_dashboard"
    BLOG = "blog"
    ECOMMERCE = "ecommerce"
    CONTACT = "contact"
    AUTH = "auth"

    @classmethod
    def from_str(cls, value: Any, default: Optional['PageArchetype'] = None) -> 'PageArchetype':
        """
        Safely parse any string or enum input into a valid PageArchetype member.
        Returns default (or LANDING) if input does not match any canonical archetype.
        """
        if isinstance(value, cls):
            return value
        if not value:
            return default or cls.LANDING
            
        val_str = str(value).lower().strip()
        for member in cls:
            if member.value == val_str or member.name.lower() == val_str:
                return member
                
        return default or cls.LANDING
