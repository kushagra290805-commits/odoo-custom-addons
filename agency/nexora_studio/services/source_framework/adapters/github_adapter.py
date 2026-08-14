# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from .base_adapter import BaseProviderAdapter
from ..domain_models import ComponentPackage, Provenance, ComponentMetadata
import datetime
import json

import warnings

class GitHubAdapter(BaseProviderAdapter):
    """
    DEPRECATED (Phase 23.1).
    This legacy adapter bypasses the Universal Capability Execution Layer (UCEL).
    MIGRATION REFERENCE: Use the canonical 'nexora.provider.github' model instead.
    """
    def __init__(self, transport: Optional[Any] = None, config: Optional[Dict[str, Any]] = None):
        warnings.warn(
            "GitHubAdapter is deprecated and will be removed. "
            "Please migrate to the canonical nexora.provider.github model.",
            DeprecationWarning, stacklevel=2
        )
        super().__init__(transport, config)
        if self.transport is None:
            from ..transport.mock_transport import MockTransport
            self.transport = MockTransport({
                "github_search": lambda args: {
                    "items": [{"full_name": f"github_repo_{args.get('query', 'default')}", "stargazers_count": 100, "license": "MIT"}]
                }
            })
        
    @property
    def capabilities(self) -> List[str]:
        return ['SEARCH', 'DOWNLOAD', 'DEPENDENCY_DISCOVERY', 'LICENSE_INFORMATION', 'RELEASES', 'CHANGELOG']
        
    def _create_package(self, repo_id: str, repo_data: Dict[str, Any]) -> ComponentPackage:
        # Normalize repository payload
        name = repo_data.get("full_name", repo_data.get("name", f"GitHub Repo {repo_id}"))
        releases = repo_data.get("releases", [])
        if not isinstance(releases, list):
            releases = []
            
        package = ComponentPackage(
            component_id=repo_id,
            name=name,
            provenance=Provenance(
                provider="github",
                repository=repo_id,
                import_timestamp=str(datetime.datetime.now()),
                license=repo_data.get("license", "Unknown")
            ),
            extended_metadata=ComponentMetadata(
                source_id=repo_id,
                releases=releases,
                changelog_url=f"https://github.com/{repo_id}/blob/main/CHANGELOG.md",
                health_metadata={"stars": repo_data.get("stargazers_count", 0)}
            )
        )
        return package
        
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        try:
            res = self.transport.call_tool("github_search", {"query": query})
        except Exception as e:
            print(f"GitHub transport failed: {str(e)}")
            return []
            
        packages = []
        for repo in res.get("items", []):
            if not isinstance(repo, dict) or "full_name" not in repo:
                continue # Malformed
            packages.append(self._create_package(repo["full_name"], repo))
        return packages
        
    def get_component(self, component_id: str) -> ComponentPackage:
        res = self.transport.call_tool("github_get_repo", {"repo": component_id})
        return self._create_package(component_id, res)
        
    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        return {"source": "github", "repo": component_id}
        
    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return {}
        
    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        try:
            res = self.transport.call_tool("github_read_file", {"repo": component_id, "path": "package.json"})
            content = res.get("content", "{}")
            pkg_data = json.loads(content)
            deps = pkg_data.get("dependencies", {})
            return [{"package": k, "version": v} for k, v in deps.items()]
        except Exception:
            return []
        
    def get_license(self, component_id: str) -> str:
        try:
            res = self.transport.call_tool("github_get_repo", {"repo": component_id})
            return res.get("license", "Unknown")
        except Exception:
            return "Unknown"
        
    def get_installation_guide(self, component_id: str) -> str:
        try:
            res = self.transport.call_tool("github_read_file", {"repo": component_id, "path": "README.md"})
            return res.get("content", "No README found.")
        except Exception:
            return "No README found."
