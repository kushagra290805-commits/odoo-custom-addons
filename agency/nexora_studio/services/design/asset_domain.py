# -*- coding: utf-8 -*-
"""
Asset Domain Models — Phase 11F: AI Asset Planning & Content Intelligence Engine.

Defines provider-neutral, rendering-neutral domain classes for representing assets,
priorities, lifecycles, licenses, dependencies, collections, requirements, and AI prompt
specifications without referencing React, HTML, CSS, Three.js, or Penpot canvas schemas.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid


class AssetPriority:
    """Standard asset priority classification levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"

    @classmethod
    def is_valid(cls, val: str) -> bool:
        return val.lower() in {cls.CRITICAL, cls.HIGH, cls.MEDIUM, cls.LOW, cls.OPTIONAL}


class AssetLifecycle:
    """
    Provider-neutral asset lifecycle state model.
    Independent of asset source (generated, user-supplied, reusable).
    """
    PLANNED = "planned"
    REQUESTED = "requested"
    GENERATED = "generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REPLACED = "replaced"
    PUBLISHED = "published"
    ARCHIVED = "archived"

    @classmethod
    def is_valid(cls, val: str) -> bool:
        return val.lower() in {
            cls.PLANNED, cls.REQUESTED, cls.GENERATED, cls.REVIEWED, cls.APPROVED,
            cls.REJECTED, cls.REPLACED, cls.PUBLISHED, cls.ARCHIVED
        }


@dataclass
class PromptSpecification:
    """
    Structured, provider-neutral AI prompt specification for asset generation.
    Does not invoke AI models; declares exact parameters for downstream generation workers.
    """
    prompt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: str = "image"                   # 'image', 'illustration', '3d_asset', 'icon'
    subject_description: str = ""
    style_keywords: List[str] = field(default_factory=list)
    lighting_mood: str = "natural"
    color_palette_constraints: List[str] = field(default_factory=list)
    aspect_ratio: str = "16:9"                  # '16:9', '4:3', '1:1', '9:16'
    negative_prompt: str = "blurry, low quality, distorted, text, watermarks"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptSpecification':
        if not data:
            return cls()
        return cls(
            prompt_id=data.get('prompt_id', str(uuid.uuid4())),
            asset_type=data.get('asset_type', 'image').lower(),
            subject_description=data.get('subject_description', ''),
            style_keywords=data.get('style_keywords', []),
            lighting_mood=data.get('lighting_mood', 'natural'),
            color_palette_constraints=data.get('color_palette_constraints', []),
            aspect_ratio=data.get('aspect_ratio', '16:9'),
            negative_prompt=data.get('negative_prompt', 'blurry, low quality, distorted, text, watermarks'),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'prompt_id': self.prompt_id,
            'asset_type': self.asset_type,
            'subject_description': self.subject_description,
            'style_keywords': self.style_keywords,
            'lighting_mood': self.lighting_mood,
            'color_palette_constraints': self.color_palette_constraints,
            'aspect_ratio': self.aspect_ratio,
            'negative_prompt': self.negative_prompt,
            'metadata': self.metadata
        }


@dataclass
class AssetLicense:
    """
    Licensing and attribution metadata for assets.
    """
    license_type: str = "proprietary"           # 'proprietary', 'cc0', 'cc-by', 'commercial', 'user-supplied'
    attribution_required: bool = False
    source_url: Optional[str] = None
    commercial_use: bool = True
    modification_allowed: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetLicense':
        if not data:
            return cls()
        return cls(
            license_type=data.get('license_type', 'proprietary').lower(),
            attribution_required=bool(data.get('attribution_required', False)),
            source_url=data.get('source_url'),
            commercial_use=bool(data.get('commercial_use', True)),
            modification_allowed=bool(data.get('modification_allowed', True))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'license_type': self.license_type,
            'attribution_required': self.attribution_required,
            'source_url': self.source_url,
            'commercial_use': self.commercial_use,
            'modification_allowed': self.modification_allowed
        }


