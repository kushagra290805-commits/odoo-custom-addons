# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union

class DesignProvider(ABC):
    """
    Abstract interface for all Design Providers in Nexora Studio.
    
    This interface serves as the sole vendor-neutral abstraction used by Builder Sessions,
    Design Orchestrators, and future design integrations. No core module may depend
    directly on a specific vendor implementation (e.g., Penpot).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with the design provider using supplied credentials."""
        pass

    @abstractmethod
    def create_project(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new design project."""
        pass

    @abstractmethod
    def create_page(self, project_id: str, name: str) -> Dict[str, Any]:
        """Create a new page within an existing project."""
        pass

    @abstractmethod
    def create_component(self, page_id: str, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reusable design component on a specified page."""
        pass

    @abstractmethod
    def export_svg(self, node_id: str, options: Optional[Dict[str, Any]] = None) -> str:
        """Export a design node as an SVG string."""
        pass

    @abstractmethod
    def export_png(self, node_id: str, options: Optional[Dict[str, Any]] = None) -> bytes:
        """Export a design node as PNG binary data."""
        pass

    @abstractmethod
    def export_pdf(self, node_id: str, options: Optional[Dict[str, Any]] = None) -> bytes:
        """Export a design node as PDF binary data."""
        pass

    @abstractmethod
    def get_project(self, project_id: str) -> Dict[str, Any]:
        """Retrieve project metadata and structure."""
        pass

    @abstractmethod
    def create_workspace(self, name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a dedicated workspace for organizing design projects."""
        pass

    @abstractmethod
    def create_frame(self, page_id: str, frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a structural frame or canvas container on a page."""
        pass

    @abstractmethod
    def update_component(self, component_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update properties, tokens, or hierarchy of an existing component."""
        pass

    @abstractmethod
    def delete_component(self, component_id: str) -> bool:
        """Delete a component from a page or project."""
        pass

    @abstractmethod
    def create_design_tokens(self, project_id: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
        """Define or update design tokens (colors, typography, spacing) for a project."""
        pass

    @abstractmethod
    def apply_theme(self, project_id: str, theme_id: str) -> bool:
        """Apply a predefined theme or style collection to a project."""
        pass

    @abstractmethod
    def export_assets(self, node_ids: List[str], format: str = 'png') -> Dict[str, bytes]:
        """Batch export multiple design nodes into mapped binary assets."""
        pass

    @abstractmethod
    def import_assets(self, project_id: str, assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Import external media assets into a design project."""
        pass

    @abstractmethod
    def list_projects(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available design projects, optionally filtered by workspace."""
        pass

    @abstractmethod
    def sync_project(self, project_id: str) -> Dict[str, Any]:
        """Trigger a bidirectional synchronization of project state and design tokens."""
        pass

    @abstractmethod
    def validate_design(self, project_id: str, ruleset: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate a design project against accessibility, responsive, and design system rules."""
        pass

    @abstractmethod
    def process_blueprint(self, blueprint: Any, **kwargs) -> Dict[str, Any]:
        """
        Translate and process a DesignBlueprint into provider-specific design operations.
        Only supported provider operations may be executed; unsupported granular operations must be reported as deferred.
        """
        pass
