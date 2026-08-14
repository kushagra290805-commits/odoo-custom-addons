# -*- coding: utf-8 -*-
"""
Asset & Content Validator — Phase 11F: AI Asset Planning & Content Intelligence Engine.

Performs static analysis, completeness checking, accessibility validation, licensing
compliance verification, localization auditing, and quantitative quality scoring
for AssetPlans and ContentPlans without referencing rendering technologies or AI models.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

_logger = logging.getLogger(__name__)


@dataclass
class AssetContentQualityScore:
    """
    Quantitative quality metric for asset planning and content intelligence.
    Computed via deduction heuristics starting from a baseline of 100.0 across 6 criteria.
    """
    asset_completeness_score: float = 100.0     # Weight 20%
    licensing_compliance_score: float = 100.0   # Weight 15%
    accessibility_score: float = 100.0          # Weight 20%
    localization_score: float = 100.0           # Weight 15%
    content_consistency_score: float = 100.0    # Weight 15%
    prompt_quality_score: float = 100.0         # Weight 15%
    overall_score: float = 100.0                # Weighted average

    def calculate_overall(self) -> float:
        self.asset_completeness_score = max(0.0, min(100.0, self.asset_completeness_score))
        self.licensing_compliance_score = max(0.0, min(100.0, self.licensing_compliance_score))
        self.accessibility_score = max(0.0, min(100.0, self.accessibility_score))
        self.localization_score = max(0.0, min(100.0, self.localization_score))
        self.content_consistency_score = max(0.0, min(100.0, self.content_consistency_score))
        self.prompt_quality_score = max(0.0, min(100.0, self.prompt_quality_score))

        weights = {
            'completeness': 0.20,
            'licensing': 0.15,
            'accessibility': 0.20,
            'localization': 0.15,
            'consistency': 0.15,
            'prompt_quality': 0.15
        }
        overall = (
            self.asset_completeness_score * weights['completeness'] +
            self.licensing_compliance_score * weights['licensing'] +
            self.accessibility_score * weights['accessibility'] +
            self.localization_score * weights['localization'] +
            self.content_consistency_score * weights['consistency'] +
            self.prompt_quality_score * weights['prompt_quality']
        )
        self.overall_score = round(overall, 2)
        return self.overall_score

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetContentQualityScore':
        if not data:
            return cls()
        score = cls(
            asset_completeness_score=float(data.get('asset_completeness_score', 100.0)),
            licensing_compliance_score=float(data.get('licensing_compliance_score', 100.0)),
            accessibility_score=float(data.get('accessibility_score', 100.0)),
            localization_score=float(data.get('localization_score', 100.0)),
            content_consistency_score=float(data.get('content_consistency_score', 100.0)),
            prompt_quality_score=float(data.get('prompt_quality_score', 100.0)),
            overall_score=float(data.get('overall_score', 100.0))
        )
        score.calculate_overall()
        return score

    def to_dict(self) -> Dict[str, Any]:
        self.calculate_overall()
        return {
            'asset_completeness_score': round(self.asset_completeness_score, 2),
            'licensing_compliance_score': round(self.licensing_compliance_score, 2),
            'accessibility_score': round(self.accessibility_score, 2),
            'localization_score': round(self.localization_score, 2),
            'content_consistency_score': round(self.content_consistency_score, 2),
            'prompt_quality_score': round(self.prompt_quality_score, 2),
            'overall_score': round(self.overall_score, 2)
        }


@dataclass
class AssetContentValidationResult:
    """
    Result of executing AssetContentValidator against a design blueprint, asset plan, and content plan.
    """
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    quality_score: AssetContentQualityScore = field(default_factory=AssetContentQualityScore)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'metrics': self.metrics,
            'quality_score': self.quality_score.to_dict() if hasattr(self.quality_score, 'to_dict') else self.quality_score
        }


class AssetContentValidator:
    """
    Automated verification engine for asset plans and content intelligence bundles.
    Enforces completeness, licensing, WCAG accessibility, localization, consistency, and prompt quality.
    """

    @classmethod
    def validate(cls, blueprint: Any = None, asset_plan: Any = None, content_plan: Any = None) -> AssetContentValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        metrics: Dict[str, Any] = {
            'total_assets_inspected': 0,
            'missing_assets_count': 0,
            'prompt_specifications_count': 0,
            'content_sections_inspected': 0,
            'accessibility_violations': 0,
            'licensing_violations': 0
        }
        score = AssetContentQualityScore()

        # Convert to dictionary representations if objects passed
        bp_dict = blueprint.to_dict() if hasattr(blueprint, 'to_dict') else (blueprint or {})
        ap_dict = asset_plan.to_dict() if hasattr(asset_plan, 'to_dict') else (asset_plan or {})
        cp_dict = content_plan.to_dict() if hasattr(content_plan, 'to_dict') else (content_plan or {})

        # ---------------------------------------------------------
        # Ruleset 1: Asset Completeness
        # ---------------------------------------------------------
        req_assets = ap_dict.get('required_assets', [])
        missing_assets = ap_dict.get('missing_assets', [])
        prompt_specs = ap_dict.get('prompt_specifications', [])

        metrics['total_assets_inspected'] = len(req_assets) + len(ap_dict.get('optional_assets', [])) + len(ap_dict.get('reusable_assets', []))
        metrics['missing_assets_count'] = len(missing_assets)
        metrics['prompt_specifications_count'] = len(prompt_specs)

        for missing in missing_assets:
            m_id = missing.get('asset_id', 'unknown') if isinstance(missing, dict) else getattr(missing, 'asset_id', 'unknown')
            m_name = missing.get('name', 'Unnamed') if isinstance(missing, dict) else getattr(missing, 'name', 'Unnamed')
            # Check if there is a corresponding prompt spec
            has_prompt = any(
                (p.get('prompt_id') == m_id or p.get('metadata', {}).get('target_asset_id') == m_id) if isinstance(p, dict)
                else (getattr(p, 'prompt_id', None) == m_id or getattr(p, 'metadata', {}).get('target_asset_id') == m_id)
                for p in prompt_specs
            )
            if not has_prompt:
                errors.append(f"Completeness Error: Required asset '{m_name}' ({m_id}) is marked missing and has no generated prompt specification.")
                score.asset_completeness_score -= 20.0
            else:
                warnings.append(f"Completeness Warning: Asset '{m_name}' ({m_id}) is currently missing; relying on AI prompt specification for future generation.")
                score.asset_completeness_score -= 5.0

        # ---------------------------------------------------------
        # Ruleset 2: Duplicate Assets
        # ---------------------------------------------------------
        seen_asset_ids = set()
        all_assets = req_assets + ap_dict.get('optional_assets', []) + ap_dict.get('reusable_assets', []) + ap_dict.get('generated_assets', [])
        for asset in all_assets:
            a_id = asset.get('asset_id') if isinstance(asset, dict) else getattr(asset, 'asset_id', None)
            if a_id:
                if a_id in seen_asset_ids:
                    warnings.append(f"Duplicate Asset Warning: Asset ID '{a_id}' is defined multiple times across collection buckets.")
                    score.asset_completeness_score -= 10.0
                seen_asset_ids.add(a_id)

        seen_prompt_ids = set()
        for p in prompt_specs:
            p_id = p.get('prompt_id') if isinstance(p, dict) else getattr(p, 'prompt_id', None)
            if p_id:
                if p_id in seen_prompt_ids:
                    warnings.append(f"Duplicate Prompt Warning: Prompt specification ID '{p_id}' is duplicated.")
                    score.prompt_quality_score -= 10.0
                seen_prompt_ids.add(p_id)

        # ---------------------------------------------------------
        # Ruleset 3: Licensing Compliance
        # ---------------------------------------------------------
        for asset in all_assets:
            lic = asset.get('license', {}) if isinstance(asset, dict) else getattr(asset, 'license', {})
            lic_dict = lic.to_dict() if hasattr(lic, 'to_dict') else (lic if isinstance(lic, dict) else {})
            a_name = asset.get('name', 'Unnamed') if isinstance(asset, dict) else getattr(asset, 'name', 'Unnamed')
            
            l_type = lic_dict.get('license_type', 'proprietary').lower()
            attr_req = lic_dict.get('attribution_required', False)
            source = lic_dict.get('source_url')

            if attr_req and not source and l_type not in ('generated', 'reusable', 'proprietary'):
                warnings.append(f"Licensing Violation: Asset '{a_name}' requires attribution but declares no source_url or attribution text.")
                score.licensing_compliance_score -= 15.0
                metrics['licensing_violations'] += 1
            if not lic_dict.get('commercial_use', True):
                errors.append(f"Licensing Error: Asset '{a_name}' explicitly disallows commercial use in a commercial project.")
                score.licensing_compliance_score -= 25.0
                metrics['licensing_violations'] += 1

        # ---------------------------------------------------------
        # Ruleset 4: Accessibility Metadata (WCAG A11y)
        # ---------------------------------------------------------
        for asset in all_assets:
            meta = asset.get('metadata', {}) if isinstance(asset, dict) else getattr(asset, 'metadata', {})
            meta_dict = meta.to_dict() if hasattr(meta, 'to_dict') else (meta if isinstance(meta, dict) else {})
            a_name = asset.get('name', 'Unnamed') if isinstance(asset, dict) else getattr(asset, 'name', 'Unnamed')
            a_type = asset.get('asset_type', 'image') if isinstance(asset, dict) else getattr(asset, 'asset_type', 'image')

            if a_type in ('image', 'illustration', '3d_asset', 'icon'):
                alt = meta_dict.get('alt_text', '').strip()
                role = meta_dict.get('aria_role', 'img').lower()
                if not alt and role not in ('decorative', 'presentation'):
                    warnings.append(f"Accessibility Warning: Media asset '{a_name}' has empty alt_text and aria_role is not decorative.")
                    score.accessibility_score -= 15.0
                    metrics['accessibility_violations'] += 1

        # ---------------------------------------------------------
        # Ruleset 5: Localization Completeness
        # ---------------------------------------------------------
        loc = cp_dict.get('global_localization', {})
        loc_dict = loc.to_dict() if hasattr(loc, 'to_dict') else (loc if isinstance(loc, dict) else {})
        supported = loc_dict.get('supported_locales', ['en_US'])
        strings = loc_dict.get('localized_strings', {})
        status = loc_dict.get('translation_status', 'complete').lower()

        if len(supported) > 1 and status == 'pending':
            warnings.append(f"Localization Warning: Project supports multiple locales ({supported}) but translation_status is marked 'pending'.")
            score.localization_score -= 15.0
        elif len(supported) > 1 and not strings and status == 'complete':
            warnings.append("Localization Warning: translation_status is 'complete' for multiple locales, but localized_strings dictionary is empty.")
            score.localization_score -= 20.0

        # ---------------------------------------------------------
        # Ruleset 6: Content Consistency & Prompt Quality
        # ---------------------------------------------------------
        pages = cp_dict.get('pages', [])
        for page in pages:
            bundles = page.get('section_bundles', []) if isinstance(page, dict) else getattr(page, 'section_bundles', [])
            metrics['content_sections_inspected'] += len(bundles)
            for bundle in bundles:
                sec_title = bundle.get('section_title', 'Unnamed Section') if isinstance(bundle, dict) else getattr(bundle, 'section_title', 'Unnamed Section')
                headlines = bundle.get('headlines', []) if isinstance(bundle, dict) else getattr(bundle, 'headlines', [])
                ctas = bundle.get('ctas', []) if isinstance(bundle, dict) else getattr(bundle, 'ctas', [])
                
                for h in headlines:
                    h_text = h.get('text', '').strip() if isinstance(h, dict) else getattr(h, 'text', '').strip()
                    if not h_text:
                        errors.append(f"Content Consistency Error: Section '{sec_title}' contains a headline with empty text.")
                        score.content_consistency_score -= 20.0
                        
                for c in ctas:
                    c_label = c.get('primary_label', '').strip() if isinstance(c, dict) else getattr(c, 'primary_label', '').strip()
                    if not c_label:
                        errors.append(f"Content Consistency Error: Section '{sec_title}' contains a CTA with empty primary_label.")
                        score.content_consistency_score -= 20.0

        for p in prompt_specs:
            subj = p.get('subject_description', '').strip() if isinstance(p, dict) else getattr(p, 'subject_description', '').strip()
            styles = p.get('style_keywords', []) if isinstance(p, dict) else getattr(p, 'style_keywords', [])
            p_id = p.get('prompt_id', 'unknown') if isinstance(p, dict) else getattr(p, 'prompt_id', 'unknown')
            
            if not subj:
                errors.append(f"Prompt Quality Error: PromptSpecification '{p_id}' has empty subject_description.")
                score.prompt_quality_score -= 25.0
            if not styles:
                warnings.append(f"Prompt Quality Warning: PromptSpecification '{p_id}' has no style_keywords defined.")
                score.prompt_quality_score -= 10.0

        # Calculate final overall score
        score.calculate_overall()
        is_valid = len(errors) == 0

        return AssetContentValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            quality_score=score
        )
