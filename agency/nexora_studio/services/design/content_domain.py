# -*- coding: utf-8 -*-
"""
Content Domain Models — Phase 11F: AI Asset Planning & Content Intelligence Engine.

Defines provider-neutral, rendering-neutral domain classes for representing content strategy,
brand voice, reading level, SEO metadata, localization, headlines, body content, CTAs,
and structured page/section bundles without referencing React, HTML, CSS, Three.js, or Penpot schemas.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid


@dataclass
class ContentStrategy:
    """
    Provider-neutral content strategy model guiding AI content planning and structure.
    Does not invoke or reference any AI models or rendering technologies.
    """
    primary_goal: str = "conversion"            # 'conversion', 'brand_awareness', 'engagement', 'lead_generation', 'education'
    secondary_goals: List[str] = field(default_factory=lambda: ["trust_building", "seo_visibility"])
    target_audience: str = "General business professionals and digital agency clients"
    value_proposition: str = "State-of-the-art AI design and digital transformation agency solutions"
    trust_building_elements: List[str] = field(default_factory=lambda: ["testimonials", "security_badges", "client_logos", "metrics"])
    conversion_strategy: str = "schedule_demo"    # 'direct_signup', 'schedule_demo', 'free_trial', 'consultation', 'purchase'
    engagement_strategy: str = "interactive_walkthrough" # 'interactive_calculator', 'video_walkthrough', 'case_studies'
    seo_priority: str = "high"                  # 'high', 'medium', 'low'
    storytelling_style: str = "problem_solution"# 'problem_solution', 'hero_journey', 'data_driven', 'visionary', 'customer_centric'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentStrategy':
        if not data:
            return cls()
        return cls(
            primary_goal=data.get('primary_goal', 'conversion').lower(),
            secondary_goals=data.get('secondary_goals', ["trust_building", "seo_visibility"]),
            target_audience=data.get('target_audience', "General business professionals and digital agency clients"),
            value_proposition=data.get('value_proposition', "State-of-the-art AI design and digital transformation agency solutions"),
            trust_building_elements=data.get('trust_building_elements', ["testimonials", "security_badges", "client_logos", "metrics"]),
            conversion_strategy=data.get('conversion_strategy', 'schedule_demo').lower(),
            engagement_strategy=data.get('engagement_strategy', 'interactive_walkthrough').lower(),
            seo_priority=data.get('seo_priority', 'high').lower(),
            storytelling_style=data.get('storytelling_style', 'problem_solution').lower()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'primary_goal': self.primary_goal,
            'secondary_goals': self.secondary_goals,
            'target_audience': self.target_audience,
            'value_proposition': self.value_proposition,
            'trust_building_elements': self.trust_building_elements,
            'conversion_strategy': self.conversion_strategy,
            'engagement_strategy': self.engagement_strategy,
            'seo_priority': self.seo_priority,
            'storytelling_style': self.storytelling_style
        }


@dataclass
class BrandVoice:
    """
    Brand voice and tone guidelines governing content intelligence generation.
    """
    archetype: str = "expert"                   # 'expert', 'innovator', 'trusted', 'playful', 'authoritative', 'editorial'
    tone: str = "professional"                  # 'professional', 'conversational', 'authoritative', 'inspiring', 'friendly'
    formality_level: int = 4                    # 1 (very informal) to 5 (highly formal)
    enthusiasm_level: int = 3                   # 1 (reserved/objective) to 5 (highly enthusiastic)
    vocabulary_rules: Dict[str, List[str]] = field(default_factory=lambda: {
        "preferred": ["innovative", "state-of-the-art", "seamless", "intelligent", "adaptive"],
        "avoid": ["cheap", "hack", "basic", "quick fix", "amateur"]
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrandVoice':
        if not data:
            return cls()
        return cls(
            archetype=data.get('archetype', 'expert').lower(),
            tone=data.get('tone', 'professional').lower(),
            formality_level=int(data.get('formality_level', 4)),
            enthusiasm_level=int(data.get('enthusiasm_level', 3)),
            vocabulary_rules=data.get('vocabulary_rules', {
                "preferred": ["innovative", "state-of-the-art", "seamless", "intelligent", "adaptive"],
                "avoid": ["cheap", "hack", "basic", "quick fix", "amateur"]
            })
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'archetype': self.archetype,
            'tone': self.tone,
            'formality_level': self.formality_level,
            'enthusiasm_level': self.enthusiasm_level,
            'vocabulary_rules': self.vocabulary_rules
        }


@dataclass
class ReadingLevel:
    """
    Readability and sentence complexity guidelines.
    """
    target_grade_level: int = 8                 # US grade level (e.g. 8th grade readability)
    flesch_kincaid_target: float = 65.0         # Flesch reading ease score target (0-100)
    max_sentence_length: int = 20               # Maximum average words per sentence

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReadingLevel':
        if not data:
            return cls()
        return cls(
            target_grade_level=int(data.get('target_grade_level', 8)),
            flesch_kincaid_target=float(data.get('flesch_kincaid_target', 65.0)),
            max_sentence_length=int(data.get('max_sentence_length', 20))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'target_grade_level': self.target_grade_level,
            'flesch_kincaid_target': self.flesch_kincaid_target,
            'max_sentence_length': self.max_sentence_length
        }


@dataclass
class LocalizationMetadata:
    """
    Localization and multi-locale string management metadata.
    """
    primary_locale: str = "en_US"
    supported_locales: List[str] = field(default_factory=lambda: ["en_US"])
    rtl_enabled: bool = False
    translation_status: str = "complete"        # 'complete', 'pending', 'in_progress'
    localized_strings: Dict[str, Dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LocalizationMetadata':
        if not data:
            return cls()
        return cls(
            primary_locale=data.get('primary_locale', 'en_US'),
            supported_locales=data.get('supported_locales', ['en_US']),
            rtl_enabled=bool(data.get('rtl_enabled', False)),
            translation_status=data.get('translation_status', 'complete').lower(),
            localized_strings=data.get('localized_strings', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'primary_locale': self.primary_locale,
            'supported_locales': self.supported_locales,
            'rtl_enabled': self.rtl_enabled,
            'translation_status': self.translation_status,
            'localized_strings': self.localized_strings
        }


@dataclass
class SEOMetadata:
    """
    Search engine optimization metadata for pages and content bundles.
    """
    title: str = "Nexora Studio — AI Design Agency"
    description: str = "Experience state-of-the-art AI design and digital transformation solutions."
    keywords: List[str] = field(default_factory=lambda: ["ai design", "digital agency", "web application", "ux design", "enterprise solutions"])
    og_image_ref: Optional[str] = None
    canonical_url_pattern: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SEOMetadata':
        if not data:
            return cls()
        return cls(
            title=data.get('title', "Nexora Studio — AI Design Agency"),
            description=data.get('description', "Experience state-of-the-art AI design and digital transformation solutions."),
            keywords=data.get('keywords', ["ai design", "digital agency", "web application", "ux design", "enterprise solutions"]),
            og_image_ref=data.get('og_image_ref'),
            canonical_url_pattern=data.get('canonical_url_pattern')
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'description': self.description,
            'keywords': self.keywords,
            'og_image_ref': self.og_image_ref,
            'canonical_url_pattern': self.canonical_url_pattern
        }


@dataclass
class HeadlineContent:
    """
    Headline and title content element.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    subtext: Optional[str] = None
    semantic_role: str = "h1"                   # 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hero', 'section_title'
    locale: str = "en_US"
    tone_tag: str = "authoritative"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HeadlineContent':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            text=data.get('text', ''),
            subtext=data.get('subtext'),
            semantic_role=data.get('semantic_role', 'h1').lower(),
            locale=data.get('locale', 'en_US'),
            tone_tag=data.get('tone_tag', 'authoritative').lower()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'text': self.text,
            'subtext': self.subtext,
            'semantic_role': self.semantic_role,
            'locale': self.locale,
            'tone_tag': self.tone_tag
        }


