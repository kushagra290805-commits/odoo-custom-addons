# -*- coding: utf-8 -*-
"""
Asset Planning Engine Service — Phase 11F: AI Asset Planning & Content Intelligence Engine.

Odoo AbstractModel ('nexora.asset_planning_engine') responsible for scanning design
blueprints and component definitions to determine required, optional, reusable, missing,
generated, and user-supplied assets. Automatically generates structured, provider-neutral
AI prompt specifications without invoking external AI models or rendering technologies.
"""
from odoo import models, api, _
import logging
from typing import Dict, Any, Optional, List
from .asset_domain import (
    AssetPlan, AssetDefinition, AssetCollection, AssetReference, AssetRequirement,
    AssetPriority, AssetLifecycle, AssetLicense, AssetMetadata, AssetDependency,
    PromptSpecification
)
from .asset_content_validator import AssetContentValidator

_logger = logging.getLogger(__name__)


class AssetPlanningEngine(models.AbstractModel):
    """
    Asset Planning Engine Service.
    
    Transforms blueprint asset placeholders and component requirements into a first-class,
    provider-neutral AssetPlan with declarative AI prompt specifications and quality scoring.
    """
    _name = 'nexora.asset_planning_engine'
    _description = 'AI Asset Planning Engine Service'

    @api.model
    def _create_prompt_spec(self, asset_name: str, asset_type: str, project_name: str, style_keywords: List[str], color_palette: List[str], aspect_ratio: str = "16:9") -> PromptSpecification:
        """
        Construct a structured, provider-neutral AI prompt specification without invoking AI models.
        """
        subject_map = {
            "image": f"High-resolution professional photography depicting {asset_name.lower()} for {project_name}, clean composition, natural lighting.",
            "illustration": f"Modern digital illustration representing {asset_name.lower()}, sleek geometric shapes, corporate tech aesthetic for {project_name}.",
            "3d_asset": f"Abstract 3D rendering of {asset_name.lower()} for {project_name}, glassmorphism, soft studio lighting, metallic accents, isometric view.",
            "icon": f"Minimalist vector icon representing {asset_name.lower()} for {project_name}, clean pixel grid, bold outlines, scalable symbols."
        }

        subject = subject_map.get(asset_type, f"High quality visual asset representing {asset_name} for {project_name}.")
        
        return PromptSpecification(
            asset_type=asset_type,
            subject_description=subject,
            style_keywords=style_keywords or ["modern", "clean", "professional", "minimalist"],
            lighting_mood="soft studio lighting" if asset_type == "3d_asset" else "natural ambient",
            color_palette_constraints=color_palette or ["#3B82F6", "#1D4ED8", "#F8FAFC", "#0F172A"],
            aspect_ratio=aspect_ratio,
            negative_prompt="blurry, low resolution, distorted, text, watermarks, pixelated, amateur",
            metadata={"generated_for_project": project_name, "target_asset_name": asset_name}
        )

    @api.model
    def generate_asset_plan(self, requirements: Optional[Dict[str, Any]] = None, blueprint: Any = None) -> Dict[str, Any]:
        """
        Generate an AssetPlan by scanning client requirements and blueprint structures.
        """
        req = requirements or {}
        project_name = req.get('project_name', 'Unnamed Project')
        project_type = req.get('project_type', 'standard').lower()
        color_palette = req.get('color_palette', ["#3B82F6", "#1D4ED8", "#F8FAFC", "#0F172A"])
        style_keywords = req.get('style_keywords', ["modern", "clean", "professional", "premium"])

        plan = AssetPlan(project_name=project_name)

        # 1. Add baseline project logo / icon (User Supplied or Generated)
        logo_asset = AssetDefinition(
            name=f"{project_name} Brand Logo",
            asset_type="icon",
            priority=AssetPriority.CRITICAL,
            lifecycle=AssetLifecycle.REQUESTED if not req.get('logo_url') else AssetLifecycle.APPROVED,
            source_type="user_supplied" if req.get('logo_url') else "generated",
            metadata=AssetMetadata(width_px=200, height_px=60, aspect_ratio="10:3", file_format="svg", alt_text=f"{project_name} Official Logo", aria_role="img"),
            license=AssetLicense(license_type="user-supplied" if req.get('logo_url') else "proprietary", commercial_use=True)
        )
        if not req.get('logo_url'):
            logo_asset.prompt_spec = self._create_prompt_spec(f"{project_name} logo symbol", "icon", project_name, style_keywords, color_palette, "1:1")
            plan.prompt_specifications.append(logo_asset.prompt_spec)
            plan.generated_assets.append(logo_asset)
        else:
            logo_asset.license.source_url = req.get('logo_url')
            plan.user_supplied_assets.append(logo_asset)
        plan.required_assets.append(logo_asset)

        # 2. Add Hero visual asset (Image or 3D Asset)
        hero_type = "3d_asset" if project_type in ("saas", "tech", "ai", "dashboard") else "image"
        hero_asset = AssetDefinition(
            name="Hero Section Primary Media",
            asset_type=hero_type,
            priority=AssetPriority.HIGH,
            lifecycle=AssetLifecycle.PLANNED,
            source_type="generated",
            metadata=AssetMetadata(width_px=1920, height_px=1080, aspect_ratio="16:9", file_format="glb" if hero_type == "3d_asset" else "webp", alt_text=f"{project_name} Hero Visual", aria_role="img"),
            license=AssetLicense(license_type="proprietary", commercial_use=True)
        )
        hero_asset.prompt_spec = self._create_prompt_spec("Hero showcase visual", hero_type, project_name, style_keywords, color_palette, "16:9")
        plan.prompt_specifications.append(hero_asset.prompt_spec)
        plan.generated_assets.append(hero_asset)
        plan.required_assets.append(hero_asset)

        # 3. Scan blueprint sections if provided
        bp_dict = blueprint.to_dict() if hasattr(blueprint, 'to_dict') else (blueprint if isinstance(blueprint, dict) else {})
        pages = bp_dict.get('pages', [])
        for page in pages:
            sections = page.get('sections', []) if isinstance(page, dict) else getattr(page, 'sections', [])
            for sec in sections:
                sec_type = sec.get('section_type', '').lower() if isinstance(sec, dict) else getattr(sec, 'section_type', '').lower()
                sec_name = sec.get('name', 'Section') if isinstance(sec, dict) else getattr(sec, 'name', 'Section')
                
                if sec_type in ("features", "services", "grid", "gallery", "ecommerce"):
                    for i in range(3):
                        feat_asset = AssetDefinition(
                            name=f"{sec_name} Item {i+1} Illustration",
                            asset_type="illustration" if sec_type == "features" else "image",
                            priority=AssetPriority.MEDIUM,
                            lifecycle=AssetLifecycle.PLANNED,
                            source_type="generated",
                            metadata=AssetMetadata(width_px=600, height_px=400, aspect_ratio="3:2", file_format="svg" if sec_type == "features" else "webp", alt_text=f"{sec_name} illustration {i+1}", aria_role="img"),
                            license=AssetLicense(license_type="proprietary", commercial_use=True)
                        )
                        feat_asset.prompt_spec = self._create_prompt_spec(f"{sec_name} feature {i+1}", feat_asset.asset_type, project_name, style_keywords, color_palette, "3:2")
                        plan.prompt_specifications.append(feat_asset.prompt_spec)
                        plan.generated_assets.append(feat_asset)
                        plan.optional_assets.append(feat_asset)
                elif sec_type in ("testimonials", "team"):
                    reusable_avatar = AssetDefinition(
                        name=f"{sec_name} Reusable Avatar Placeholder",
                        asset_type="image",
                        priority=AssetPriority.LOW,
                        lifecycle=AssetLifecycle.APPROVED,
                        source_type="reusable",
                        metadata=AssetMetadata(width_px=128, height_px=128, aspect_ratio="1:1", file_format="webp", alt_text="User Avatar Placeholder", aria_role="presentation"),
                        license=AssetLicense(license_type="cc0", source_url="https://ui-avatars.com", commercial_use=True)
                    )
                    if not any(a.name == reusable_avatar.name for a in plan.reusable_assets):
                        plan.reusable_assets.append(reusable_avatar)

        # Check for pre-existing planned assets in blueprint metadata or existing asset_plan
        existing_summary = bp_dict.get('metadata', {}).get('asset_plan_summary', {}) or bp_dict.get('asset_plan', {})
        if isinstance(existing_summary, dict):
            for k in ['planned_assets', 'required_assets', 'optional_assets', 'reusable_assets', 'generated_assets', 'user_supplied_assets', 'assets']:
                for a_data in existing_summary.get(k, []):
                    a_obj = AssetDefinition.from_dict(a_data) if isinstance(a_data, dict) else a_data
                    if not any(existing.asset_id == a_obj.asset_id or existing.name == a_obj.name for existing in plan.required_assets + plan.optional_assets + plan.reusable_assets):
                        plan.required_assets.append(a_obj)

        # 4. Validate AssetPlan via AssetContentValidator
        val_res = AssetContentValidator.validate(blueprint=blueprint, asset_plan=plan, content_plan=None)

        return {
            "status": "success",
            "is_valid": val_res.is_valid,
            "asset_plan": plan.to_dict(),
            "quality_score": val_res.quality_score.to_dict(),
            "validation_metrics": val_res.metrics,
            "validation_errors": val_res.errors,
            "validation_warnings": val_res.warnings
        }

    @api.model
    def process_blueprint(self, blueprint: Any, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Consume a candidate blueprint, generate its AssetPlan, attach it to the blueprint,
        and return validation compliance report.
        """
        res = self.generate_asset_plan(requirements=requirements, blueprint=blueprint)
        plan_dict = res.get("asset_plan", {})

        # Attach asset plan to blueprint object or dict
        if hasattr(blueprint, 'asset_plan'):
            blueprint.asset_plan = plan_dict
        elif isinstance(blueprint, dict):
            blueprint['asset_plan'] = plan_dict

        return {
            "status": "success",
            "enriched_blueprint": blueprint,
            "asset_plan": plan_dict,
            "is_asset_compliant": res.get("is_valid", True),
            "quality_score": res.get("quality_score", {}),
            "validation_metrics": res.get("validation_metrics", {}),
            "validation_errors": res.get("validation_errors", []),
            "validation_warnings": res.get("validation_warnings", [])
        }
