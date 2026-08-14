from typing import List, Optional
from .models import CapabilityManifest
from .repository import CapabilityRepository
import logging

_logger = logging.getLogger(__name__)

class CapabilityResolver:
    def __init__(self, repository: CapabilityRepository):
        self.repository = repository
        
    def resolve_candidates(self, namespace: str) -> List[CapabilityManifest]:
        manifests = self.repository.get_manifests_by_namespace(namespace)
        if not manifests and self.repository.env:
            _logger.info(f"Capability {namespace} not found. Triggering lazy installation via DependencyInstallerService...")
            # Example heuristic mapping to provider plugins
            provider_map = {
                'mcp.eslint': 'mcp.eslint',
                'mcp.playwright': 'mcp.playwright',
                'mcp.search': 'mcp.search',
                'mcp.page_reviewer': 'mcp.page_reviewer',
                'mcp.section_reviewer': 'mcp.section_reviewer',
                'mcp.crosspage_reviewer': 'mcp.crosspage_reviewer',
                'mcp.business_goal_reviewer': 'mcp.business_goal_reviewer',
                'mcp.brand_reviewer': 'mcp.brand_reviewer',
                'mcp.design_reviewer': 'mcp.design_reviewer'
            }
            if namespace in provider_map:
                try:
                    self.repository.env['nexora.capability_providers_service'].register_all_providers()
                    manifests = self.repository.get_manifests_by_namespace(namespace)
                except Exception as e:
                    _logger.error(f"Lazy installation failed: {e}")
        return manifests

    def resolve_by_capability(self, capability: str) -> List[CapabilityManifest]:
        """
        Resolves a list of provider manifests that declare support for a specific semantic capability.
        """
        all_manifests = self.repository.get_all_manifests()
        matching = []
        for manifest in all_manifests:
            supported = manifest.metadata.get('supported_capabilities', [])
            # Also fall back to capability_filters if supported_capabilities is not fully populated yet
            filters = manifest.metadata.get('capability_filters', [])
            if capability in supported or '*' in filters or '*' in supported:
                matching.append(manifest)
        return matching