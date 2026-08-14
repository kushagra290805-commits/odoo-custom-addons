# -*- coding: utf-8 -*-
"""
Render Domain Model — Phase 12A: React Generation Engine Foundation.

Defines the authoritative, provider-neutral, and rendering-neutral Render Model that
acts as the intermediate rendering contract between frozen AI planning models and
target-specific rendering engines (React, HTML/CSS, Flutter, Native Mobile, etc.).

Strict Architectural Governance:
This module must NOT reference JSX, React, React Router, CSS, HTML, Vite, Next.js,
or any specific UI framework syntax. It describes tokens, assets, content, routes,
components, layouts, pages, and projects using purely domain-driven structural concepts.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import uuid
from .domain_enums import ComponentCategory, PageArchetype


@dataclass
class RenderToken:
    """
    Provider-neutral representation of a design token (color, typography, spacing, radius, shadow, transition).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                              # e.g., 'primary-color', 'spacing-md', 'font-heading'
    token_type: str = "color"                   # 'color', 'spacing', 'typography', 'radius', 'shadow', 'transition'
    value: Union[str, int, float, Dict[str, Any]] = ""
    category: str = "brand"                     # 'brand', 'neutral', 'system', 'layout'
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderToken':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            token_type=data.get('token_type', 'color'),
            value=data.get('value', ''),
            category=data.get('category', 'brand'),
            description=data.get('description'),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'token_type': self.token_type,
            'value': self.value,
            'category': self.category,
            'description': self.description,
            'metadata': self.metadata
        }

    @property
    def css_var_name(self) -> str:
        """Return the CSS custom property name without leading dashes (e.g., 'color-primary')."""
        t_name = self.name.lower().replace(" ", "-").replace("_", "-")
        t_type = self.token_type.lower()
        if t_type == 'color' and not t_name.startswith("color-"):
            return f"color-{t_name}"
        elif t_type in ('typography', 'font') and not t_name.startswith("font-"):
            return f"font-{t_name}"
        return t_name

    @property
    def css_var(self) -> str:
        """Return the full CSS variable expression (e.g., 'var(--color-primary)')."""
        return f"var(--{self.css_var_name})"



@dataclass
class RenderAsset:
    """
    Provider-neutral representation of a media asset requirement bound for rendering.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    asset_type: str = "image"                   # 'image', 'illustration', 'video', 'icon', 'logo', '3d_asset'
    source_uri: str = ""                        # Placeholder URI or resolved asset URI
    dimensions: Dict[str, Union[int, str]] = field(default_factory=dict)  # e.g., {'width': 1920, 'height': 1080}
    alt_text: str = ""
    role: str = "general"                       # 'hero_background', 'feature_icon', 'avatar', 'logo'
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderAsset':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            asset_type=data.get('asset_type', 'image'),
            source_uri=data.get('source_uri', ''),
            dimensions=data.get('dimensions', {}),
            alt_text=data.get('alt_text', ''),
            role=data.get('role', 'general'),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'asset_type': self.asset_type,
            'source_uri': self.source_uri,
            'dimensions': self.dimensions,
            'alt_text': self.alt_text,
            'role': self.role,
            'metadata': self.metadata
        }


@dataclass
class RenderContent:
    """
    Provider-neutral representation of text copy, headings, labels, or SEO metadata.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_type: str = "body"                  # 'headline', 'sub_headline', 'body', 'cta', 'label', 'seo_title', 'seo_desc'
    text: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)  # e.g., {'hierarchy_level': 1, 'destination_intent': '/signup'}
    locale: str = "en-US"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderContent':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            content_type=data.get('content_type', 'body'),
            text=data.get('text', ''),
            attributes=data.get('attributes', {}),
            locale=data.get('locale', 'en-US'),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content_type': self.content_type,
            'text': self.text,
            'attributes': self.attributes,
            'locale': self.locale,
            'metadata': self.metadata
        }


@dataclass
class RenderRoute:
    """
    Provider-neutral representation of an application navigation route.
    """
    route_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = "/"                             # e.g., '/', '/dashboard', '/blog', '/contact', '/login'
    page_id: str = ""                           # Target RenderPage.id
    title: str = ""
    is_default: bool = False
    requires_auth: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderRoute':
        if not data:
            return cls()
        return cls(
            route_id=data.get('route_id', str(uuid.uuid4())),
            path=data.get('path', '/'),
            page_id=data.get('page_id', ''),
            title=data.get('title', ''),
            is_default=bool(data.get('is_default', False)),
            requires_auth=bool(data.get('requires_auth', False)),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'route_id': self.route_id,
            'path': self.path,
            'page_id': self.page_id,
            'title': self.title,
            'is_default': self.is_default,
            'requires_auth': self.requires_auth,
            'metadata': self.metadata
        }


