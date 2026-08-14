# -*- coding: utf-8 -*-
"""
Component Manifest Layer — Phase 12B: React Component Library & Design System Integration.

Introduces a provider-neutral Component Manifest between the Render Model and rendering code synthesizers:
    Render Model -> Component Manifest -> React Component Library

Strict Architectural Governance (ADR-0035 & ADR-0038):
- This module must remain 100% framework-agnostic.
- Does NOT reference JSX, React, Vue, HTML string templates, or framework-specific rendering syntax.
- Authoritatively describes component types, structured props schemas, slots, variants, design token bindings,
  accessibility metadata, and responsive behavior for all 25 core library components and custom sections.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import uuid


@dataclass
class ComponentManifestEntry:
    """
    Framework-agnostic manifest specification for a single UI component or primitive.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    component_type: str = ""                         # e.g., 'Button', 'Hero', 'Navbar', 'Card', 'Table'
    category: str = "primitive"                      # 'primitive', 'molecule', 'organism', 'section'
    description: str = ""
    props_schema: Dict[str, Any] = field(default_factory=dict)       # e.g., {'variant': {'type': 'string', 'default': 'primary'}}
    slots: List[str] = field(default_factory=list)                   # e.g., ['children', 'icon', 'badge', 'footer', 'header']
    variants: List[str] = field(default_factory=list)                # e.g., ['primary', 'secondary', 'outline', 'ghost', 'link']
    design_token_bindings: Dict[str, str] = field(default_factory=dict)  # e.g., {'color': 'var(--color-primary)', 'radius': 'var(--radius-md)'}
    accessibility_metadata: Dict[str, Any] = field(default_factory=dict) # e.g., {'role': 'button', 'keyboard_navigable': True, 'semantic_tag': 'button'}
    responsive_behavior: Dict[str, Any] = field(default_factory=dict)    # e.g., {'mobile': {'stack': True, 'width': '100%'}}
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentManifestEntry':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            component_type=data.get('component_type', ''),
            category=data.get('category', 'primitive'),
            description=data.get('description', ''),
            props_schema=data.get('props_schema', {}),
            slots=data.get('slots', []),
            variants=data.get('variants', []),
            design_token_bindings=data.get('design_token_bindings', {}),
            accessibility_metadata=data.get('accessibility_metadata', {}),
            responsive_behavior=data.get('responsive_behavior', {}),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'component_type': self.component_type,
            'category': self.category,
            'description': self.description,
            'props_schema': self.props_schema,
            'slots': self.slots,
            'variants': self.variants,
            'design_token_bindings': self.design_token_bindings,
            'accessibility_metadata': self.accessibility_metadata,
            'responsive_behavior': self.responsive_behavior,
            'metadata': self.metadata
        }


