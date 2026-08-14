# -*- coding: utf-8 -*-
"""
Provider Interface & Multi-Renderer Foundation: RenderingProvider Contract

Defines the authoritative abstraction layer for rendering providers in Nexora Studio.
This interface remains strictly provider-neutral and contains zero framework-specific
(e.g., React, Vue, Angular, Vite) keywords or logic. All rendering engines must implement
this contract, consuming Provider-Neutral Render Models and Component Manifests within
an encapsulated RenderingContext.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from ..render_domain import RenderProject, RenderToken, RenderAsset
    from ..component_manifest import ComponentManifest

_logger = logging.getLogger(__name__)


@dataclass
class ProviderCapabilityModel:
    """
    Declares the functional rendering capabilities supported by a provider implementation.
    """
    layouts: bool = True
    routing: bool = True
    forms: bool = True
    animations: bool = False
    design_tokens: bool = True
    accessibility: bool = True
    static_export: bool = True
    ssr: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderCapabilityModel":
        if not data:
            return cls()
        return cls(
            layouts=bool(data.get("layouts", True)),
            routing=bool(data.get("routing", True)),
            forms=bool(data.get("forms", True)),
            animations=bool(data.get("animations", False)),
            design_tokens=bool(data.get("design_tokens", True)),
            accessibility=bool(data.get("accessibility", True)),
            static_export=bool(data.get("static_export", True)),
            ssr=bool(data.get("ssr", False)),
        )


@dataclass
class ProviderVersioning:
    """
    Declares versioning metadata for the provider, API, and manifest schemas
    to ensure long-term compatibility across evolving pipelines.
    """
    provider_version: str = "1.0.0"
    api_version: str = "1.0.0"
    manifest_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderVersioning":
        if not data:
            return cls()
        return cls(
            provider_version=str(data.get("provider_version", "1.0.0")),
            api_version=str(data.get("api_version", "1.0.0")),
            manifest_version=str(data.get("manifest_version", "1.0.0")),
        )


@dataclass
class ProviderMetadata:
    """
    Exposes descriptive metadata, capabilities, versioning, and structural output
    specifications for a rendering provider.
    """
    provider_id: str
    display_name: str
    capabilities: ProviderCapabilityModel = field(default_factory=ProviderCapabilityModel)
    versioning: ProviderVersioning = field(default_factory=ProviderVersioning)
    supported_features: List[str] = field(default_factory=list)
    supported_components: List[str] = field(default_factory=list)
    supported_variants: Dict[str, List[str]] = field(default_factory=dict)
    output_structure: Dict[str, str] = field(default_factory=dict)
    validation_capabilities: List[str] = field(default_factory=lambda: [
        "validate_manifest",
        "validate_project",
        "validate_build",
        "validate_runtime",
        "validate_artifacts"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "capabilities": self.capabilities.to_dict(),
            "versioning": self.versioning.to_dict(),
            "supported_features": self.supported_features,
            "supported_components": self.supported_variants if not self.supported_components and self.supported_variants else self.supported_components,
            "supported_variants": self.supported_variants,
            "output_structure": self.output_structure,
            "validation_capabilities": self.validation_capabilities,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderMetadata":
        cap_data = data.get("capabilities", {})
        ver_data = data.get("versioning", {})
        return cls(
            provider_id=str(data.get("provider_id", "")),
            display_name=str(data.get("display_name", "")),
            capabilities=ProviderCapabilityModel.from_dict(cap_data) if isinstance(cap_data, dict) else cap_data,
            versioning=ProviderVersioning.from_dict(ver_data) if isinstance(ver_data, dict) else ver_data,
            supported_features=list(data.get("supported_features", [])),
            supported_components=list(data.get("supported_components", [])),
            supported_variants=dict(data.get("supported_variants", {})),
            output_structure=dict(data.get("output_structure", {})),
            validation_capabilities=list(data.get("validation_capabilities", [
                "validate_manifest", "validate_project", "validate_build", "validate_runtime", "validate_artifacts"
            ])),
        )


@dataclass
class RenderingContext:
    """
    Encapsulates all inputs required for rendering and validation operations,
    preventing method signature expansion as new requirements emerge.
    """
    render_project: Any  # RenderProject
    manifest: Any        # ComponentManifest
    metadata: Optional[ProviderMetadata] = None
    tokens: List[Any] = field(default_factory=list)  # List[RenderToken]
    assets: List[Any] = field(default_factory=list)  # List[RenderAsset]
    output_config: Dict[str, Any] = field(default_factory=dict)
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    interaction_model: Optional[Any] = None  # InteractionModel

    @classmethod
    def from_project(
        cls,
        render_project: Any,
        manifest: Optional[Any] = None,
        metadata: Optional[ProviderMetadata] = None,
        output_config: Optional[Dict[str, Any]] = None,
        feature_flags: Optional[Dict[str, bool]] = None,
        interaction_model: Optional[Any] = None,
    ) -> "RenderingContext":
        """
        Factory method constructing a RenderingContext directly from a RenderProject.
        Automatically resolves manifest, tokens, assets, and interaction_model if omitted.
        """
        if manifest is None:
            # Dynamically import ComponentManifest to avoid circular dependency
            from ..component_manifest import ComponentManifest
            manifest = ComponentManifest.from_render_project(render_project)

        if interaction_model is None:
            from ..interaction_builder import InteractionBuilder
            interaction_model = InteractionBuilder.build(render_project, manifest)

        tokens = getattr(render_project, "tokens", [])
        assets = getattr(render_project, "global_assets", [])

        return cls(
            render_project=render_project,
            manifest=manifest,
            metadata=metadata,
            tokens=list(tokens) if tokens else [],
            assets=list(assets) if assets else [],
            output_config=output_config or {},
            feature_flags=feature_flags or {},
            interaction_model=interaction_model,
        )


class RenderingProvider(ABC):
    """
    Abstract Base Class establishing the authoritative provider contract for all
    multi-renderer target implementations in Nexora Studio.
    """

    def __init__(self, **kwargs):
        self.config = kwargs.get('config', {})
        self.env = kwargs.get('env', None)

    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        """
        Return authoritative provider metadata, versioning, and capability declarations.
        """
        pass

    @abstractmethod
    def generate_project(self, context: RenderingContext) -> Dict[str, Any]:
        """
        Synthesize a complete, production-ready project package from the RenderingContext.
        Returns a structured summary including project_structure, metadata, and validation results.
        """
        pass

    @abstractmethod
    def generate_components(self, context: RenderingContext) -> Dict[str, str]:
        """
        Synthesize reusable atomic and organism UI components.
        Returns a dictionary mapping relative file paths to rendered source code strings.
        """
        pass

    @abstractmethod
    def generate_pages(self, context: RenderingContext) -> Dict[str, str]:
        """
        Synthesize page views composing layouts and section components.
        Returns a dictionary mapping relative file paths to rendered source code strings.
        """
        pass

    @abstractmethod
    def generate_layouts(self, context: RenderingContext) -> Dict[str, str]:
        """
        Synthesize hierarchical, responsive layout wrapper components.
        Returns a dictionary mapping relative file paths to rendered source code strings.
        """
        pass

    @abstractmethod
    def generate_routes(self, context: RenderingContext) -> Dict[str, str]:
        """
        Synthesize modular routing tables and root application containers.
        Returns a dictionary mapping relative file paths to rendered source code strings.
        """
        pass

    @abstractmethod
    def generate_assets(self, context: RenderingContext) -> Dict[str, str]:
        """
        Synthesize asset registries and static binding configurations.
        Returns a dictionary mapping relative file paths to rendered source code strings.
        """
        pass

    @abstractmethod
    def generate_design_tokens(self, context: RenderingContext) -> Dict[str, str]:
        """
        Synthesize authoritative stylesheets and token variable bindings.
        Returns a dictionary mapping relative file paths to rendered source code strings.
        """
        pass

    # Expanded 5-Part Validation Contract

    @abstractmethod
    def validate_manifest(self, context: RenderingContext) -> Dict[str, Any]:
        """
        Validate that the ComponentManifest in context satisfies provider requirements.
        """
        pass

    @abstractmethod
    def validate_project(self, context: RenderingContext, project_structure: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate structural integrity, required file presence, and syntax health of generated code.
        """
        pass

    @abstractmethod
    def validate_build(self, context: RenderingContext, build_output: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate compile-time health and toolchain bundling (e.g., Vite/esbuild production builds).
        """
        pass

    @abstractmethod
    def validate_runtime(self, context: RenderingContext, runtime_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate runtime server execution, HTTP responsiveness, and DOM hierarchy health.
        """
        pass

    @abstractmethod
    def validate_artifacts(self, context: RenderingContext, artifacts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate visual artifacts, screenshots, and accessibility compliance evidence.
        """
        pass

    def process_blueprint(self, blueprint: Any, **kwargs) -> Dict[str, Any]:
        """
        Unified provider contract bridge. Transforms the input design blueprint or
        planning bundle into an authoritative RenderProject and executes generate_project().
        """
        from ..render_domain import RenderProject
        render_project = RenderProject.from_generation_bundle(blueprint, **kwargs)
        context = RenderingContext.from_project(
            render_project=render_project,
            output_config=kwargs.get('output_config', {}),
            feature_flags=kwargs.get('feature_flags', {})
        )
        return self.generate_project(context)

