from typing import Dict, Any
from odoo.addons.nexora_studio.services.providers.provider_interface import ProviderInterface

class GitHubProvider(ProviderInterface):
    """Interface stub for GitHub REST operations."""
    def initialize(self) -> None:
        pass
        
    def health(self) -> Dict[str, Any]:
        return {"status": "ok"}
        
    def shutdown(self) -> None:
        pass
        
    # Future-proof interfaces designed per Phase 19B refinement
    def get_repository(self, repo_name: str) -> Dict[str, Any]:
        pass
        
    def get_template(self, template_id: str) -> Dict[str, Any]:
        pass
        
    def get_branch(self, branch_name: str) -> Dict[str, Any]:
        pass
        
    def create_commit(self, branch: str, files: Dict[str, str], message: str) -> str:
        """Minimal subset implemented for Phase 19B"""
        return "mock_commit_sha"
        
    def create_pull_request(self, head: str, base: str, title: str) -> str:
        pass
        
    def get_release(self, tag: str) -> Dict[str, Any]:
        pass
        
    def run_workflow_file(self, workflow_name: str) -> bool:
        pass