@dataclass
class RenderComponent:
    """
    Provider-neutral representation of a reusable UI component or section.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                              # e.g., 'HeroSection', 'Navbar', 'PricingTable'
    category: str = "general"                   # 'hero', 'navbar', 'footer', 'pricing', 'features', 'testimonials', etc.
    variant: str = "default"
    capabilities: List[str] = field(default_factory=list)  # e.g., ['dark_mode', 'localization', 'responsive']
    props_schema: Dict[str, Any] = field(default_factory=dict)
    bound_assets: List[RenderAsset] = field(default_factory=list)
    bound_content: List[RenderContent] = field(default_factory=list)
    style_rules: Dict[str, Any] = field(default_factory=dict)  # Provider-neutral style rules e.g., {'background': 'primary-color'}
    children: List['RenderComponent'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderComponent':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            category=data.get('category', 'general'),
            variant=data.get('variant', 'default'),
            capabilities=data.get('capabilities', []),
            props_schema=data.get('props_schema', {}),
            bound_assets=[RenderAsset.from_dict(a) if isinstance(a, dict) else a for a in data.get('bound_assets', [])],
            bound_content=[RenderContent.from_dict(c) if isinstance(c, dict) else c for c in data.get('bound_content', [])],
            style_rules=data.get('style_rules', {}),
            children=[RenderComponent.from_dict(ch) if isinstance(ch, dict) else ch for ch in data.get('children', [])],
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'variant': self.variant,
            'capabilities': self.capabilities,
            'props_schema': self.props_schema,
            'bound_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.bound_assets],
            'bound_content': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.bound_content],
            'style_rules': self.style_rules,
            'children': [ch.to_dict() if hasattr(ch, 'to_dict') else ch for ch in self.children],
            'metadata': self.metadata
        }


@dataclass
class RenderLayout:
    """
    Provider-neutral representation of a structural layout wrapper or container.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    layout_type: str = "container"              # 'container', 'grid', 'stack', 'split', 'masonry', 'overlay', 'section_flow'
    direction: str = "vertical"                 # 'vertical', 'horizontal'
    alignment: Dict[str, str] = field(default_factory=dict)  # e.g., {'horizontal': 'center', 'vertical': 'start'}
    constraints: Dict[str, Any] = field(default_factory=dict)  # e.g., {'max_width_px': 1280, 'padding': 'spacing-xl'}
    behaviors: List[str] = field(default_factory=list)         # e.g., ['sticky', 'responsive', 'scroll_snap']
    responsive_rules: Dict[str, Any] = field(default_factory=dict)  # Viewport adaptations e.g., {'mobile': {'columns': 1}}
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderLayout':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            layout_type=data.get('layout_type', 'container'),
            direction=data.get('direction', 'vertical'),
            alignment=data.get('alignment', {}),
            constraints=data.get('constraints', {}),
            behaviors=data.get('behaviors', []),
            responsive_rules=data.get('responsive_rules', {}),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'layout_type': self.layout_type,
            'direction': self.direction,
            'alignment': self.alignment,
            'constraints': self.constraints,
            'behaviors': self.behaviors,
            'responsive_rules': self.responsive_rules,
            'metadata': self.metadata
        }


