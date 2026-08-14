import logging
from typing import Any, Dict, List
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class ReviewEngine(BaseGenerationEngine):
    """
    Canonical owner of all qualitative review.
    Executes specific reviewers (Section, Page, CrossPage, BusinessGoal, Brand, Design)
    via UCEL based on the requested review scope.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ReviewEngine (Phase 21E.2 Canonical Engine)...")
        # ReviewEngine handles reviews sequentially or selectively if requested
        # For this standalone engine execution, we default to full cross-page, business, brand review.
        # But this engine also exposes a direct review interface for iterative loop usage inside CodeGenerationEngine or Pipeline.
        
        issues = []
        
        # 1. Cross Page Review
        cross_issues = self._run_reviewer("mcp.crosspage_reviewer", artifact, runtime)
        issues.extend(cross_issues)
        
        # 2. Business Goal Review
        business_issues = self._run_reviewer("mcp.business_goal_reviewer", artifact, runtime)
        issues.extend(business_issues)
        
        # 3. Brand Review
        brand_issues = self._run_reviewer("mcp.brand_reviewer", artifact, runtime)
        issues.extend(brand_issues)
        
        # 4. Design Review
        design_issues = self._run_reviewer("mcp.design_reviewer", artifact, runtime)
        issues.extend(design_issues)

        # Artifact validation field is updated with these qualitative issues, alongside ValidationEngine's static checks
        validation_report = artifact.validation
        all_issues = list(validation_report.issues) + issues
        passed = validation_report.passed and len([i for i in issues if i.get("severity") == "error"]) == 0
        
        import dataclasses
        new_validation = dataclasses.replace(validation_report, passed=passed, issues=all_issues)
        
        return EngineExecutionResult(
            success=True, 
            artifact=artifact.evolve(validation=new_validation), 
            metadata={"qualitative_issues_found": len(issues)}, 
            error=None
        )
        
    def _run_reviewer(self, tool_namespace: str, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> List[Dict[str, Any]]:
        try:
            res = runtime.tools.execute(tool_namespace, {"artifact": "serialized_payload_placeholder"}, runtime)
            if res and isinstance(res, list):
                return res
            return []
        except Exception as e:
            _logger.warning(f"ReviewEngine: {tool_namespace} unavailable or failed: {e}")
            return []

    def review_section(self, section_name: str, code: str, runtime: 'GenerationRuntime') -> List[Dict[str, Any]]:
        """Used iteratively by the pipeline/generators to review a specific section."""
        try:
            res = runtime.tools.execute("mcp.section_reviewer", {"section": section_name, "code": code}, runtime)
            return res if isinstance(res, list) else []
        except Exception as e:
            _logger.warning(f"ReviewEngine: section_reviewer unavailable: {e}")
            return []
            
    def review_page(self, page_name: str, code: str, runtime: 'GenerationRuntime') -> List[Dict[str, Any]]:
        """Used iteratively to review an entire page."""
        try:
            res = runtime.tools.execute("mcp.page_reviewer", {"page": page_name, "code": code}, runtime)
            return res if isinstance(res, list) else []
        except Exception as e:
            _logger.warning(f"ReviewEngine: page_reviewer unavailable: {e}")
            return []
