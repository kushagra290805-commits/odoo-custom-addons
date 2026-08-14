import logging
import os
from typing import Any, List, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, ValidationReport

from odoo.addons.nexora_studio.services.design.design_blueprint import DesignBlueprint

_logger = logging.getLogger(__name__)

class ValidationEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ValidationEngine (Delegating to DesignOrchestrator)...")
        
        issues = []
        a11y_score = 100
        seo_score = 100
        perf_score = 100
        
        # 1. Orchestrate Design Validation
        try:
            # We convert our Blueprint payload into a DesignBlueprint for the validator
            bp_dict = {
                "project_name": artifact.requirements.domain or 'unknown',
                "project_id": artifact.requirements.domain or 'unknown',
                "pages": []
            }
            component_hierarchy = artifact.architecture.component_hierarchy if hasattr(artifact.architecture, "component_hierarchy") else {}
            for comp_id, comp_data in component_hierarchy.items():
                if comp_data.get("type") != "page": continue
                path = comp_data.get("path", "/")
                sections = comp_data.get("sections", ["Hero", "Content"])
                
                page_dict = {
                    "path": path,
                    "title": path.strip('/') or 'Home',
                    "sections": []
                }
                for sec in sections:
                    page_dict["sections"].append({
                        "id": f"sec_{sec}",
                        "name": sec,
                        "components": [{"id": f"comp_{sec}", "name": sec, "category": sec}]
                    })
                bp_dict["pages"].append(page_dict)
                
            bp = DesignBlueprint.from_dict(bp_dict)
            
            # Delegate to canonical orchestrator
            design_val = self.orchestrator.env['nexora.design_orchestrator'].validate_design(bp)
            
            issues.extend(design_val.get("issues", []))
            scores = design_val.get("scores", {})
            a11y_score = scores.get("accessibility", a11y_score)
            perf_score = scores.get("performance", perf_score)
            
        except Exception as e:
            _logger.error(f"Design Validation integration failed: {e}")
            issues.append({"type": "error", "message": f"Design validation failed: {str(e)}", "category": "system"})

        # 2. Basic SEO Validation
        for path, page in artifact.content.pages.items():
            seo = page.get("seo", {})
            if not seo.get("title"):
                issues.append({"type": "error", "message": f"Page {path} is missing SEO title.", "category": "seo"})
                seo_score -= 15
            if not seo.get("description"):
                issues.append({"type": "error", "message": f"Page {path} is missing SEO description.", "category": "seo"})
                seo_score -= 15
        # 3. Dynamic Validation (via Capability Router)
        workspace_path = artifact.workspace.project_path
        if workspace_path and os.path.exists(workspace_path):
            try:
                _logger.info("Running dynamic validation pipeline...")
                if hasattr(runtime, 'orchestrator'):
                    context_overrides = {
                        "shared_variables": {"workspace_path": workspace_path},
                        "artifacts": {"landing_page_html": artifact.content.pages.get("/", {}).get("html", "")}
                    }
                    
                    trace = runtime.orchestrator.execute_plan(
                        "Validate the generated website workspace",
                        target_outputs=["validation_report"],
                        context_overrides=context_overrides
                    )
                    
                    if trace.steps_failed:
                        issues.append({"type": "error", "message": f"Dynamic validation step(s) failed: {trace.steps_failed}", "category": "validation"})
                else:
                    _logger.warning("Production orchestrator not available for dynamic validation.")
            except Exception as e:
                issues.append({"type": "error", "message": f"Dynamic validation execution failed: {e}", "category": "validation"})
                
        a11y_score = max(0, a11y_score)
        seo_score = max(0, seo_score)
        perf_score = max(0, perf_score)
        
        passed = len([i for i in issues if i["type"] == "error"]) == 0
        
        model = ValidationReport(
            passed=passed,
            accessibility_score=a11y_score,
            seo_score=seo_score,
            performance_score=perf_score,
            issues=issues
        )
        return EngineExecutionResult(success=True, artifact=artifact.evolve(validation=model), metadata={"validation_issues_count": len(issues)}, error=None)