@dataclass
class ComponentManifest:
    """
    Authoritative catalog of all UI component manifest entries for a project.
    Provides the standard 25 core component definitions plus dynamic section entries from the RenderModel.
    """
    project_id: str = ""
    project_name: str = ""
    version: str = "1.0.0"
    entries: Dict[str, ComponentManifestEntry] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentManifest':
        if not data:
            return cls()
        entries = {}
        for k, v in data.get('entries', {}).items():
            entries[k] = ComponentManifestEntry.from_dict(v) if isinstance(v, dict) else v
        return cls(
            project_id=data.get('project_id', ''),
            project_name=data.get('project_name', ''),
            version=data.get('version', '1.0.0'),
            entries=entries,
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'project_id': self.project_id,
            'project_name': self.project_name,
            'version': self.version,
            'entries': {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.entries.items()},
            'metadata': self.metadata
        }

    @classmethod
    def create_default_manifest(cls, project_id: str = "default", project_name: str = "Nexora Components") -> 'ComponentManifest':
        """
        Creates an authoritative, framework-agnostic ComponentManifest containing the 25 core library components
        with complete Variant Intelligence, Accessibility Metadata, and Design Token Bindings.
        """
        manifest = cls(project_id=project_id, project_name=project_name, version="1.0.0")

        # 1. Button (Primitive)
        manifest.entries['Button'] = ComponentManifestEntry(
            component_type='Button',
            category='primitive',
            description='Interactive trigger element supporting multiple visual variants and sizes.',
            props_schema={
                'variant': {'type': 'string', 'default': 'primary', 'options': ['primary', 'secondary', 'outline', 'ghost', 'link']},
                'size': {'type': 'string', 'default': 'md', 'options': ['sm', 'md', 'lg']},
                'disabled': {'type': 'boolean', 'default': False},
                'href': {'type': 'string', 'default': None},
                'onClick': {'type': 'function', 'default': None}
            },
            slots=['children', 'iconLeft', 'iconRight'],
            variants=['primary', 'secondary', 'outline', 'ghost', 'link'],
            design_token_bindings={
                'background_primary': 'var(--color-primary, #3b82f6)',
                'background_secondary': 'var(--color-secondary, #64748b)',
                'text_color': 'var(--color-text, #f8fafc)',
                'radius': 'var(--radius-md, 6px)',
                'padding_md': '0.625rem 1.25rem',
                'font_family': 'var(--font-body, sans-serif)'
            },
            accessibility_metadata={
                'semantic_tag': 'button_or_a',
                'role': 'button',
                'keyboard_navigable': True,
                'focus_visible': 'outline: 2px solid var(--color-primary, #3b82f6); outline-offset: 2px;',
                'aria_disabled': 'bound_to_disabled_prop'
            },
            responsive_behavior={
                'mobile': {'width': '100%_when_stacked', 'padding': '0.75rem 1.5rem'},
                'desktop': {'width': 'auto'}
            }
        )

        # 2. Badge (Primitive)
        manifest.entries['Badge'] = ComponentManifestEntry(
            component_type='Badge',
            category='primitive',
            description='Compact visual indicator for status, category, or counts.',
            props_schema={
                'variant': {'type': 'string', 'default': 'default', 'options': ['default', 'success', 'warning', 'error', 'info']},
                'size': {'type': 'string', 'default': 'sm', 'options': ['sm', 'md']}
            },
            slots=['children'],
            variants=['default', 'success', 'warning', 'error', 'info'],
            design_token_bindings={
                'background': 'var(--color-surface, rgba(255,255,255,0.1))',
                'radius': 'var(--radius-full, 9999px)',
                'font_size': '0.75rem',
                'font_weight': '600'
            },
            accessibility_metadata={
                'semantic_tag': 'span',
                'role': 'status',
                'keyboard_navigable': False,
                'aria_label': 'Status badge'
            }
        )

        # 3. Avatar (Primitive)
        manifest.entries['Avatar'] = ComponentManifestEntry(
            component_type='Avatar',
            category='primitive',
            description='User or entity visual profile representation with fallback initials.',
            props_schema={
                'src': {'type': 'string', 'default': ''},
                'alt': {'type': 'string', 'default': 'User Avatar'},
                'size': {'type': 'string', 'default': 'md', 'options': ['sm', 'md', 'lg', 'xl']},
                'fallback': {'type': 'string', 'default': 'U'}
            },
            slots=['fallback'],
            variants=['circle', 'square'],
            design_token_bindings={
                'radius': 'var(--radius-full, 50%)',
                'background': 'var(--color-secondary, #64748b)',
                'border': '2px solid rgba(255,255,255,0.1)'
            },
            accessibility_metadata={
                'semantic_tag': 'img_or_span',
                'role': 'img',
                'alt_required': True,
                'keyboard_navigable': False
            }
        )

        # 4. Alert (Primitive)
        manifest.entries['Alert'] = ComponentManifestEntry(
            component_type='Alert',
            category='primitive',
            description='Contextual feedback message box for user notifications.',
            props_schema={
                'variant': {'type': 'string', 'default': 'info', 'options': ['info', 'success', 'warning', 'error']},
                'title': {'type': 'string', 'default': ''},
                'onClose': {'type': 'function', 'default': None}
            },
            slots=['children', 'icon', 'action'],
            variants=['info', 'success', 'warning', 'error'],
            design_token_bindings={
                'radius': 'var(--radius-md, 8px)',
                'padding': 'var(--spacing-md, 1rem)',
                'border': '1px solid rgba(255,255,255,0.15)'
            },
            accessibility_metadata={
                'semantic_tag': 'div',
                'role': 'alert',
                'aria_live': 'polite',
                'keyboard_navigable': True
            }
        )

        # 5. Breadcrumb (Primitive)
        manifest.entries['Breadcrumb'] = ComponentManifestEntry(
            component_type='Breadcrumb',
            category='primitive',
            description='Hierarchical navigation trail indicating current page location.',
            props_schema={
                'items': {'type': 'list', 'default': []},
                'separator': {'type': 'string', 'default': '/'}
            },
            slots=['separator'],
            variants=['default', 'slash', 'chevron'],
            design_token_bindings={
                'text_color': 'var(--color-text, #f8fafc)',
                'text_muted': 'var(--color-text-muted, #94a3b8)',
                'spacing': '0.5rem'
            },
            accessibility_metadata={
                'semantic_tag': 'nav',
                'role': 'navigation',
                'aria_label': 'Breadcrumb',
                'keyboard_navigable': True
            }
        )

        # 6. Pagination (Primitive)
        manifest.entries['Pagination'] = ComponentManifestEntry(
            component_type='Pagination',
            category='primitive',
            description='Page navigation controls for data lists or grids. Composes Button.',
            props_schema={
                'currentPage': {'type': 'number', 'default': 1},
                'totalPages': {'type': 'number', 'default': 1},
                'onPageChange': {'type': 'function', 'default': None}
            },
            slots=['prevButton', 'nextButton', 'pageNumbers'],
            variants=['standard', 'compact'],
            design_token_bindings={
                'spacing': '0.25rem',
                'radius': 'var(--radius-md, 6px)'
            },
            accessibility_metadata={
                'semantic_tag': 'nav',
                'role': 'navigation',
                'aria_label': 'Pagination Navigation',
                'keyboard_navigable': True
            }
        )

        # 7. Modal (Primitive/Overlay)
        manifest.entries['Modal'] = ComponentManifestEntry(
            component_type='Modal',
            category='primitive',
            description='Accessible dialog window overlaying main page content. Composes Card and Button.',
            props_schema={
                'isOpen': {'type': 'boolean', 'default': False},
                'title': {'type': 'string', 'default': ''},
                'onClose': {'type': 'function', 'default': None}
            },
            slots=['children', 'header', 'footer'],
            variants=['standard', 'fullscreen', 'drawer'],
            design_token_bindings={
                'backdrop_bg': 'rgba(0,0,0,0.75)',
                'surface_bg': 'var(--color-background, #0f172a)',
                'radius': 'var(--radius-lg, 12px)',
                'shadow': 'var(--shadow-lg, 0 10px 25px rgba(0,0,0,0.5))'
            },
            accessibility_metadata={
                'semantic_tag': 'dialog_or_div',
                'role': 'dialog',
                'aria_modal': 'true',
                'keyboard_navigable': True,
                'escape_to_close': True,
                'focus_trap': True
            }
        )

        # 8. Card (Molecule)
        manifest.entries['Card'] = ComponentManifestEntry(
            component_type='Card',
            category='molecule',
            description='Versatile content container with header, media, body, and footer slots. Composes Badge and Avatar.',
            props_schema={
                'title': {'type': 'string', 'default': ''},
                'subtitle': {'type': 'string', 'default': ''},
                'image': {'type': 'object', 'default': None},
                'badge': {'type': 'string', 'default': ''},
                'variant': {'type': 'string', 'default': 'elevated', 'options': ['elevated', 'outlined', 'flat']}
            },
            slots=['header', 'media', 'children', 'footer', 'badge'],
            variants=['elevated', 'outlined', 'flat'],
            design_token_bindings={
                'background': 'var(--color-surface, rgba(255,255,255,0.05))',
                'border': '1px solid rgba(255,255,255,0.1)',
                'radius': 'var(--radius-md, 8px)',
                'padding': 'var(--spacing-lg, 1.5rem)',
                'shadow': 'var(--shadow-md, 0 4px 6px rgba(0,0,0,0.1))'
            },
            accessibility_metadata={
                'semantic_tag': 'article_or_div',
                'role': 'region',
                'keyboard_navigable': False
            },
            responsive_behavior={
                'mobile': {'padding': '1rem', 'width': '100%'},
                'desktop': {'padding': '1.5rem'}
            }
        )

        # 9. StatsCard (Molecule)
        manifest.entries['StatsCard'] = ComponentManifestEntry(
            component_type='StatsCard',
            category='molecule',
            description='Analytical metric summary display with trend indicator. Composes Card and Badge.',
            props_schema={
                'label': {'type': 'string', 'default': ''},
                'value': {'type': 'string', 'default': ''},
                'change': {'type': 'string', 'default': ''},
                'trend': {'type': 'string', 'default': 'neutral', 'options': ['up', 'down', 'neutral']}
            },
            slots=['icon', 'badge'],
            variants=['standard', 'bordered', 'compact'],
            design_token_bindings={
                'value_size': '2rem',
                'value_weight': '700',
                'radius': 'var(--radius-md, 8px)'
            },
            accessibility_metadata={
                'semantic_tag': 'div',
                'role': 'group',
                'aria_label': 'Metric summary'
            }
        )

        # 10. DashboardCard (Molecule)
        manifest.entries['DashboardCard'] = ComponentManifestEntry(
            component_type='DashboardCard',
            category='molecule',
            description='Interactive analytical widget card with action header. Composes Card and Button.',
            props_schema={
                'title': {'type': 'string', 'default': ''},
                'metric': {'type': 'string', 'default': ''},
                'description': {'type': 'string', 'default': ''},
                'actionLabel': {'type': 'string', 'default': ''}
            },
            slots=['children', 'action'],
            variants=['standard', 'wide', 'chart'],
            design_token_bindings={
                'background': 'var(--color-surface, rgba(255,255,255,0.05))',
                'padding': '1.5rem'
            },
            accessibility_metadata={
                'semantic_tag': 'section',
                'role': 'region',
                'aria_label': 'Dashboard widget'
            }
        )

        # 11. PricingCard (Molecule)
        manifest.entries['PricingCard'] = ComponentManifestEntry(
            component_type='PricingCard',
            category='molecule',
            description='Subscription tier presentation card with feature list and conversion trigger. Composes Card, Badge, and Button.',
            props_schema={
                'title': {'type': 'string', 'default': 'Starter'},
                'price': {'type': 'string', 'default': '$29/mo'},
                'period': {'type': 'string', 'default': 'per month'},
                'features': {'type': 'list', 'default': []},
                'isPopular': {'type': 'boolean', 'default': False},
                'cta': {'type': 'object', 'default': {'label': 'Choose Plan', 'href': '#'}}
            },
            slots=['featuresList', 'badge', 'ctaButton'],
            variants=['standard', 'highlighted', 'compact'],
            design_token_bindings={
                'border_highlight': '2px solid var(--color-primary, #3b82f6)',
                'price_size': '2.5rem',
                'radius': 'var(--radius-lg, 12px)'
            },
            accessibility_metadata={
                'semantic_tag': 'article',
                'role': 'region',
                'aria_label': 'Pricing plan',
                'keyboard_navigable': True
            }
        )

        # 12. Testimonial (Molecule)
        manifest.entries['Testimonial'] = ComponentManifestEntry(
            component_type='Testimonial',
            category='molecule',
            description='Customer quote endorsement card with author metadata. Composes Card and Avatar.',
            props_schema={
                'quote': {'type': 'string', 'default': ''},
                'author': {'type': 'string', 'default': ''},
                'role': {'type': 'string', 'default': ''},
                'company': {'type': 'string', 'default': ''},
                'avatar': {'type': 'string', 'default': ''}
            },
            slots=['avatar', 'rating'],
            variants=['card', 'quote_only', 'centered'],
            design_token_bindings={
                'quote_style': 'italic',
                'background': 'var(--color-surface, rgba(255,255,255,0.05))'
            },
            accessibility_metadata={
                'semantic_tag': 'blockquote',
                'role': 'complementary',
                'aria_label': 'Customer endorsement'
            }
        )

        # 13. BlogCard (Molecule)
        manifest.entries['BlogCard'] = ComponentManifestEntry(
            component_type='BlogCard',
            category='molecule',
            description='Editorial article summary card with media preview and author byline. Composes Card, Badge, and Avatar.',
            props_schema={
                'title': {'type': 'string', 'default': ''},
                'excerpt': {'type': 'string', 'default': ''},
                'date': {'type': 'string', 'default': ''},
                'category': {'type': 'string', 'default': ''},
                'image': {'type': 'object', 'default': None},
                'href': {'type': 'string', 'default': '#'}
            },
            slots=['media', 'categoryBadge', 'authorByline'],
            variants=['grid_item', 'horizontal', 'featured'],
            design_token_bindings={
                'hover_shadow': 'var(--shadow-lg)',
                'radius': 'var(--radius-md, 8px)'
            },
            accessibility_metadata={
                'semantic_tag': 'article',
                'role': 'article',
                'keyboard_navigable': True
            }
        )

        # 14. ProductCard (Molecule)
        manifest.entries['ProductCard'] = ComponentManifestEntry(
            component_type='ProductCard',
            category='molecule',
            description='E-Commerce merchandise display card with pricing and cart trigger. Composes Card, Badge, and Button.',
            props_schema={
                'title': {'type': 'string', 'default': ''},
                'price': {'type': 'string', 'default': '$0.00'},
                'rating': {'type': 'number', 'default': 5},
                'badge': {'type': 'string', 'default': ''},
                'image': {'type': 'object', 'default': None},
                'onAddToCart': {'type': 'function', 'default': None}
            },
            slots=['media', 'badge', 'actionButton'],
            variants=['standard', 'compact', 'list_item'],
            design_token_bindings={
                'price_color': 'var(--color-primary, #3b82f6)',
                'price_weight': '700'
            },
            accessibility_metadata={
                'semantic_tag': 'article',
                'role': 'region',
                'aria_label': 'Product item',
                'keyboard_navigable': True
            }
        )

        # 15. Navbar (Organism)
        manifest.entries['Navbar'] = ComponentManifestEntry(
            component_type='Navbar',
            category='organism',
            description='Primary top navigation bar with branding, links, and conversion triggers. Composes Button and Avatar.',
            props_schema={
                'logo': {'type': 'string', 'default': 'Brand'},
                'navigation': {'type': 'list', 'default': []},
                'actions': {'type': 'list', 'default': []},
                'variant': {'type': 'string', 'default': 'standard', 'options': ['standard', 'transparent', 'sidebar']}
            },
            slots=['brand', 'menuLinks', 'actionsSlot', 'mobileToggle'],
            variants=['standard', 'transparent', 'sidebar'],
            design_token_bindings={
                'height': '5rem',
                'background_standard': 'var(--color-background, #0f172a)',
                'border_bottom': '1px solid rgba(255,255,255,0.1)'
            },
            accessibility_metadata={
                'semantic_tag': 'header',
                'role': 'banner',
                'nav_role': 'navigation',
                'aria_label': 'Main Navigation',
                'keyboard_navigable': True,
                'mobile_menu_aria': 'aria-expanded bound to state'
            },
            responsive_behavior={
                'mobile': {'menu_mode': 'drawer_or_collapsed', 'padding': '1rem'},
                'desktop': {'menu_mode': 'inline', 'padding': '1rem 2rem'}
            }
        )

        # 16. Footer (Organism)
        manifest.entries['Footer'] = ComponentManifestEntry(
            component_type='Footer',
            category='organism',
            description='Site footer with multi-column link directories, legal copyright, and branding.',
            props_schema={
                'logo': {'type': 'string', 'default': 'Brand'},
                'copyright': {'type': 'string', 'default': '© 2026 All Rights Reserved.'},
                'columns': {'type': 'list', 'default': []},
                'socials': {'type': 'list', 'default': []}
            },
            slots=['brandCol', 'linkColumns', 'legalRow', 'socialLinks'],
            variants=['standard', 'minimal', 'multi_column'],
            design_token_bindings={
                'padding_top': 'var(--spacing-2xl, 6rem)',
                'padding_bottom': 'var(--spacing-xl, 4rem)',
                'background': 'var(--color-surface, rgba(0,0,0,0.25))',
                'border_top': '1px solid rgba(255,255,255,0.1)'
            },
            accessibility_metadata={
                'semantic_tag': 'footer',
                'role': 'contentinfo',
                'aria_label': 'Site Footer',
                'keyboard_navigable': True
            },
            responsive_behavior={
                'mobile': {'grid_columns': 1, 'text_align': 'center'},
                'desktop': {'grid_columns': 4, 'text_align': 'start'}
            }
        )

        # 17. Hero (Organism)
        manifest.entries['Hero'] = ComponentManifestEntry(
            component_type='Hero',
            category='organism',
            description='High-impact landing hero banner with headline, subtitle, CTAs, and media. Composes Badge and Button.',
            props_schema={
                'title': {'type': 'string', 'default': 'Welcome to Our Platform'},
                'subtitle': {'type': 'string', 'default': 'Deliver state-of-the-art web experiences powered by intelligent design.'},
                'cta': {'type': 'object', 'default': {'label': 'Get Started', 'href': '#features'}},
                'image': {'type': 'object', 'default': None},
                'badge': {'type': 'string', 'default': ''},
                'variant': {'type': 'string', 'default': 'centered', 'options': ['centered', 'split', 'fullscreen']}
            },
            slots=['badgeSlot', 'headlineSlot', 'ctaGroup', 'mediaSlot'],
            variants=['centered', 'split', 'fullscreen'],
            design_token_bindings={
                'title_size': 'calc(2.5rem + 1vw)',
                'subtitle_size': '1.25rem',
                'padding_vertical': 'var(--spacing-2xl, 6rem)',
                'max_width': '1280px'
            },
            accessibility_metadata={
                'semantic_tag': 'section',
                'role': 'region',
                'aria_label': 'Hero Banner',
                'heading_level': 1,
                'keyboard_navigable': True
            },
            responsive_behavior={
                'mobile': {'layout': 'flex-column', 'text_align': 'center'},
                'desktop': {'layout': 'flex-row_for_split', 'text_align': 'center_or_start'}
            }
        )

        # 18. FeatureGrid (Organism)
        manifest.entries['FeatureGrid'] = ComponentManifestEntry(
            component_type='FeatureGrid',
            category='organism',
            description='Multi-column grid presenting key value propositions or product features. Composes Card.',
            props_schema={
                'title': {'type': 'string', 'default': 'Key Features'},
                'subtitle': {'type': 'string', 'default': 'Everything you need to succeed.'},
                'features': {'type': 'list', 'default': []},
                'columns': {'type': 'number', 'default': 3}
            },
            slots=['headerSlot', 'gridSlot'],
            variants=['grid_3', 'grid_2', 'cards_outlined'],
            design_token_bindings={
                'gap': 'var(--spacing-lg, 2rem)',
                'padding_vertical': 'var(--spacing-2xl, 5rem)'
            },
            accessibility_metadata={
                'semantic_tag': 'section',
                'role': 'region',
                'aria_label': 'Features Grid',
                'heading_level': 2
            },
            responsive_behavior={
                'mobile': {'grid_columns': 1},
                'tablet': {'grid_columns': 2},
                'desktop': {'grid_columns': 3}
            }
        )

        # 19. ProductGrid (Organism)
        manifest.entries['ProductGrid'] = ComponentManifestEntry(
            component_type='ProductGrid',
            category='organism',
            description='E-Commerce storefront catalog grid. Composes ProductCard.',
            props_schema={
                'title': {'type': 'string', 'default': 'Featured Products'},
                'products': {'type': 'list', 'default': []},
                'columns': {'type': 'number', 'default': 4}
            },
            slots=['headerSlot', 'productsSlot'],
            variants=['grid_4', 'grid_3', 'compact'],
            design_token_bindings={
                'gap': 'var(--spacing-lg, 2rem)',
                'padding': 'var(--spacing-2xl, 4rem)'
            },
            accessibility_metadata={
                'semantic_tag': 'section',
                'role': 'region',
                'aria_label': 'Product Catalog Grid',
                'heading_level': 2
            },
            responsive_behavior={
                'mobile': {'grid_columns': 1},
                'tablet': {'grid_columns': 2},
                'desktop': {'grid_columns': 4}
            }
        )

        # 20. BlogGrid (Organism)
        manifest.entries['BlogGrid'] = ComponentManifestEntry(
            component_type='BlogGrid',
            category='organism',
            description='Editorial article feed grid. Composes BlogCard.',
            props_schema={
                'title': {'type': 'string', 'default': 'Latest Insights'},
                'posts': {'type': 'list', 'default': []},
                'columns': {'type': 'number', 'default': 3}
            },
            slots=['headerSlot', 'postsSlot'],
            variants=['grid_3', 'masonry', 'list_view'],
            design_token_bindings={
                'gap': 'var(--spacing-lg, 2rem)',
                'padding': 'var(--spacing-xl, 4rem)'
            },
            accessibility_metadata={
                'semantic_tag': 'section',
                'role': 'feed',
                'aria_label': 'Blog Articles Feed',
                'heading_level': 2
            }
        )

        # 21. FAQ (Organism)
        manifest.entries['FAQ'] = ComponentManifestEntry(
            component_type='FAQ',
            category='organism',
            description='Interactive collapsible accordion list for frequently asked questions. Composes Card.',
            props_schema={
                'title': {'type': 'string', 'default': 'Frequently Asked Questions'},
                'subtitle': {'type': 'string', 'default': 'Everything you need to know about our product and billing.'},
                'items': {'type': 'list', 'default': []}
            },
            slots=['headerSlot', 'accordionSlot'],
            variants=['standard', 'bordered', 'two_column'],
            design_token_bindings={
                'item_spacing': '1rem',
                'radius': 'var(--radius-md, 8px)'
            },
            accessibility_metadata={
                'semantic_tag': 'section',
                'role': 'region',
                'aria_label': 'Frequently Asked Questions',
                'accordion_role': 'button with aria-expanded and aria-controls',
                'keyboard_navigable': True
            }
        )

        # 22. ContactForm (Organism)
        manifest.entries['ContactForm'] = ComponentManifestEntry(
            component_type='ContactForm',
            category='organism',
            description='Structured inquiry submission portal with input validation. Composes Button, Alert, and Card.',
            props_schema={
                'title': {'type': 'string', 'default': 'Get in Touch'},
                'subtitle': {'type': 'string', 'default': 'We would love to hear from you. Please fill out the form below.'},
                'submitLabel': {'type': 'string', 'default': 'Send Message'},
                'onSubmit': {'type': 'function', 'default': None}
            },
            slots=['headerSlot', 'formFieldsSlot', 'alertSlot', 'submitSlot'],
            variants=['standard', 'split_with_map', 'compact'],
            design_token_bindings={
                'input_padding': '0.75rem',
                'input_radius': 'var(--radius-md, 6px)',
                'input_border': '1px solid rgba(255,255,255,0.2)'
            },
            accessibility_metadata={
                'semantic_tag': 'section_with_form',
                'role': 'form',
                'aria_label': 'Contact Inquiry Form',
                'input_labels': 'explicit label element or aria-label required for all inputs',
                'keyboard_navigable': True
            }
        )

        # 23. AuthForm (Organism)
        manifest.entries['AuthForm'] = ComponentManifestEntry(
            component_type='AuthForm',
            category='organism',
            description='Authentication card for user login or registration with OAuth triggers. Composes Card, Button, and Alert.',
            props_schema={
                'title': {'type': 'string', 'default': 'Sign In to Account'},
                'subtitle': {'type': 'string', 'default': 'Enter your credentials to access your dashboard.'},
                'type': {'type': 'string', 'default': 'login', 'options': ['login', 'register']},
                'oauthProviders': {'type': 'list', 'default': ['Google', 'GitHub']}
            },
            slots=['headerSlot', 'fieldsSlot', 'oauthSlot', 'footerLinkSlot'],
            variants=['centered_card', 'split_screen', 'modal'],
            design_token_bindings={
                'max_width': '420px',
                'card_padding': '2rem',
                'radius': 'var(--radius-lg, 12px)'
            },
            accessibility_metadata={
                'semantic_tag': 'section_with_form',
                'role': 'form',
                'aria_label': 'Authentication Form',
                'keyboard_navigable': True,
                'password_toggle_aria': 'aria-label on show/hide password toggle'
            }
        )

        # 24. Table (Organism)
        manifest.entries['Table'] = ComponentManifestEntry(
            component_type='Table',
            category='organism',
            description='Structured data grid for analytical or administrative records. Composes Pagination, Badge, and Button.',
            props_schema={
                'columns': {'type': 'list', 'default': []},
                'data': {'type': 'list', 'default': []},
                'pagination': {'type': 'object', 'default': None}
            },
            slots=['headerRow', 'bodyRows', 'paginationSlot'],
            variants=['standard', 'striped', 'bordered', 'compact'],
            design_token_bindings={
                'cell_padding': '0.75rem 1rem',
                'border_color': 'rgba(255,255,255,0.1)',
                'header_bg': 'rgba(255,255,255,0.05)'
            },
            accessibility_metadata={
                'semantic_tag': 'table_wrapper_with_table',
                'role': 'table',
                'aria_label': 'Data Grid Table',
                'table_headers': 'th elements with scope="col" or scope="row"',
                'keyboard_navigable': True
            },
            responsive_behavior={
                'mobile': {'overflow_x': 'auto', 'display': 'block'},
                'desktop': {'overflow_x': 'visible'}
            }
        )

        # 25. Sidebar (Organism)
        manifest.entries['Sidebar'] = ComponentManifestEntry(
            component_type='Sidebar',
            category='organism',
            description='Vertical application navigation drawer with collapsible state and user profile widget. Composes Button, Badge, and Avatar.',
            props_schema={
                'items': {'type': 'list', 'default': []},
                'activeItem': {'type': 'string', 'default': ''},
                'collapsed': {'type': 'boolean', 'default': False},
                'onToggle': {'type': 'function', 'default': None},
                'user': {'type': 'object', 'default': None}
            },
            slots=['brandSlot', 'navItemsSlot', 'userProfileSlot', 'collapseToggleSlot'],
            variants=['standard', 'collapsed', 'floating'],
            design_token_bindings={
                'width_expanded': '260px',
                'width_collapsed': '80px',
                'background': 'var(--color-surface, #1e293b)',
                'border_right': '1px solid rgba(255,255,255,0.1)'
            },
            accessibility_metadata={
                'semantic_tag': 'aside_with_nav',
                'role': 'complementary',
                'nav_role': 'navigation',
                'aria_label': 'Sidebar NavigationDrawer',
                'keyboard_navigable': True
            },
            responsive_behavior={
                'mobile': {'position': 'fixed', 'mode': 'off_canvas_drawer'},
                'desktop': {'position': 'relative', 'mode': 'static'}
            }
        )

        return manifest

    @classmethod
    def from_render_project(cls, project: Any) -> 'ComponentManifest':
        """
        Stage 1.5: Enriches the default 25-component manifest with project-specific custom sections,
        design token bindings, and variant selections from a RenderProject.
        """
        proj_id = getattr(project, 'id', 'proj-12b')
        proj_name = getattr(project, 'name', 'Nexora React App')
        manifest = cls.create_default_manifest(project_id=proj_id, project_name=proj_name)

        # Map custom sections from pages
        pages = getattr(project, 'pages', [])
        for p in pages:
            for s in getattr(p, 'sections', []):
                s_name = getattr(s, 'name', '') or getattr(s, 'id', '')
                c_name = s_name.replace(" ", "")
                if not c_name or c_name == "Section":
                    c_name = f"{getattr(s, 'category', 'general').capitalize()}Section"
                
                # If section is not already in manifest, register it as an organism composing library primitives
                if c_name not in manifest.entries:
                    manifest.entries[c_name] = ComponentManifestEntry(
                        component_type=c_name,
                        category='section',
                        description=f"Generated section component '{c_name}' composing reusable React Component Library primitives.",
                        props_schema=getattr(s, 'props_schema', {}) or {'title': {'type': 'string'}, 'subtitle': {'type': 'string'}},
                        slots=['headerSlot', 'contentSlot'],
                        variants=[getattr(s, 'variant', 'default')],
                        design_token_bindings={
                            'padding_vertical': 'var(--spacing-2xl, 4rem)',
                            'background': getattr(s, 'style_rules', {}).get('background', 'transparent')
                        },
                        accessibility_metadata={
                            'semantic_tag': 'section',
                            'role': 'region',
                            'aria_label': c_name,
                            'keyboard_navigable': True
                        }
                    )
        return manifest
