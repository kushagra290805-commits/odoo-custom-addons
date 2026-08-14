# -*- coding: utf-8 -*-
"""
Content Intelligence Engine Service — Phase 11F: AI Asset Planning & Content Intelligence Engine.

Odoo AbstractModel ('nexora.content_intelligence_engine') responsible for generating
structured, provider-neutral content bundles (headlines, body content, CTAs, SEO metadata,
and localization) guided by ContentStrategy, BrandVoice, and ReadingLevel without invoking
AI models or referencing rendering technologies.
"""
from odoo import models, api, _
import logging
from typing import Dict, Any, Optional, List
from .content_domain import (
    ContentPlan, ContentStrategy, BrandVoice, ReadingLevel, LocalizationMetadata,
    SEOMetadata, PageContentBundle, SectionContentBundle, HeadlineContent,
    SubHeadlineContent, BodyContent, CTAContent
)
from .asset_content_validator import AssetContentValidator

_logger = logging.getLogger(__name__)


class ContentIntelligenceEngine(models.AbstractModel):
    """
    Content Intelligence Engine Service.
    
    Transforms client requirements and blueprint layout structures into structured,
    provider-neutral ContentPlans governed by brand voice archetypes and reading level targets.
    """
    _name = 'nexora.content_intelligence_engine'
    _description = 'AI Content Intelligence Engine Service'

    @api.model
    def generate_content_plan(self, requirements: Optional[Dict[str, Any]] = None, blueprint: Any = None) -> Dict[str, Any]:
        """
        Generate a comprehensive ContentPlan guided by ContentStrategy.
        """
        req = requirements or {}
        project_name = req.get('project_name', 'Unnamed Project')
        project_type = req.get('project_type', 'standard').lower()
        target_audience = req.get('target_audience', "Modern digital professionals and enterprise leaders")
        value_prop = req.get('value_proposition', f"Next-generation {project_type} platform engineered for seamless scalability and AI-driven performance.")

        # 1. Initialize ContentStrategy, BrandVoice, and ReadingLevel
        strategy = ContentStrategy(
            primary_goal=req.get('primary_goal', 'conversion'),
            target_audience=target_audience,
            value_proposition=value_prop,
            conversion_strategy=req.get('conversion_strategy', 'schedule_demo'),
            storytelling_style=req.get('storytelling_style', 'problem_solution')
        )
        voice = BrandVoice(
            archetype=req.get('brand_archetype', 'innovator' if project_type in ('saas', 'tech', 'ai') else 'expert'),
            tone=req.get('brand_tone', 'authoritative' if project_type == 'enterprise' else 'conversational')
        )
        reading_level = ReadingLevel(
            target_grade_level=int(req.get('target_grade_level', 8)),
            flesch_kincaid_target=float(req.get('flesch_kincaid_target', 65.0))
        )

        # 2. Setup Localization Metadata
        supported_locales = req.get('supported_locales', ['en_US'])
        localization = LocalizationMetadata(
            primary_locale="en_US",
            supported_locales=supported_locales,
            translation_status="complete" if len(supported_locales) == 1 else "in_progress",
            localized_strings={}
        )

        plan = ContentPlan(
            project_name=project_name,
            strategy=strategy,
            brand_voice=voice,
            reading_level=reading_level,
            global_localization=localization
        )

        # 3. Populate Page and Section Content Bundles from Blueprint
        bp_dict = blueprint.to_dict() if hasattr(blueprint, 'to_dict') else (blueprint if isinstance(blueprint, dict) else {})
        pages = bp_dict.get('pages', [])
        
        if not pages:
            # Create a default Home Page bundle if blueprint has no explicit pages yet
            pages = [{"name": "Home Page", "page_type": "landing", "sections": [
                {"name": "Hero Section", "section_type": "hero"},
                {"name": "Features Section", "section_type": "features"},
                {"name": "CTA Section", "section_type": "contact"}
            ]}]

        for p_idx, page in enumerate(pages):
            p_name = page.get('name', f"Page {p_idx+1}") if isinstance(page, dict) else getattr(page, 'name', f"Page {p_idx+1}")
            p_type = page.get('page_type', 'landing') if isinstance(page, dict) else getattr(page, 'page_type', 'landing')
            
            seo = SEOMetadata(
                title=f"{p_name} | {project_name}",
                description=f"{value_prop[:150]}...",
                keywords=[project_name.lower(), p_type, project_type, "digital transformation", "ai design"]
            )
            
            page_bundle = PageContentBundle(page_name=p_name, seo_metadata=seo)
            
            sections = page.get('sections', []) if isinstance(page, dict) else getattr(page, 'sections', [])
            for s_idx, sec in enumerate(sections):
                s_name = sec.get('name', f"Section {s_idx+1}") if isinstance(sec, dict) else getattr(sec, 'name', f"Section {s_idx+1}")
                s_type = sec.get('section_type', 'content').lower() if isinstance(sec, dict) else getattr(sec, 'section_type', 'content').lower()
                
                sec_bundle = SectionContentBundle(section_title=s_name)
                
                # Construct tailored content elements based on section archetype
                if s_type == "hero":
                    sec_bundle.headlines.append(HeadlineContent(text=f"Transform Your Workflow with {project_name}", semantic_role="h1", tone_tag=voice.tone))
                    sec_bundle.sub_headlines.append(SubHeadlineContent(text=value_prop))
                    sec_bundle.ctas.append(CTAContent(primary_label="Start Free Trial", secondary_label="Schedule Demo", action_intent=strategy.conversion_strategy, urgency_level="high"))
                elif s_type in ("features", "services"):
                    sec_bundle.headlines.append(HeadlineContent(text="Engineered for Scalability and Precision", semantic_role="h2", tone_tag=voice.tone))
                    sec_bundle.body_content.append(BodyContent(paragraphs=[
                        f"Our state-of-the-art architecture adapts to your business needs.",
                        f"Experience seamless integration with {project_name}'s intelligent automation tools."
                    ], summary="Core capabilities overview", reading_time_sec=45))
                elif s_type in ("pricing", "ecommerce"):
                    sec_bundle.headlines.append(HeadlineContent(text="Transparent, Predictable Pricing", semantic_role="h2", tone_tag=voice.tone))
                    sec_bundle.ctas.append(CTAContent(primary_label="Choose Plan", action_intent="purchase", urgency_level="medium"))
                elif s_type in ("contact", "footer", "cta"):
                    sec_bundle.headlines.append(HeadlineContent(text="Ready to Get Started?", semantic_role="h2", tone_tag=voice.tone))
                    sec_bundle.sub_headlines.append(SubHeadlineContent(text=f"Join thousands of innovators using {project_name} today."))
                    sec_bundle.ctas.append(CTAContent(primary_label="Contact Sales", action_intent="contact", urgency_level="high"))
                else:
                    sec_bundle.headlines.append(HeadlineContent(text=s_name, semantic_role="h2", tone_tag=voice.tone))
                    sec_bundle.body_content.append(BodyContent(paragraphs=[f"Explore {s_name} and discover how {project_name} empowers your team."]))

                # Populate mock localization strings if multi-locale is supported
                if len(supported_locales) > 1:
                    for loc_code in supported_locales:
                        if loc_code != "en_US":
                            for h in sec_bundle.headlines:
                                localization.localized_strings[f"{h.id}_{loc_code}"] = f"[{loc_code}] {h.text}"
                            for c in sec_bundle.ctas:
                                localization.localized_strings[f"{c.id}_{loc_code}"] = f"[{loc_code}] {c.primary_label}"

                page_bundle.section_bundles.append(sec_bundle)
            plan.pages.append(page_bundle)

        # 4. Validate ContentPlan via AssetContentValidator
        val_res = AssetContentValidator.validate(blueprint=blueprint, asset_plan=None, content_plan=plan)

        return {
            "status": "success",
            "is_valid": val_res.is_valid,
            "content_plan": plan.to_dict(),
            "quality_score": val_res.quality_score.to_dict(),
            "validation_metrics": val_res.metrics,
            "validation_errors": val_res.errors,
            "validation_warnings": val_res.warnings
        }

    @api.model
    def process_blueprint(self, blueprint: Any, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Consume a candidate blueprint, generate its ContentPlan, attach it to the blueprint,
        and return validation compliance report.
        """
        res = self.generate_content_plan(requirements=requirements, blueprint=blueprint)
        plan_dict = res.get("content_plan", {})

        # Attach content plan to blueprint object or dict
        if hasattr(blueprint, 'content_plan'):
            blueprint.content_plan = plan_dict
        elif isinstance(blueprint, dict):
            blueprint['content_plan'] = plan_dict

        return {
            "status": "success",
            "enriched_blueprint": blueprint,
            "content_plan": plan_dict,
            "is_content_compliant": res.get("is_valid", True),
            "quality_score": res.get("quality_score", {}),
            "validation_metrics": res.get("validation_metrics", {}),
            "validation_errors": res.get("validation_errors", []),
            "validation_warnings": res.get("validation_warnings", [])
        }
