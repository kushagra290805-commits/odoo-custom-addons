# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
import uuid
from typing import Dict, Any, Optional
from .design_blueprint import (
    DesignBlueprint, PageBlueprint, SectionBlueprint, ComponentBlueprint,
    ColorPalette, ColorToken, TypographyScale, TypographyToken, DesignTokenSet,
    NavigationTree, NavigationNode, ResponsiveBreakpoint, AssetPlaceholder,
    AnimationRule, ExperienceBlueprint
)
from .blueprint_validator import BlueprintValidator, ValidationResult

_logger = logging.getLogger(__name__)

class DesignBlueprintEngine(models.AbstractModel):
    """
    AI Design Blueprint Engine Service.
    
    Acts as the transformation bridge between Builder Sessions and Design Orchestrators.
    Consumes high-level client requirements or AI session specifications and generates
    a fully structured, provider-neutral, and rendering-neutral DesignBlueprint.
    Performs comprehensive validation before outputting the blueprint.
    """
    _name = 'nexora.design_blueprint_engine'
    _description = 'AI Design Blueprint Engine Service'

    @api.model
    def generate_blueprint(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate and validate a DesignBlueprint from input requirement specifications.
        """
        req = requirements or {}
        project_name = req.get('project_name') or req.get('name') or 'Studio Generated Project'
        
        # 1. Generate Tokens & Palette
        palette_data = req.get('color_palette', {})
        tokens_list = [
            ColorToken(id='col_prim', name='primary', hex_value='#3b82f6', role='primary', contrast_ratio_on_background=5.2, wcag_grade='AA'),
            ColorToken(id='col_sec', name='secondary', hex_value='#64748b', role='secondary', contrast_ratio_on_background=4.8, wcag_grade='AA'),
            ColorToken(id='col_bg', name='background', hex_value='#0f172a', role='background', contrast_ratio_on_background=18.0, wcag_grade='AAA'),
            ColorToken(id='col_surf', name='surface', hex_value='#1e293b', role='surface', contrast_ratio_on_background=14.5, wcag_grade='AAA'),
            ColorToken(id='col_acc', name='accent', hex_value='#f59e0b', role='accent', contrast_ratio_on_background=3.5, wcag_grade='AA'),
            ColorToken(id='col_txt', name='text', hex_value='#f8fafc', role='text', contrast_ratio_on_background=14.5, wcag_grade='AAA')
        ]
        color_palette = ColorPalette(id='pal_main', name=palette_data.get('name', 'Core Brand Palette'), tokens=tokens_list, background_token_id='col_bg')
        
        typo_list = [
            TypographyToken(id='typo_h1', name='Heading 1', font_family='Inter', font_size_px=48, font_weight=700, line_height_ratio=1.2),
            TypographyToken(id='typo_body', name='Body Regular', font_family='Inter', font_size_px=16, font_weight=400, line_height_ratio=1.5)
        ]
        typo_scale = TypographyScale(id='scale_main', name='Standard Typography', tokens=typo_list)
        
        token_set = DesignTokenSet(id='tokens_root', name='Primary Token Set', color_palette=color_palette, typography_scale=typo_scale)
        
        # 2. Generate Placeholders & Animations
        placeholders = {
            'ph_hero_img': AssetPlaceholder(id='ph_hero_img', name='Hero Illustration', asset_type='illustration', width_px=1200, height_px=800, alt_text='Vibrant hero illustration depicting modern studio workflows.', aria_role='img')
        }
        
        animations = {
            'anim_fade': AnimationRule(id='anim_fade', name='Smooth Fade In', trigger='on-scroll', duration_ms=400, easing='ease-out', target_property='opacity', intensity='subtle')
        }
        
        # 3. Generate Navigation
        nav_tree = NavigationTree(id='nav_main', name='Header Navigation', root_nodes=[
            NavigationNode(id='nav_home', label='Home', target_slug_or_id='/'),
            NavigationNode(id='nav_features', label='Features', target_slug_or_id='#sec_features'),
            NavigationNode(id='nav_about', label='About', target_slug_or_id='/about')
        ])
        
        # 4. Generate Breakpoints
        breakpoints = [
            ResponsiveBreakpoint(id='bp_mobile', label='mobile', min_width_px=320, max_width_px=767, columns=4, margin_px=16),
            ResponsiveBreakpoint(id='bp_tablet', label='tablet', min_width_px=768, max_width_px=1023, columns=8, margin_px=24),
            ResponsiveBreakpoint(id='bp_desktop', label='desktop', min_width_px=1024, max_width_px=None, columns=12, margin_px=32)
        ]
        
        # 5. Generate Experience Blueprint (First-class domain object)
        exp_data = req.get('experience', {})
        experience = ExperienceBlueprint(
            visual_style=exp_data.get('visual_style', 'modern'),
            interaction_style=exp_data.get('interaction_style', 'dynamic'),
            animation_intensity=exp_data.get('animation_intensity', 'subtle'),
            scrolling_behavior=exp_data.get('scrolling_behavior', 'smooth'),
            section_transitions=exp_data.get('section_transitions', 'fade'),
            parallax_level=exp_data.get('parallax_level', 'none'),
            cursor_behavior=exp_data.get('cursor_behavior', 'default'),
            rendering_preference=exp_data.get('rendering_preference', '2D'),
            performance_budget=exp_data.get('performance_budget', {'max_asset_payload_kb': 2048, 'target_fps': 60, 'max_animation_simultaneous': 5}),
            accessibility_preferences=exp_data.get('accessibility_preferences', {'prefers_reduced_motion': False, 'wcag_target': 'AA', 'screen_reader_optimized': True})
        )
        
        # 6. Generate Components, Sections, and Pages
        hero_comp = ComponentBlueprint(
            id='comp_hero_card', name='Hero Card', category='card', layout_type='flex-column', alignment='center', width_mode='fill', height_mode='hug',
            token_references=['col_prim', 'typo_h1', 'typo_body'], asset_placeholders=['ph_hero_img'], animation_rule_ids=['anim_fade']
        )
        
        sec_hero = SectionBlueprint(id='sec_hero', name='Hero Section', section_type='hero', layout_container='grid-12', background_token_id='col_bg', components=[hero_comp])
        sec_features = SectionBlueprint(id='sec_features', name='Features Grid', section_type='features', layout_container='grid-12', background_token_id='col_bg', components=[])
        
        page_home = PageBlueprint(id='page_home', name='Home', slug='/', seo_title='Nexora Studio | Home', seo_description='Empowering AI agentic design workflows.', sections=[sec_hero, sec_features])
        page_about = PageBlueprint(id='page_about', name='About Us', slug='/about', seo_title='Nexora Studio | About', seo_description='Our mission and design intelligence framework.', sections=[])
        
        meta = dict(req.get('metadata', {}))
        if 'project_type' in req and 'project_type' not in meta:
            meta['project_type'] = req['project_type']
        if 'category' in req and 'category' not in meta:
            meta['category'] = req['category']

        # 7. Construct Root Aggregate
        blueprint = DesignBlueprint(
            blueprint_id=req.get('blueprint_id', str(uuid.uuid4())),
            project_name=project_name,
            version=req.get('version', '1.0.0'),
            pages=[page_home, page_about],
            token_set=token_set,
            navigation=nav_tree,
            breakpoints=breakpoints,
            experience=experience,
            placeholders=placeholders,
            animations=animations,
            metadata=meta
        )
        
        # 8. Validate Blueprint
        val_result = BlueprintValidator.validate(blueprint)
        if not val_result.is_valid:
            _logger.warning("Generated DesignBlueprint '%s' failed validation: %s", project_name, val_result.errors)
            
        return {
            "status": "success",
            "is_valid": val_result.is_valid,
            "blueprint": blueprint.to_dict(),
            "validation": val_result.to_dict()
        }