@dataclass
class AssetMetadata:
    """
    Technical and accessibility metadata for an asset.
    """
    width_px: int = 1200
    height_px: int = 800
    aspect_ratio: str = "16:9"
    file_format: str = "webp"                   # 'webp', 'svg', 'png', 'jpg', 'glb', 'gltf'
    color_space: str = "srgb"                   # 'srgb', 'p3'
    alt_text: str = ""
    aria_role: str = "img"                      # 'img', 'presentation', 'decorative'
    file_size_kb_max: int = 2048

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetMetadata':
        if not data:
            return cls()
        return cls(
            width_px=int(data.get('width_px', 1200)),
            height_px=int(data.get('height_px', 800)),
            aspect_ratio=data.get('aspect_ratio', '16:9'),
            file_format=data.get('file_format', 'webp').lower(),
            color_space=data.get('color_space', 'srgb').lower(),
            alt_text=data.get('alt_text', ''),
            aria_role=data.get('aria_role', 'img').lower(),
            file_size_kb_max=int(data.get('file_size_kb_max', 2048))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'width_px': self.width_px,
            'height_px': self.height_px,
            'aspect_ratio': self.aspect_ratio,
            'file_format': self.file_format,
            'color_space': self.color_space,
            'alt_text': self.alt_text,
            'aria_role': self.aria_role,
            'file_size_kb_max': self.file_size_kb_max
        }


@dataclass
class AssetDependency:
    """
    Expresses dependencies between assets (e.g. fallback images, variants, thumbnails, textures).
    """
    dependent_asset_id: str = ""
    dependency_type: str = "fallback"           # 'fallback', 'variant', 'thumbnail', 'texture'
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetDependency':
        if not data:
            return cls()
        return cls(
            dependent_asset_id=data.get('dependent_asset_id', ''),
            dependency_type=data.get('dependency_type', 'fallback').lower(),
            description=data.get('description', '')
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'dependent_asset_id': self.dependent_asset_id,
            'dependency_type': self.dependency_type,
            'description': self.description
        }


@dataclass
class AssetDefinition:
    """
    First-class domain definition of a required, optional, or reusable asset.
    """
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unnamed Asset"
    asset_type: str = "image"                   # 'image', 'illustration', '3d_asset', 'icon', 'video', 'audio', 'document'
    priority: str = AssetPriority.MEDIUM
    lifecycle: str = AssetLifecycle.PLANNED
    source_type: str = "generated"              # 'generated', 'reusable', 'user_supplied', 'missing'
    metadata: AssetMetadata = field(default_factory=AssetMetadata)
    license: AssetLicense = field(default_factory=AssetLicense)
    dependencies: List[AssetDependency] = field(default_factory=list)
    prompt_spec: Optional[PromptSpecification] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetDefinition':
        if not data:
            return cls()
        meta_data = data.get('metadata')
        lic_data = data.get('license')
        deps_data = data.get('dependencies', [])
        prompt_data = data.get('prompt_spec')
        
        return cls(
            asset_id=data.get('asset_id', str(uuid.uuid4())),
            name=data.get('name', 'Unnamed Asset'),
            asset_type=data.get('asset_type', 'image').lower(),
            priority=data.get('priority', AssetPriority.MEDIUM).lower(),
            lifecycle=data.get('lifecycle', AssetLifecycle.PLANNED).lower(),
            source_type=data.get('source_type', 'generated').lower(),
            metadata=AssetMetadata.from_dict(meta_data) if isinstance(meta_data, dict) else (meta_data or AssetMetadata()),
            license=AssetLicense.from_dict(lic_data) if isinstance(lic_data, dict) else (lic_data or AssetLicense()),
            dependencies=[AssetDependency.from_dict(d) if isinstance(d, dict) else d for d in deps_data],
            prompt_spec=PromptSpecification.from_dict(prompt_data) if isinstance(prompt_data, dict) else prompt_data
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'asset_id': self.asset_id,
            'name': self.name,
            'asset_type': self.asset_type,
            'priority': self.priority,
            'lifecycle': self.lifecycle,
            'source_type': self.source_type,
            'metadata': self.metadata.to_dict() if hasattr(self.metadata, 'to_dict') else self.metadata,
            'license': self.license.to_dict() if hasattr(self.license, 'to_dict') else self.license,
            'dependencies': [d.to_dict() if hasattr(d, 'to_dict') else d for d in self.dependencies],
            'prompt_spec': self.prompt_spec.to_dict() if self.prompt_spec and hasattr(self.prompt_spec, 'to_dict') else None
        }


