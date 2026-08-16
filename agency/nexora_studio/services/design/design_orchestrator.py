# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
from typing import Dict, Any, Optional
from .design_provider import DesignProvider

_logger = logging.getLogger(__name__)

class DesignOrchestrator(models.AbstractModel):
    """
    Design Orchestrator — Central routing and governance layer for Design Provider operations.
    
    Builder Sessions and other subsystems interact exclusively with this orchestrator or
    via the DesignProvider interface. The orchestrator routes operations to the active
    default provider (PenpotDesignProvider), injecting Odoo environment context for
    configuration resolution and pre-flight validation.
    """
    _name = 'nexora.design_orchestrator'
    _description = 'Design Orchestrator Service'

    @api.model
    def get_provider(self, provider_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Resolve and return the requested DesignProvider or RenderingProvider instance.
        
        Defaults to 'penpot' (PenpotDesignProvider) if no provider is specified.
        Injects Odoo self.env to enable 4-tier configuration precedence resolution.
        """
        target_provider = (provider_name or 'react').lower()
        
        from .providers.provider_registry import RenderingProviderRegistry
        try:
            return RenderingProviderRegistry.get_provider(target_provider, config=config, env=self.env)
        except (ValueError, NotImplementedError):
            pass
        
        raise ValidationError(_("Unsupported design provider: %s.") % target_provider)



    @api.model
    def validate_provider_connection(self, provider_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform a pre-flight connection and health check against the target design provider.
        """
        provider = self.get_provider(provider_name=provider_name, config=config)
        if hasattr(provider, 'client') and hasattr(provider.client, 'validate_connection'):
            return provider.client.validate_connection()
            
        return {
            "status": "ok",
            "reachable": True,
            "authenticated": True,
            "provider": provider_name or "penpot",
            "note": "Provider does not expose explicit live connection validation."
        }

    @api.model
    def execute_operation(self, operation: str, provider_name: Optional[str] = None, **kwargs) -> Any:
        """
        Execute a design operation on the specified or default provider.
        """
        provider = self.get_provider(provider_name=provider_name)
        if not hasattr(provider, operation):
            raise ValidationError(_("Operation '%s' is not supported by interface DesignProvider.") % operation)
        
        method = getattr(provider, operation)
        return method(**kwargs)

    @api.model
    def execute_blueprint(self, blueprint: Any, provider_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Consume a DesignBlueprint, route it through DesignSystemEngine for component
        composition resolution and validation (Phase 11D), route it through LayoutEngine for responsive
        layout adaptation and quality scoring (Phase 11E), and forward to the specified design provider.
        """
        from .blueprint_validator import BlueprintValidator
        
        val_res = BlueprintValidator.validate(blueprint)
        if not val_res.is_valid:
            _logger.warning("DesignBlueprint validation failed prior to execution: %s", val_res.errors)
            
        # Route through DesignSystemEngine (Phase 11D)
        sys_engine = self.env['nexora.design_system_engine']
        sys_res = sys_engine.process_blueprint(blueprint)
        enriched_bp = sys_res.get("enriched_blueprint", blueprint)
        if not sys_res.get("is_system_compliant"):
            _logger.warning("Design System validation reported warnings/errors prior to provider execution: %s", sys_res.get("validation_errors"))
            
        # Route through LayoutEngine (Phase 11E)
        layout_engine = self.env['nexora.layout_engine']
        layout_res = layout_engine.process_blueprint(enriched_bp)
        enriched_bp = layout_res.get("enriched_blueprint", enriched_bp)
        if not layout_res.get("is_layout_compliant"):
            _logger.warning("Layout Intelligence validation reported warnings/errors prior to provider execution: %s", layout_res.get("validation_errors"))
            
        # Route through AssetPlanningEngine (Phase 11F)
        asset_engine = self.env['nexora.asset_planning_engine']
        asset_res = asset_engine.process_blueprint(enriched_bp, kwargs)
        enriched_bp = asset_res.get("enriched_blueprint", enriched_bp)
        if not asset_res.get("is_asset_compliant"):
            _logger.warning("Asset Planning validation reported warnings/errors prior to provider execution: %s", asset_res.get("validation_errors"))
            
        # Route through ContentIntelligenceEngine (Phase 11F)
        content_engine = self.env['nexora.content_intelligence_engine']
        content_res = content_engine.process_blueprint(enriched_bp, kwargs)
        enriched_bp = content_res.get("enriched_blueprint", enriched_bp)
        if not content_res.get("is_content_compliant"):
            _logger.warning("Content Intelligence validation reported warnings/errors prior to provider execution: %s", content_res.get("validation_errors"))
            
        provider = self.get_provider(provider_name=provider_name)
        if not hasattr(provider, 'process_blueprint'):
            raise ValidationError(_("Provider '%s' does not support process_blueprint.") % (provider_name or 'default'))
            
        # Pass asset_plan and content_plan to provider
        kwargs['asset_plan'] = asset_res.get("asset_plan")
        kwargs['content_plan'] = content_res.get("content_plan")
        res = provider.process_blueprint(enriched_bp, **kwargs)
        res["design_system_compliance"] = {
            "is_compliant": sys_res.get("is_system_compliant"),
            "library_components_resolved": sys_res.get("library_components_resolved", [])
        }
        res["layout_intelligence_compliance"] = {
            "is_compliant": layout_res.get("is_layout_compliant"),
            "resolved_layouts_count": layout_res.get("resolved_layouts_count", 0),
            "quality_score": layout_res.get("quality_score", {}),
            "metrics": layout_res.get("validation_metrics", {})
        }
        res["asset_planning_compliance"] = {
            "is_compliant": asset_res.get("is_asset_compliant"),
            "quality_score": asset_res.get("quality_score", {}),
            "metrics": asset_res.get("validation_metrics", {})
        }
        res["content_intelligence_compliance"] = {
            "is_compliant": content_res.get("is_content_compliant"),
            "quality_score": content_res.get("quality_score", {}),
            "metrics": content_res.get("validation_metrics", {})
        }
        return res

    @api.model
    def validate_design(self, blueprint: Any) -> Dict[str, Any]:
        """
        Single canonical owner for design validation.
        Runs DesignSystem, Layout, and aggregates issues and scores.
        """
        from .design_system_validator import DesignSystemValidator
        from .layout_validator import LayoutValidator
        
        issues = []
        scores = {"accessibility": 100, "performance": 100, "seo": 100}
        
        ds_val = DesignSystemValidator.validate(blueprint)
        if not ds_val.is_valid:
            for err in ds_val.errors:
                issues.append({"type": "error", "message": f"[DesignSystem] {err}", "category": "design"})
            for warn in ds_val.warnings:
                issues.append({"type": "warning", "message": f"[DesignSystem] {warn}", "category": "design"})
                
        ly_val = LayoutValidator.validate(blueprint)
        if not ly_val.is_valid:
            for err in ly_val.errors:
                issues.append({"type": "error", "message": f"[Layout] {err}", "category": "layout"})
            for warn in ly_val.warnings:
                issues.append({"type": "warning", "message": f"[Layout] {warn}", "category": "layout"})
                
        if ly_val.quality_score:
            scores["accessibility"] = ly_val.quality_score.accessibility_score
            scores["performance"] = ly_val.quality_score.performance_score
            
        return {
            "issues": issues,
            "scores": scores
        }