@dataclass
class SubHeadlineContent:
    """
    Sub-headline supporting a primary headline.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    parent_headline_id: Optional[str] = None
    locale: str = "en_US"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubHeadlineContent':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            text=data.get('text', ''),
            parent_headline_id=data.get('parent_headline_id'),
            locale=data.get('locale', 'en_US')
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'text': self.text,
            'parent_headline_id': self.parent_headline_id,
            'locale': self.locale
        }


@dataclass
class BodyContent:
    """
    Structured body content and paragraph text.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    paragraphs: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    reading_time_sec: int = 30
    locale: str = "en_US"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BodyContent':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            paragraphs=data.get('paragraphs', []),
            summary=data.get('summary'),
            reading_time_sec=int(data.get('reading_time_sec', 30)),
            locale=data.get('locale', 'en_US')
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'paragraphs': self.paragraphs,
            'summary': self.summary,
            'reading_time_sec': self.reading_time_sec,
            'locale': self.locale
        }


@dataclass
class CTAContent:
    """
    Call to action text and behavioral intent.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    primary_label: str = "Get Started"
    secondary_label: Optional[str] = None
    action_intent: str = "signup"               # 'signup', 'contact', 'demo', 'purchase', 'learn_more'
    urgency_level: str = "high"                 # 'high', 'medium', 'low'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CTAContent':
        if not data:
            return cls()
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            primary_label=data.get('primary_label', 'Get Started'),
            secondary_label=data.get('secondary_label'),
            action_intent=data.get('action_intent', 'signup').lower(),
            urgency_level=data.get('urgency_level', 'high').lower()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'primary_label': self.primary_label,
            'secondary_label': self.secondary_label,
            'action_intent': self.action_intent,
            'urgency_level': self.urgency_level
        }


@dataclass
class SectionContentBundle:
    """
    Aggregates all content intelligence elements for a specific section.
    """
    section_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    section_title: str = "Section Title"
    headlines: List[HeadlineContent] = field(default_factory=list)
    sub_headlines: List[SubHeadlineContent] = field(default_factory=list)
    body_content: List[BodyContent] = field(default_factory=list)
    ctas: List[CTAContent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SectionContentBundle':
        if not data:
            return cls()
        return cls(
            section_id=data.get('section_id', str(uuid.uuid4())),
            section_title=data.get('section_title', 'Section Title'),
            headlines=[HeadlineContent.from_dict(h) if isinstance(h, dict) else h for h in data.get('headlines', [])],
            sub_headlines=[SubHeadlineContent.from_dict(sh) if isinstance(sh, dict) else sh for sh in data.get('sub_headlines', [])],
            body_content=[BodyContent.from_dict(b) if isinstance(b, dict) else b for b in data.get('body_content', [])],
            ctas=[CTAContent.from_dict(c) if isinstance(c, dict) else c for c in data.get('ctas', [])],
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'section_id': self.section_id,
            'section_title': self.section_title,
            'headlines': [h.to_dict() if hasattr(h, 'to_dict') else h for h in self.headlines],
            'sub_headlines': [sh.to_dict() if hasattr(sh, 'to_dict') else sh for sh in self.sub_headlines],
            'body_content': [b.to_dict() if hasattr(b, 'to_dict') else b for b in self.body_content],
            'ctas': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.ctas],
            'metadata': self.metadata
        }


@dataclass
class PageContentBundle:
    """
    Aggregates all section bundles, SEO metadata, and localization for a page.
    """
    page_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    page_name: str = "Home Page"
    seo_metadata: SEOMetadata = field(default_factory=SEOMetadata)
    section_bundles: List[SectionContentBundle] = field(default_factory=list)
    localization: LocalizationMetadata = field(default_factory=LocalizationMetadata)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PageContentBundle':
        if not data:
            return cls()
        seo_data = data.get('seo_metadata')
        loc_data = data.get('localization')
        return cls(
            page_id=data.get('page_id', str(uuid.uuid4())),
            page_name=data.get('page_name', 'Home Page'),
            seo_metadata=SEOMetadata.from_dict(seo_data) if isinstance(seo_data, dict) else (seo_data or SEOMetadata()),
            section_bundles=[SectionContentBundle.from_dict(sb) if isinstance(sb, dict) else sb for sb in data.get('section_bundles', [])],
            localization=LocalizationMetadata.from_dict(loc_data) if isinstance(loc_data, dict) else (loc_data or LocalizationMetadata())
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'page_id': self.page_id,
            'page_name': self.page_name,
            'seo_metadata': self.seo_metadata.to_dict() if hasattr(self.seo_metadata, 'to_dict') else self.seo_metadata,
            'section_bundles': [sb.to_dict() if hasattr(sb, 'to_dict') else sb for sb in self.section_bundles],
            'localization': self.localization.to_dict() if hasattr(self.localization, 'to_dict') else self.localization
        }


@dataclass
class ContentPlan:
    """
    Root aggregate representing the complete content intelligence plan for a project.
    Guided by ContentStrategy, BrandVoice, and ReadingLevel without referencing rendering or AI models.
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_name: str = "Unnamed Project"
    strategy: ContentStrategy = field(default_factory=ContentStrategy)
    brand_voice: BrandVoice = field(default_factory=BrandVoice)
    reading_level: ReadingLevel = field(default_factory=ReadingLevel)
    pages: List[PageContentBundle] = field(default_factory=list)
    global_localization: LocalizationMetadata = field(default_factory=LocalizationMetadata)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentPlan':
        if not data:
            return cls()
        strat_data = data.get('strategy')
        voice_data = data.get('brand_voice')
        read_data = data.get('reading_level')
        loc_data = data.get('global_localization')
        
        return cls(
            plan_id=data.get('plan_id', str(uuid.uuid4())),
            project_name=data.get('project_name', 'Unnamed Project'),
            strategy=ContentStrategy.from_dict(strat_data) if isinstance(strat_data, dict) else (strat_data or ContentStrategy()),
            brand_voice=BrandVoice.from_dict(voice_data) if isinstance(voice_data, dict) else (voice_data or BrandVoice()),
            reading_level=ReadingLevel.from_dict(read_data) if isinstance(read_data, dict) else (read_data or ReadingLevel()),
            pages=[PageContentBundle.from_dict(p) if isinstance(p, dict) else p for p in data.get('pages', [])],
            global_localization=LocalizationMetadata.from_dict(loc_data) if isinstance(loc_data, dict) else (loc_data or LocalizationMetadata()),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'project_name': self.project_name,
            'strategy': self.strategy.to_dict() if hasattr(self.strategy, 'to_dict') else self.strategy,
            'brand_voice': self.brand_voice.to_dict() if hasattr(self.brand_voice, 'to_dict') else self.brand_voice,
            'reading_level': self.reading_level.to_dict() if hasattr(self.reading_level, 'to_dict') else self.reading_level,
            'pages': [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.pages],
            'global_localization': self.global_localization.to_dict() if hasattr(self.global_localization, 'to_dict') else self.global_localization,
            'metadata': self.metadata
        }