@dataclass
class AssetCollection:
    """
    Logical grouping of related assets (e.g. brand icons, hero media pack).
    """
    collection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Asset Collection"
    assets: List[AssetDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetCollection':
        if not data:
            return cls()
        assets_data = data.get('assets', [])
        return cls(
            collection_id=data.get('collection_id', str(uuid.uuid4())),
            name=data.get('name', 'Asset Collection'),
            assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in assets_data]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'collection_id': self.collection_id,
            'name': self.name,
            'assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.assets]
        }


@dataclass
class AssetReference:
    """
    Reference tying an asset ID to a target component or layout region in the blueprint.
    """
    ref_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = ""
    target_component_id: Optional[str] = None
    target_region: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetReference':
        if not data:
            return cls()
        return cls(
            ref_id=data.get('ref_id', str(uuid.uuid4())),
            asset_id=data.get('asset_id', ''),
            target_component_id=data.get('target_component_id'),
            target_region=data.get('target_region')
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ref_id': self.ref_id,
            'asset_id': self.asset_id,
            'target_component_id': self.target_component_id,
            'target_region': self.target_region
        }


@dataclass
class AssetRequirement:
    """
    Declarative specification of an asset requirement from a component or section.
    """
    req_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: str = "image"
    description: str = ""
    mandatory: bool = True
    priority: str = AssetPriority.HIGH

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetRequirement':
        if not data:
            return cls()
        return cls(
            req_id=data.get('req_id', str(uuid.uuid4())),
            asset_type=data.get('asset_type', 'image').lower(),
            description=data.get('description', ''),
            mandatory=bool(data.get('mandatory', True)),
            priority=data.get('priority', AssetPriority.HIGH).lower()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'req_id': self.req_id,
            'asset_type': self.asset_type,
            'description': self.description,
            'mandatory': self.mandatory,
            'priority': self.priority
        }


@dataclass
class AssetPlan:
    """
    Root aggregate representing the comprehensive asset plan for a design blueprint.
    Classifies assets by source and priority, and collects provider-neutral prompt specifications.
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_name: str = "Unnamed Project"
    required_assets: List[AssetDefinition] = field(default_factory=list)
    optional_assets: List[AssetDefinition] = field(default_factory=list)
    reusable_assets: List[AssetDefinition] = field(default_factory=list)
    missing_assets: List[AssetDefinition] = field(default_factory=list)
    generated_assets: List[AssetDefinition] = field(default_factory=list)
    user_supplied_assets: List[AssetDefinition] = field(default_factory=list)
    prompt_specifications: List[PromptSpecification] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetPlan':
        if not data:
            return cls()
        return cls(
            plan_id=data.get('plan_id', str(uuid.uuid4())),
            project_name=data.get('project_name', 'Unnamed Project'),
            required_assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in data.get('required_assets', [])],
            optional_assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in data.get('optional_assets', [])],
            reusable_assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in data.get('reusable_assets', [])],
            missing_assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in data.get('missing_assets', [])],
            generated_assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in data.get('generated_assets', [])],
            user_supplied_assets=[AssetDefinition.from_dict(a) if isinstance(a, dict) else a for a in data.get('user_supplied_assets', [])],
            prompt_specifications=[PromptSpecification.from_dict(p) if isinstance(p, dict) else p for p in data.get('prompt_specifications', [])],
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'project_name': self.project_name,
            'required_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.required_assets],
            'optional_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.optional_assets],
            'reusable_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.reusable_assets],
            'missing_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.missing_assets],
            'generated_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.generated_assets],
            'user_supplied_assets': [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.user_supplied_assets],
            'prompt_specifications': [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.prompt_specifications],
            'metadata': self.metadata
        }