@dataclass
class RenderPage:
    """
    Provider-neutral representation of a complete application page or view.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    archetype: str = "landing"                  # 'landing', 'saas_dashboard', 'blog', 'ecommerce', 'contact', 'auth'
    path: str = "/"
    page_layout: Optional[RenderLayout] = None
    sections: List[RenderComponent] = field(default_factory=list)
    page_assets: List[RenderAsset] = field(default_factory=list)
    page_content: List[RenderContent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderPage':
        if not data:
            return cls()
        layout_data = data.get('page_layout')
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            archetype=data.get('archetype', 'landing'),
            path=data.get('path', '/'),
            page_layout=RenderLayout.from_dict(layout_data) if isinstance(layout_data, dict) else layout_data,
            sections=[RenderComponent.from_dict(s) if isinstance(s, dict) else s for s in data.get('sections', [])],
            page_assets=[RenderAsset.from_dict(a) if isinstance(a, dict) else a for a in data.get('page_assets', [])],
            page_content=[RenderContent.from_dict(c) if isinstance(c, dict) else c for c in data.get('page_content', [])],
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'archetype': self.archetype,
            'path': self.path,
            'page_layout': self.page_layout.to_dict() if hasattr(self.page_layout, 'to_dict') else self.page_layout,
            'sections': [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.sections],
            'page_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.page_assets],
            'page_content': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.page_content],
            'metadata': self.metadata
        }


@dataclass
class RenderProject:
    """
    Authoritative, provider-neutral root aggregate representing a complete UI project ready for rendering.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    project_type: str = "web_app"
    tokens: List[RenderToken] = field(default_factory=list)
    routes: List[RenderRoute] = field(default_factory=list)
    pages: List[RenderPage] = field(default_factory=list)
    shared_components: List[RenderComponent] = field(default_factory=list)
    shared_layouts: List[RenderLayout] = field(default_factory=list)
    global_assets: List[RenderAsset] = field(default_factory=list)
    global_content: List[RenderContent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderProject':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            version=data.get('version', '1.0.0'),
            project_type=data.get('project_type', 'web_app'),
            tokens=[RenderToken.from_dict(t) if isinstance(t, dict) else t for t in data.get('tokens', [])],
            routes=[RenderRoute.from_dict(r) if isinstance(r, dict) else r for r in data.get('routes', [])],
            pages=[RenderPage.from_dict(p) if isinstance(p, dict) else p for p in data.get('pages', [])],
            shared_components=[RenderComponent.from_dict(sc) if isinstance(sc, dict) else sc for sc in data.get('shared_components', [])],
            shared_layouts=[RenderLayout.from_dict(sl) if isinstance(sl, dict) else sl for sl in data.get('shared_layouts', [])],
            global_assets=[RenderAsset.from_dict(ga) if isinstance(ga, dict) else ga for ga in data.get('global_assets', [])],
            global_content=[RenderContent.from_dict(gc) if isinstance(gc, dict) else gc for gc in data.get('global_content', [])],
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'project_type': self.project_type,
            'tokens': [t.to_dict() if hasattr(t, 'to_dict') else t for t in self.tokens],
            'routes': [r.to_dict() if hasattr(r, 'to_dict') else r for r in self.routes],
            'pages': [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.pages],
            'shared_components': [sc.to_dict() if hasattr(sc, 'to_dict') else sc for sc in self.shared_components],
            'shared_layouts': [sl.to_dict() if hasattr(sl, 'to_dict') else sl for sl in self.shared_layouts],
            'global_assets': [ga.to_dict() if hasattr(ga, 'to_dict') else ga for ga in self.global_assets],
            'global_content': [gc.to_dict() if hasattr(gc, 'to_dict') else gc for gc in self.global_content],
            'metadata': self.metadata
        }

    @classmethod
    def from_generation_bundle(cls, bundle: Any, **kwargs) -> 'RenderProject':
        """
        Authoritative construction API to build an immutable RenderProject from a validated
        planning bundle, builder session, imported template, or design blueprint.
        """
        bp_dict = bundle if isinstance(bundle, dict) else (bundle.to_dict() if hasattr(bundle, 'to_dict') else {})
        if not bp_dict and hasattr(bundle, '__dict__'):
            bp_dict = getattr(bundle, '__dict__', {})

        render_project = cls(
            id=bp_dict.get('id') or bp_dict.get('blueprint_id', str(uuid.uuid4())),
            name=bp_dict.get('name') or bp_dict.get('project_name', 'Generated Studio Project'),
            version=bp_dict.get('version', '1.0.0'),
            project_type=bp_dict.get('project_type', 'web_app'),
            metadata={
                'source': 'from_generation_bundle',
                'original_blueprint_id': bp_dict.get('id') or bp_dict.get('blueprint_id'),
                'raw_metadata': bp_dict.get('metadata', {})
            }
        )

        # 1. Map Tokens
        t_set = bp_dict.get('token_set') or bp_dict.get('tokens') or {}
        if isinstance(t_set, dict):
            cp = t_set.get('color_palette') or {}
            c_tokens = cp.get('tokens', []) if isinstance(cp, dict) else []
            for t in c_tokens:
                t_dict = t if isinstance(t, dict) else (t.to_dict() if hasattr(t, 'to_dict') else {})
                if t_dict:
                    render_project.tokens.append(RenderToken(
                        id=t_dict.get('id', str(uuid.uuid4())),
                        name=t_dict.get('name', 'color'),
                        token_type='color',
                        value=t_dict.get('hex_value', t_dict.get('value', '#000000')),
                        category='color',
                        description=f"Role: {t_dict.get('role', 'primary')}"
                    ))
            ts = t_set.get('typography_scale') or {}
            typo_tokens = ts.get('tokens', []) if isinstance(ts, dict) else []
            for t in typo_tokens:
                t_dict = t if isinstance(t, dict) else (t.to_dict() if hasattr(t, 'to_dict') else {})
                if t_dict:
                    render_project.tokens.append(RenderToken(
                        id=t_dict.get('id', str(uuid.uuid4())),
                        name=t_dict.get('name', 'font'),
                        token_type='typography',
                        value=f"{t_dict.get('font_size_px', 16)}px {t_dict.get('font_family', 'sans-serif')}",
                        category='typography',
                        description=f"Weight: {t_dict.get('font_weight', 400)}"
                    ))
            spacing_list = t_set.get('spacing_scale_px', [])
            for idx, sp in enumerate(spacing_list):
                render_project.tokens.append(RenderToken(
                    id=f"sp-{idx}",
                    name=f"spacing-{idx+1}",
                    token_type='spacing',
                    value=f"{sp}px",
                    category='spacing'
                ))
            direct_tokens = t_set.get('tokens', []) if isinstance(t_set.get('tokens'), list) else []
            for t in direct_tokens:
                t_dict = t if isinstance(t, dict) else (t.to_dict() if hasattr(t, 'to_dict') else {})
                if t_dict:
                    render_project.tokens.append(RenderToken(
                        id=t_dict.get('id', str(uuid.uuid4())),
                        name=t_dict.get('name', 'token'),
                        token_type=t_dict.get('token_type', 'custom'),
                        value=t_dict.get('value', t_dict.get('hex_value', '')),
                        category=t_dict.get('category', 'custom')
                    ))
        elif isinstance(t_set, list):
            for t in t_set:
                t_dict = t if isinstance(t, dict) else (t.to_dict() if hasattr(t, 'to_dict') else {})
                if t_dict:
                    render_project.tokens.append(RenderToken(
                        id=t_dict.get('id', str(uuid.uuid4())),
                        name=t_dict.get('name', 'token'),
                        token_type=t_dict.get('token_type', 'color'),
                        value=t_dict.get('value', t_dict.get('hex_value', '')),
                        category=t_dict.get('category', 'brand')
                    ))

        # 2. Map Global Assets
        metadata_dict = bp_dict.get('metadata', {}) or {}
        asset_plan_summary = kwargs.get('asset_plan') or metadata_dict.get('asset_plan_summary') or bp_dict.get('asset_plan') or {}
        assets_list = []
        if isinstance(asset_plan_summary, dict):
            for k in ['planned_assets', 'required_assets', 'optional_assets', 'reusable_assets', 'generated_assets', 'user_supplied_assets', 'assets']:
                assets_list.extend(asset_plan_summary.get(k, []))
        elif isinstance(asset_plan_summary, list):
            assets_list = asset_plan_summary
        for a in assets_list:
            a_dict = a if isinstance(a, dict) else (a.to_dict() if hasattr(a, 'to_dict') else {})
            if a_dict:
                r_asset = RenderAsset(
                    id=a_dict.get('asset_id') or a_dict.get('id', str(uuid.uuid4())),
                    name=a_dict.get('name', 'asset'),
                    asset_type=a_dict.get('asset_type', 'image'),
                    source_uri=a_dict.get('source_uri', f"/assets/placeholder_{a_dict.get('name', 'media')}.jpg"),
                    dimensions=a_dict.get('dimensions', {}),
                    alt_text=a_dict.get('alt_text', a_dict.get('name', 'Image asset')),
                    role=a_dict.get('role', 'general'),
                    metadata=a_dict.get('metadata', {})
                )
                render_project.global_assets.append(r_asset)

        # 3. Map Global Content
        content_plan_summary = kwargs.get('content_plan') or metadata_dict.get('content_plan_summary') or bp_dict.get('content_plan') or {}
        content_list = []
        if isinstance(content_plan_summary, dict):
            for k in ['generated_bundles', 'pages', 'bundles', 'content']:
                content_list.extend(content_plan_summary.get(k, []))
        elif isinstance(content_plan_summary, list):
            content_list = content_plan_summary
        for c in content_list:
            c_dict = c if isinstance(c, dict) else (c.to_dict() if hasattr(c, 'to_dict') else {})
            if c_dict:
                r_content = RenderContent(
                    id=c_dict.get('bundle_id') or c_dict.get('id', str(uuid.uuid4())),
                    content_type='bundle',
                    text=c_dict.get('name', 'Content Bundle'),
                    attributes=c_dict,
                    locale=c_dict.get('locale', 'en-US')
                )
                render_project.global_content.append(r_content)

        # 4. Map Pages, Layouts, and Sections
        pages_data = bp_dict.get('pages', []) or []
        archetypes_seen = set()
        for idx, p in enumerate(pages_data):
            p_dict = p if isinstance(p, dict) else (p.to_dict() if hasattr(p, 'to_dict') else {})
            if not p_dict:
                continue
            
            p_id = p_dict.get('id') or str(uuid.uuid4())
            p_name = p_dict.get('name') or f"Page {idx+1}"
            p_path = p_dict.get('slug') or p_dict.get('path') or ("/" if idx == 0 else f"/{p_name.lower().replace(' ', '-')}")
            
            p_arch_enum = PageArchetype.from_str(p_dict.get('archetype'))
            p_arch = p_arch_enum.value
            archetypes_seen.add(p_arch)

            layout_data = p_dict.get('layout_tree') or p_dict.get('page_layout') or {}
            r_layout = None
            if layout_data:
                l_dict = layout_data if isinstance(layout_data, dict) else (layout_data.to_dict() if hasattr(layout_data, 'to_dict') else {})
                r_layout = RenderLayout(
                    id=l_dict.get('id', str(uuid.uuid4())),
                    layout_type=l_dict.get('layout_type', 'container'),
                    direction=l_dict.get('direction', 'vertical'),
                    alignment=l_dict.get('alignment', {}),
                    constraints=l_dict.get('constraints', {}),
                    behaviors=l_dict.get('behaviors', []),
                    responsive_rules=l_dict.get('responsive_rules', {})
                )
            else:
                r_layout = RenderLayout(
                    id=f"layout-{p_id}",
                    layout_type="container",
                    direction="vertical",
                    constraints={"max_width_px": 1280, "padding": "spacing-lg"}
                )

            r_page = RenderPage(
                id=p_id,
                name=p_name,
                archetype=p_arch,
                path=p_path,
                page_layout=r_layout,
                metadata=p_dict.get('metadata', {})
            )

            sections_data = p_dict.get('sections', []) or []
            for s in sections_data:
                s_dict = s if isinstance(s, dict) else (s.to_dict() if hasattr(s, 'to_dict') else {})
                if not s_dict:
                    continue
                
                s_id = s_dict.get('id') or str(uuid.uuid4())
                s_name = s_dict.get('name') or "Section"
                
                s_cat_enum = ComponentCategory.from_str(s_dict.get('category'))
                s_cat = s_cat_enum.value
                s_var = s_dict.get('variant', 'default')
                s_caps = s_dict.get('capabilities', [])
                s_style = s_dict.get('style_rules', s_dict.get('tokens', {}))

                bound_assets = []
                for ba in s_dict.get('bound_assets', []):
                    ba_dict = ba if isinstance(ba, dict) else (ba.to_dict() if hasattr(ba, 'to_dict') else {})
                    if ba_dict:
                        bound_assets.append(RenderAsset.from_dict(ba_dict))

                bound_content = []
                for bc in s_dict.get('bound_content', []):
                    bc_dict = bc if isinstance(bc, dict) else (bc.to_dict() if hasattr(bc, 'to_dict') else {})
                    if bc_dict:
                        bound_content.append(RenderContent.from_dict(bc_dict))

                r_comp = RenderComponent(
                    id=s_id,
                    name=s_name,
                    category=s_cat,
                    variant=s_var,
                    capabilities=s_caps,
                    props_schema=s_dict.get('props_schema', {}),
                    bound_assets=bound_assets,
                    bound_content=bound_content,
                    style_rules=s_style,
                    metadata=s_dict.get('metadata', {})
                )
                r_page.sections.append(r_comp)

            render_project.pages.append(r_page)

            r_route = RenderRoute(
                route_id=f"route-{p_id}",
                path=p_path,
                page_id=p_id,
                title=p_name,
                is_default=(idx == 0)
            )
            render_project.routes.append(r_route)

        render_project.metadata['archetypes_present'] = sorted(list(archetypes_seen))
        return render_project

    from_source = from_generation_bundle

