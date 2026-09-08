# -*- coding: utf-8 -*-
"""
Provider Interface & Multi-Renderer Foundation: RenderingProviderRegistry

Implements the authoritative registry capable of discovering, registering, and resolving
rendering providers by identifier (e.g., react, vue, angular, flutter, html, react_three_fiber).
Initially only React is implemented as a functional rendering engine, while future targets
expose metadata and capability models in preparation for multi-renderer execution.
"""

from typing import Dict, Any, List, Optional, Type
import logging
from .rendering_provider import (
    RenderingProvider,
    ProviderMetadata,
    ProviderCapabilityModel,
    ProviderVersioning,
)

_logger = logging.getLogger(__name__)


class RenderingProviderRegistry:
    """
    Singleton registry managing rendering provider classes and their associated metadata.
    """
    _providers: Dict[str, Type[RenderingProvider]] = {}
    _metadata_stubs: Dict[str, ProviderMetadata] = {}

    @classmethod
    def _initialize_defaults(cls):
        """
        Populate default metadata stubs for all supported target identifiers.
        Lazy registration of ReactRenderingProvider happens on first query or resolution.
        """
        if cls._metadata_stubs:
            return

        # 1. React (Functional implementation in Phase 12C)
        cls._metadata_stubs["react"] = ProviderMetadata(
            provider_id="react",
            display_name="React 18 (Vite + esbuild)",
            capabilities=ProviderCapabilityModel(
                layouts=True, routing=True, forms=True, animations=False,
                design_tokens=True, accessibility=True, static_export=True, ssr=False
            ),
            versioning=ProviderVersioning(provider_version="1.0.0", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=[
                "client_side_routing", "design_token_binding", "variant_adaptation",
                "a11y_metadata", "atomic_component_library", "responsive_layouts"
            ],
            supported_components=[
                "Button", "Card", "Hero", "Navbar", "Footer", "FeatureGrid",
                "Testimonial", "PricingCard", "FAQ", "ContactForm", "ProductCard",
                "ProductGrid", "BlogCard", "BlogGrid", "DashboardCard", "StatsCard",
                "Table", "Sidebar", "AuthForm", "Modal", "Badge", "Avatar",
                "Alert", "Breadcrumb", "Pagination"
            ],
            output_structure={
                "package.json": "npm project manifest and dependency definitions",
                "vite.config.js": "Vite bundler build configuration",
                "index.html": "Root HTML viewport scaffold",
                "src/main.jsx": "React application DOM mount point",
                "src/App.jsx": "Root application component with routing bounds",
                "src/routes.jsx": "React Router DOM route definitions",
                "src/styles/tokens.css": "Design system CSS variables and utilities",
                "src/config/assets.js": "Static asset binding registry",
                "src/config/content.js": "Structured content bindings",
                "src/config/manifest.js": "Serialized runtime component manifest",
                "src/layouts/": "Hierarchical layout wrappers",
                "src/components/": "Reusable UI components and section wrappers",
                "src/pages/": "Page view compositions",
            }
        )

        # 2. Vue (Future Target)
        cls._metadata_stubs["vue"] = ProviderMetadata(
            provider_id="vue",
            display_name="Vue 3 (Vite + Composition API)",
            capabilities=ProviderCapabilityModel(
                layouts=True, routing=True, forms=True, animations=True,
                design_tokens=True, accessibility=True, static_export=True, ssr=False
            ),
            versioning=ProviderVersioning(provider_version="0.1.0-alpha", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=["composition_api", "vue_router", "pinia_state", "design_token_binding"],
        )

        # 3. Angular (Future Target)
        cls._metadata_stubs["angular"] = ProviderMetadata(
            provider_id="angular",
            display_name="Angular 17 (Standalone Components)",
            capabilities=ProviderCapabilityModel(
                layouts=True, routing=True, forms=True, animations=True,
                design_tokens=True, accessibility=True, static_export=True, ssr=True
            ),
            versioning=ProviderVersioning(provider_version="0.1.0-alpha", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=["standalone_components", "reactive_forms", "rxjs_signals"],
        )

        # 4. Flutter (Future Target)
        cls._metadata_stubs["flutter"] = ProviderMetadata(
            provider_id="flutter",
            display_name="Flutter Web (Dart Widgets)",
            capabilities=ProviderCapabilityModel(
                layouts=True, routing=True, forms=True, animations=True,
                design_tokens=True, accessibility=True, static_export=True, ssr=False
            ),
            versioning=ProviderVersioning(provider_version="0.1.0-alpha", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=["widget_synthesis", "material_3", "cupertino", "canvas_rendering"],
        )

        # 5. HTML (Future Target)
        cls._metadata_stubs["html"] = ProviderMetadata(
            provider_id="html",
            display_name="Semantic HTML5 & Vanilla CSS",
            capabilities=ProviderCapabilityModel(
                layouts=True, routing=False, forms=True, animations=False,
                design_tokens=True, accessibility=True, static_export=True, ssr=False
            ),
            versioning=ProviderVersioning(provider_version="0.1.0-alpha", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=["semantic_html5", "vanilla_css", "zero_js_bundle"],
        )

        # 6. React Three Fiber (Phase 37.1)
        cls._metadata_stubs["react_three_fiber"] = ProviderMetadata(
            provider_id="react_three_fiber",
            display_name="React Three Fiber (3D WebGL Canvas)",
            capabilities=ProviderCapabilityModel(
                layouts=False, routing=False, forms=False, animations=True,
                design_tokens=True, accessibility=False, static_export=True, ssr=False
            ),
            versioning=ProviderVersioning(provider_version="1.0.0", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=["webgl_canvas", "three_js_scene", "shader_materials"],
        )

        # 7. Spline (Phase 37.2)
        cls._metadata_stubs["spline"] = ProviderMetadata(
            provider_id="spline",
            display_name="Spline 3D (Embedded Scene Renderer)",
            capabilities=ProviderCapabilityModel(
                layouts=False, routing=False, forms=False, animations=True,
                design_tokens=True, accessibility=False, static_export=True, ssr=False
            ),
            versioning=ProviderVersioning(provider_version="1.0.0", api_version="1.0.0", manifest_version="1.0.0"),
            supported_features=["spline_scene", "embedded_3d", "interactive_scene", "react_integration"],
        )

    @classmethod
    def register_provider(
        cls,
        provider_id: str,
        provider_cls: Type[RenderingProvider],
        metadata: Optional[ProviderMetadata] = None,
    ):
        """
        Register a RenderingProvider implementation under a unique identifier.
        """
        cls._initialize_defaults()
        if not issubclass(provider_cls, RenderingProvider):
            raise TypeError(f"Class '{provider_cls.__name__}' must inherit from RenderingProvider.")

        cls._providers[provider_id] = provider_cls
        if metadata:
            cls._metadata_stubs[provider_id] = metadata
        _logger.debug("Registered RenderingProvider '%s' (%s).", provider_id, provider_cls.__name__)

    @classmethod
    def get_provider(cls, provider_id: str = "react", **kwargs) -> RenderingProvider:
        """
        Resolve and instantiate the requested RenderingProvider by identifier.
        Raises NotImplementedError if the provider is a registered stub awaiting future implementation.
        """
        cls._initialize_defaults()
        provider_id = provider_id.lower().strip()

        # Ensure React is registered if requested
        if provider_id == "react" and "react" not in cls._providers:
            from .react_provider import ReactRenderingProvider
            cls._providers["react"] = ReactRenderingProvider
            
        # Ensure React Three Fiber is registered if requested
        if provider_id == "react_three_fiber" and "react_three_fiber" not in cls._providers:
            from .react_three_fiber_provider import ReactThreeFiberProvider
            cls._providers["react_three_fiber"] = ReactThreeFiberProvider

        # Ensure Spline is registered if requested
        if provider_id == "spline" and "spline" not in cls._providers:
            from .spline_provider import SplineRenderingProvider
            cls._providers["spline"] = SplineRenderingProvider

        if provider_id in cls._providers:
            return cls._providers[provider_id](**kwargs)

        if provider_id in cls._metadata_stubs:
            raise NotImplementedError(
                f"RenderingProvider '{provider_id}' is registered in the multi-renderer foundation "
                f"but its implementation is scheduled for future phases."
            )

        raise ValueError(
            f"Unknown rendering provider identifier '{provider_id}'. "
            f"Available targets: {list(cls._metadata_stubs.keys())}"
        )

    @classmethod
    def list_providers(cls) -> List[str]:
        """
        Return a list of all registered and candidate rendering provider identifiers.
        """
        cls._initialize_defaults()
        return list(cls._metadata_stubs.keys())

    @classmethod
    def get_provider_metadata(cls, provider_id: str = "react") -> ProviderMetadata:
        """
        Return authoritative ProviderMetadata for a given target identifier.
        """
        cls._initialize_defaults()
        provider_id = provider_id.lower().strip()

        if provider_id in cls._metadata_stubs:
            return cls._metadata_stubs[provider_id]

        raise ValueError(f"Unknown rendering provider identifier '{provider_id}'.")


    @classmethod
    def is_supported(cls, provider_id: str) -> bool:
        """
        Check if a provider identifier is known to the registry.
        """
        cls._initialize_defaults()
        return provider_id.lower().strip() in cls._metadata_stubs

    # Phase 47.9 (U8): authoritative renderer-selection contract.
    # RenderingBlueprint.strategy -> rendering provider identifier.
    #   webgl / immersive  -> react_three_fiber (qualified WebGL/R3F requirement)
    #   spline             -> spline            (explicit Spline requirement only)
    #   none / css_3d / canvas / anything else -> react (ordinary React website)
    # css_3d and canvas are CSS-transform / 2D-canvas techniques satisfied by the
    # standard React provider. Spline is never inferred from visual complexity and
    # R3F is never selected merely because a component carries 3D metadata.
    _STRATEGY_PROVIDER_MAP = {
        "webgl": "react_three_fiber",
        "immersive": "react_three_fiber",
        "spline": "spline",
    }

    @classmethod
    def resolve_provider_id(cls, strategy: Optional[str]) -> str:
        """
        Deterministically resolve the rendering provider identifier for a
        RenderingBlueprint strategy value. Unknown or absent strategies fall
        back to the standard React provider.
        """
        normalized = (strategy or "none").lower().strip()
        return cls._STRATEGY_PROVIDER_MAP.get(normalized, "react")

    @classmethod
    def get_capabilities(cls, provider_id: str) -> ProviderCapabilityModel:
        """
        Return the capability declaration model for a requested provider identifier.
        """
        meta = cls.get_provider_metadata(provider_id)
        return meta.capabilities
