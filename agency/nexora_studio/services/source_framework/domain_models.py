# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class Provenance:
    provider: str
    repository: Optional[str] = None
    commit_sha: Optional[str] = None
    release_version: Optional[str] = None
    license: Optional[str] = None
    import_source: Optional[str] = None
    import_timestamp: Optional[str] = None

@dataclass
class ComponentPackage:
    component_id: str
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    preview: Optional[Dict[str, Any]] = None
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    installation_guide: Optional[str] = None
    license: Optional[str] = None
    provenance: Optional[Provenance] = None
    compatibility_report: Optional[Dict[str, Any]] = None
    provider_information: Dict[str, Any] = field(default_factory=dict)
    design_tokens: Optional['DesignTokenPackage'] = None
    extended_metadata: Optional['ComponentMetadata'] = None
    extended_preview: Optional['ComponentPreview'] = None

@dataclass
class DesignTokenPackage:
    colors: Dict[str, str] = field(default_factory=dict)
    typography: Dict[str, Any] = field(default_factory=dict)
    spacing: Dict[str, str] = field(default_factory=dict)
    radius: Dict[str, str] = field(default_factory=dict)
    shadows: Dict[str, str] = field(default_factory=dict)
    effects: Dict[str, Any] = field(default_factory=dict)
    layout_grids: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComponentMetadata:
    source_id: str
    last_updated: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    version: Optional[str] = None
    releases: List[str] = field(default_factory=list)
    changelog_url: Optional[str] = None
    health_metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComponentPreview:
    preview_url: str
    type: str = "image"
    interactive: bool = False

@dataclass
class KnowledgeDocument:
    document_id: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None

@dataclass
class DesignAsset:
    asset_id: str
    name: str
    type: str
    url: Optional[str] = None
    design_tokens: Optional[DesignTokenPackage] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None

@dataclass
class RepositoryArtifact:
    artifact_id: str
    path: str
    content: Optional[str] = None
    type: str = "file"
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None

@dataclass
class BusinessData:
    data_id: str
    category: str
    payload: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Provenance] = None
