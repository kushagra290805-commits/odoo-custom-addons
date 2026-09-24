import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Phase 47.23 (ADR-0075): deterministic section-code contract.
#
# _KNOWN_SECTION_IMPORTS is the FIXED import table owned by the assembler.
# The model never controls import paths: when a generated section uses a
# known construct (e.g. <Link>), the page assembler injects the matching
# whitelisted import â€” only when the construct actually appears and the
# module does not already carry a whitelisted import for it.
# ------------------------------------------------------------------
_KNOWN_SECTION_IMPORTS = {
    'Link': "import { Link } from 'react-router-dom'",
}
_ALLOWED_IMPORT_SPECIFIERS = {'react', 'react-router-dom', 'lucide-react'}

# Safe identifier universe for static section validation: JS/browser
# globals plus the assembler-provided known constructs.
_SAFE_GLOBAL_IDENTIFIERS = {
    'React', 'Link', 'JSON', 'Math', 'Date', 'window', 'document',
    'console', 'navigator', 'Array', 'Object', 'String', 'Number',
    'Boolean', 'Promise', 'Map', 'Set', 'Symbol', 'Intl', 'URL',
    'URLSearchParams', 'Error', 'TypeError', 'fetch', 'setTimeout',
    'setInterval', 'clearTimeout', 'clearInterval', 'require',
    'undefined', 'arguments', 'this', 'Infinity', 'NaN', 'globalThis',
}

# ------------------------------------------------------------------
# Phase 47.24 (ADR-0076): lucide activation. Curated icon whitelist â€”
# identifiers the assembler can bind to the FIXED lucide-react import
# (the model never controls import paths; it may only use whitelisted
# icon tags, and the assembler injects the single import line).
# ------------------------------------------------------------------
# Phase 47.26 (ADR-0078): scaffold-composed native organisms — identifiers
# the deterministic builders reference through assembler-owned fixed import
# lines against guaranteed provider-scaffold files (SiteLayout precedent).
_SCAFFOLD_COMPONENT_IDENTIFIERS = {
    'Hero', 'PricingCard', 'FAQ', 'ProductGrid', 'FeatureGrid',
    'Testimonial', 'Button', 'Card',
}

# Phase 47.36: identifiers the capability-gated Client API binding
# references through assembler-owned fixed import lines against the
# provider-scaffold clientApi module (src/lib/clientApi.js) and the native
# ContactForm organism. Only materialize in sections when the Project
# Capability Contract enables the binding.
# Phase 47.41: the app-level cart owner (src/lib/cart.js) joins the same
# scaffold-identifier contract (CartProvider/useCart/CartDrawer), plus the
# commerce organisms the catalog surface composes.
_CLIENT_API_IDENTIFIERS = {'clientApi', 'useClientProducts', 'ContactForm',
                           'CartProvider', 'useCart', 'CartDrawer',
                           'CatalogGrid', 'ProductDetail', 'Pagination',
                           'Button', 'Badge'}

# Manifest attribution for sections composed from scaffold organisms when
# no matched component carries the attribution.
_SCAFFOLD_COMPOSED = {
    'Pricing': 'native/PricingCard',
    'FAQ': 'native/FAQ',
    'MenuHighlights': 'native/ProductGrid',
    'ContactForm': 'native/ContactForm',
}

_LUCIDE_ICON_WHITELIST = {
    'ArrowRight', 'ArrowLeft', 'ArrowUpRight', 'Check', 'X', 'Menu', 'Star',
    'Phone', 'Mail', 'MapPin', 'Clock', 'Users', 'Award', 'Heart', 'Camera',
    'Building2', 'Home', 'Briefcase', 'Globe', 'ChevronRight', 'Sun', 'Moon',
    'Sparkles', 'TrendingUp', 'Target', 'Layers', 'Box', 'Palette', 'Code',
    'Rocket', 'Compass', 'Lightbulb', 'Quote', 'UtensilsCrossed', 'Coffee',
    'ChefHat', 'Calendar', 'MessageCircle', 'ThumbsUp', 'BadgeCheck',
    'Zap', 'Shield', 'Ruler', 'PencilRuler',
}

# Pattern sections built deterministically (no LLM call — ADR-0076/0077/0078/0079
# cost control). The home Hero remains LLM-generated (novel showcase
# composition); SECONDARY-page heroes AND Content sections are deterministic
# (ADR-0078/0079 — the ContentArtifact already carries the full copy).
# Phase 47.36: ContactForm is a capability-gated deterministic section
# (leads binding) — only ArchitectureEngine injects it for lead-capable
# projects' contact pages.
_PATTERN_SECTIONS = ('ServicesGrid', 'FeatureGrid', 'MenuHighlights',
                     'About', 'Pricing', 'FAQ', 'Testimonial', 'ContactCTA',
                     'Gallery', 'Content', 'ContactForm')

# Phase 47.26 (ADR-0078): the exact CSS-variable vocabulary the LLM may use
# (mirrors tokens.css). The model previously invented `--nx-*` names from
# the theme payload's prefix hint â€” tokens.css defines none of those.
_TOKEN_VOCABULARY_PROMPT = (
    "Use ONLY these CSS custom properties (they exist in the global "
    "stylesheet): --color-primary, --color-primary-foreground, "
    "--color-background, --color-foreground, --color-secondary, "
    "--color-accent, --color-border, --color-muted, --color-card, "
    "--color-text, --color-surface, --font-heading, --font-body, "
    "--spacing-md, --spacing-lg, --spacing-xl, --spacing-2xl, "
    "--radius-md, --radius-lg, --shadow-md. Never invent other variable "
    "names."
)


class CodeGenerationEngine(BaseGenerationEngine):
    """
    Core AI Code Generation Engine supporting Iterative Generation -> Review -> Fix -> Approve workflow.

    Phase 47.18: consumes the ContentEngine artifact (section bodies, SEO)
    as the source of generated copy, materializes the site layout
    (header/navigation/footer) from the existing architecture page set,
    enforces CTA route integrity against the single authoritative route
    contract (the architecture component hierarchy), and materializes SEO
    metadata (index.html title/description + per-page titles). All through
    the existing engine/prompt/workspace ownership â€” no new services.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing CodeGenerationEngine (Phase 21E.2 Iterative Engine)...")

        try:
            # We instantiate ReviewEngine locally to drive the qualitative feedback loops
            from odoo.addons.nexora_studio.services.generation.engines.review_engine import ReviewEngine
            review_engine = ReviewEngine(self.orchestrator)

            # Iterative Page-by-Page and Section-by-Section logic
            applied_count = 0
            tasks = []
            # Phase 47.23 (ADR-0075): structured fallback evidence, the same
            # contract ContentEngine established (reason codes, no secrets).
            section_fallbacks: Dict[str, str] = {}
            # Phase 47.24 (ADR-0076): pattern sections truthfully skipped
            # (e.g. Gallery without materializable images).
            skipped_sections: List[str] = []
            # Phase 47.26 (ADR-0078): composition manifest â€” per-page
            # per-section generation mode evidence (measurement only).
            composition_manifest: Dict[str, List[Dict[str, Any]]] = {}

            # Consume modular blueprint
            modular_blueprint_dict = artifact.generation_metadata.get("modular_blueprint", {})

            # Phase 47.9 (U8): renderer/provider context consumed from the
            # existing artifact.design structure. Page generation becomes
            # renderer-compatible; the provider scaffold is never recreated.
            renderer_provider = str((artifact.design or {}).get("provider") or "react")
            renderer_import, renderer_tag = self._renderer_page_binding(renderer_provider)

            # Retrieve architecture hierarchy generated by ArchitectureEngine
            component_hierarchy = artifact.architecture.component_hierarchy if hasattr(artifact.architecture, "component_hierarchy") else {}

            # Phase 47.18 (Part F): the single authoritative route contract â€”
            # the page paths of the architecture hierarchy. Every internal
            # CTA must resolve against this set.
            valid_routes = [
                data.get('path', '/')
                for data in component_hierarchy.values()
                if data.get('type') == 'page'
            ]
            valid_routes = list(dict.fromkeys(valid_routes or ['/']))

            # Phase 47.18 (Part C): structured generation context (business,
            # research, knowledge) â€” the same bounded digest contract
            # ContentEngine established, consumed at the code boundary.
            generation_context = self._generation_context(artifact)

            # Phase 47.19 (Part C): materialize the branded hero visual the
            # AssetEngine produced, so the generated site actually ships a
            # real visual asset (closes 47.18 Assets 2/10 consumption gap).
            # Written to Vite's public/ directory, served at repo root.
            hero_image = self._hero_image_payload(artifact)
            if hero_image:
                self._apply_patch('public/hero-visual.svg', hero_image['content'], runtime)
                tasks.append('public/hero-visual.svg')

            # Phase 47.24 (ADR-0076): materialize the stock photos the
            # AssetEngine collected (optional; failures fall back to the
            # deterministic SVG hero above â€” never a hard dependency).
            stock_images, stock_evidence = self._materialize_stock_images(artifact, runtime)

            # Phase 47.24 (ADR-0076): materialize source-backed external
            # components (retrieved through the reconciled canonical
            # registry path) as their own modules; the page assembler
            # imports them through assembler-owned known-import lines.
            external_imports, external_evidence = self._materialize_external_components(
                artifact, runtime)
            for entry in external_evidence:
                tasks.append(entry.get('path'))

            # Phase 47.24: hero display preference â€” a materialized stock
            # photo wins; the branded SVG remains the deterministic floor.
            hero_display = dict(hero_image) if hero_image else None
            stock_hero = stock_images.get('stock_hero')
            if stock_hero:
                hero_display = {
                    'path': stock_hero['path'],
                    'alt': stock_hero['alt'],
                    'content': None,
                }

            for comp_id, comp_data in component_hierarchy.items():
                if comp_data.get("type") != "page": continue

                path = comp_data.get("path", "/")
                filename = "index.tsx" if path == "/" else f"{path.strip('/')}.tsx"
                page_path = f"src/pages/{filename}"
                page_module_name = self._page_module_name(path)
                section_modules = []
                section_names = []
                # Phase 47.23 (ADR-0075): per-page assembler state â€” known
                # imports required by generated sections, and structured
                # fallback evidence (mirrors ContentEngine's reporting).
                page_extra_imports = []

                # Retrieve sections mapped for this page
                sections = comp_data.get("sections", ["Hero", "Content"])

                # Phase 47.18 (Part D): the ContentEngine artifact is the
                # source of generated copy for this page's sections.
                page_content = self._page_content_sections(artifact, path)
                page_seo = self._page_seo(artifact, path)

# Phase 47.26 (ADR-0078): SECONDARY-page heroes are
                # deterministic — they render heading + ContentEngine copy +
                # the platform-chosen hero image + routes, all platform-owned
                # data. They compose the native Hero organism (SiteLayout
                # precedent: guaranteed scaffold file, assembler-owned fixed
                # import line). The HOME hero is now ALSO deterministic
                # (Phase 47.28: evidence-gated, A/B validated).
                is_home = (path == '/')
                page_records: List[Dict[str, Any]] = []
                composition_manifest[path] = page_records

                for section_index, section in enumerate(sections):
                    section_name = self._section_component_name(section, section_index)
                    selected_component = self._find_selected_component(
                        artifact, section
                    )

                    if self._is_hero_section(section):
                        # Both home and secondary heroes are now deterministic
                        if is_home:
                            built = self._build_deterministic_home_hero(
                                section_name, artifact, page_content,
                                hero_display, valid_routes, runtime)
                        else:
                            built = self._build_secondary_hero(
                                section, section_name, page_content,
                                section_index, hero_display, valid_routes,
                                runtime, artifact=artifact)
                        section_code, section_imports, hero_mode = built
                        self._validate_section_module(
                            section_name, section_code,
                            known_identifiers=set(external_imports) | {'Hero', 'Button'})
                        section_modules.append(section_code)
                        section_names.append(section_name)
                        page_extra_imports.extend(section_imports)
                        page_records.append({
                            'type': str(section), 'mode': hero_mode,
                            'component': 'native/Hero',
                            'source': 'native_library',
                        })
                        continue

                    # Phase 47.24 (ADR-0076): deterministic pattern sections
                    # (ServicesGrid / Testimonial / ContactCTA / Gallery) â€”
                    # no LLM call, ContentEngine copy + theme tokens + lucide
                    # icons + external components + stock images.
                    section_imports: List[str] = []
                    if section in _PATTERN_SECTIONS:
                        built = self._build_pattern_section(
                            section, section_name, artifact, page_content,
                            section_index, selected_component,
                            external_imports, stock_images, valid_routes,
                            page_path=path)
                        if built is None:
                            # Gallery without images is skipped truthfully.
                            _logger.info(
                                "Pattern section %s skipped (no materializable content).",
                                section)
                            skipped_sections.append(str(section))
                            continue
                        section_code, section_imports = built
                        self._validate_section_module(
                            section_name, section_code,
                            known_identifiers=(set(external_imports)
                                               | _SCAFFOLD_COMPONENT_IDENTIFIERS
                                               | _CLIENT_API_IDENTIFIERS))
                        section_modules.append(section_code)
                        section_names.append(section_name)
                        page_extra_imports.extend(section_imports)
                        # Phase 47.26 (ADR-0078): composition manifest.
                        comp_source = 'deterministic'
                        comp_component = None
                        if selected_component is not None:
                            md = selected_component.get('metadata') or {}
                            comp_component = selected_component.get('component_id')
                            comp_source = ('hybrid' if md.get('source_provider')
                                           else 'deterministic')
                        else:
                            # Scaffold-composed organisms: attributed ONLY
                            # when the builder actually emitted the organism
                            # import (a fallback composition stays
                            # unattributed).
                            scaffold = _SCAFFOLD_COMPOSED.get(str(section))
                            if scaffold:
                                organism = scaffold.split('/', 1)[1]
                                if any(organism in imp
                                       for imp in section_imports):
                                    comp_component = scaffold
                        page_records.append({
                            'type': str(section), 'mode': comp_source,
                            'component': comp_component,
                            'source': ((selected_component or {}).get('metadata') or {}).get('source_provider')
                                      or ('native_library' if comp_component
                                          and str(comp_component).startswith('native/')
                                          else None),
                        })
                        continue

                    # 1. Generate Section (LLM path â€” Hero/Content with the
                    # 47.23 contract).
                    hero_ref = hero_display if self._is_hero_section(section) else None
                    section_code = self._generate_section(
                        section, section_name, artifact, runtime,
                        modular_blueprint_dict, selected_component,
                        page_path=path, section_index=section_index,
                        page_sections=page_content, valid_routes=valid_routes,
                        generation_context=generation_context,
                        hero_image_path=(
                            hero_ref['path']
                            if (hero_ref and self._is_hero_section(section))
                            else None
                        ),
                        hero_image_content=(
                            hero_ref.get('content')
                            if (hero_ref and self._is_hero_section(section))
                            else None
                        ),
                        hero_image_alt=(
                            hero_ref.get('alt')
                            if (hero_ref and self._is_hero_section(section))
                            else None
                        ),
                    )

                    # 2. Review Section & Fix Loop
                    max_fixes = 3
                    for i in range(max_fixes):
                        issues = review_engine.review_section(section, section_code, runtime)
                        if not issues:
                            break # Approve Section
                        _logger.info(f"Fixing {len(issues)} issues in section {section} (Attempt {i+1})")
                        section_code = self._fix_code(section_code, issues, runtime)

                    # Phase 47.18 (Part F): enforce CTA route integrity
                    # against the authoritative route contract.
                    section_code = self._enforce_route_integrity(section_code, valid_routes)

                    # Phase 47.23 (ADR-0075): static identifier/import
                    # validation, then deterministic fallback â€” valid LLM
                    # output is always preserved; invalid output degrades to
                    # a safe section instead of aborting the run. Retrieved
                    # (source-adapted) components keep the legacy checks
                    # until dependency resolution lands.
                    if selected_component is None:
                        issues = self._section_module_issues(
                            section_name, section_code,
                            known_identifiers=(set(external_imports)
                                               | _SCAFFOLD_COMPONENT_IDENTIFIERS
                                               | _CLIENT_API_IDENTIFIERS))
                        if issues:
                            fallback_reason = 'ai_section_validation_failed: ' + '; '.join(issues[:4])
                            _logger.warning(
                                "Section %s failed static validation (%s). "
                                "Falling back to deterministic section.",
                                section_name, fallback_reason)
                            section_code = self._deterministic_section_fallback(
                                section_name, section, page_content,
                                section_index,
                                hero_image_path=(
                                    hero_display['path']
                                    if (hero_display and self._is_hero_section(section))
                                    else None
                                ),
                            )
                            section_code = self._enforce_route_integrity(section_code, valid_routes)
                            # The fallback is valid by construction; a
                            # failure here is an implementation bug.
                            self._validate_section_module(section_name, section_code)
                            section_fallbacks[section_name] = fallback_reason
                            page_records.append({
                                'type': str(section), 'mode': 'fallback',
                                'component': None, 'source': None,
                            })
                        else:
                            section_imports = self._required_known_imports(section_code)
                            page_extra_imports.extend(section_imports)
                            page_records.append({
                                'type': str(section), 'mode': 'llm',
                                'component': None, 'source': None,
                            })
                    elif self._is_hero_section(section):
                        page_records.append({
                            'type': str(section), 'mode': 'llm',
                            'component': None, 'source': None,
                        })
                    self._validate_section_module(section_name, section_code)
                    section_modules.append(section_code)
                    section_names.append(section_name)

                # Phase 47.9 (U8): the renderer scene component (provider-owned
                # scaffold) is bound into the home page. Canvas/Spline scene
                # ownership stays with the provider; the page only references it.
                page_imports = [renderer_import] if (path == "/" and renderer_import) else []
                # Phase 47.23 (ADR-0075): assembler-owned known imports for
                # constructs the generated sections actually use.
                page_imports.extend(dict.fromkeys(page_extra_imports))
                page_tags = [renderer_tag] if (path == "/" and renderer_tag) else []
                page_code = self._build_page_module(
                    page_module_name, section_modules, section_names,
                    extra_imports=page_imports, extra_tags=page_tags,
                    seo_title=page_seo.get('title'),
                )

                # 3. Page Review & Fix Loop
                max_fixes = 3
                for i in range(max_fixes):
                    issues = review_engine.review_page(path, page_code, runtime)
                    if not issues:
                        break # Approve Page
                    _logger.info(f"Fixing {len(issues)} issues on page {path} (Attempt {i+1})")
                    page_code = self._fix_code(page_code, issues, runtime)

                # 4. Apply Page Code
                self._apply_patch(page_path, page_code, runtime)
                applied_count += 1
                tasks.append(page_path)

            # Phase 47.18 (Part E): materialize the site layout (header with
            # navigation + footer) from the same authoritative page set.
            layout_code = self._build_site_layout(artifact, valid_routes)
            self._apply_patch('src/components/SiteLayout.jsx', layout_code, runtime)
            tasks.append('src/components/SiteLayout.jsx')

            # Keep the shipped Vite entry as the single application router,
            # wrapped in the site layout (nav + footer on every page).
            self._apply_patch('src/App.jsx', self._build_app_entry(
                component_hierarchy, artifact), runtime)
            tasks.append('src/App.jsx')

            # Phase 47.18 (Part G): materialize SEO metadata into the shipped
            # HTML document (title + meta description from the content SEO
            # artifact, business name fallback).
            self._materialize_seo(artifact, runtime, tasks)

            metadata = {
                "tasks_planned": len(tasks),
                "patches_applied": applied_count,
                "renderer_provider": renderer_provider,
                "valid_routes": valid_routes,
            }
            if section_fallbacks:
                metadata["code_fallbacks"] = section_fallbacks
                metadata["code_fallback_count"] = len(section_fallbacks)
            # Phase 47.26 (ADR-0078): composition manifest â€” per-page,
            # per-section generation evidence (measurement only).
            pattern_meta = (artifact.generation_metadata.get('page_pattern') or {})
            metadata["composition_manifest"] = {
                'pattern': pattern_meta.get('id'),
                'pages': composition_manifest,
            }
            modes = [s['mode'] for sections in composition_manifest.values()
                     for s in sections]
            if modes:
                metadata["deterministic_composition_pct"] = round(
                    100 * sum(1 for m in modes if m in ('deterministic', 'hybrid'))
                    / len(modes))
                # Phase 47.27 (ADR-0079): per-mode composition percentages.
                for mode in ('deterministic', 'llm', 'hybrid', 'fallback'):
                    metadata["%s_composition_pct" % mode] = round(
                        100 * sum(1 for m in modes if m == mode) / len(modes))
            # Phase 47.24 (ADR-0076): resource-consumption evidence.
            metadata["external_components"] = external_evidence
            metadata["external_component_count"] = len(external_evidence)
            metadata["stock_images"] = stock_evidence
            if stock_images:
                metadata["stock_image_roles"] = sorted(stock_images.keys())
            if skipped_sections:
                metadata["skipped_sections"] = skipped_sections
            return EngineExecutionResult(success=True, artifact=artifact, metadata=metadata, error=None)

        except Exception as e:
            _logger.error(f"CodeGenerationEngine failed: {e}", exc_info=True)
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=str(e))

    @staticmethod
    def _renderer_page_binding(renderer_provider: str):
        """Phase 47.9 (U8): deterministic renderer -> home-page binding.

        Returns (import_line, jsx_tag) for the provider-owned scene component
        that the home page must reference. Ordinary React generation has no
        binding and remains unchanged.
        """
        if renderer_provider == "react_three_fiber":
            return "import Scene from '../scene/Scene.jsx'", "<Scene />"
        if renderer_provider == "spline":
            return "import SplineScene from '../components/SplineScene.jsx'", "<SplineScene />"
        return None, None

    # ------------------------------------------------------------------
    # Phase 47.18 (Parts C/D): generation context + content consumption
    # ------------------------------------------------------------------

    @staticmethod
    def _generation_context(artifact: WebsiteGenerationArtifact) -> Dict[str, Any]:
        """Bounded business/research/knowledge digest from the EXISTING
        artifact contracts â€” identical ownership to ContentEngine's digest.
        Client-provided facts (business) stay distinguishable from
        research-derived facts (research/knowledge with provenance)."""
        req = artifact.requirements
        branding = req.branding or {}

        research = []
        for entry in ((artifact.research or {}).get('business_data') or [])[:6]:
            if not isinstance(entry, dict):
                continue
            payload = entry.get('payload') or {}
            research.append({
                'title': payload.get('title') or payload.get('name', ''),
                'address': payload.get('address') or payload.get('complete_address', ''),
                'rating': payload.get('rating'),
                'source': 'business_search',
            })

        knowledge = []
        for doc in ((artifact.knowledge or {}).get('knowledge_documents') or [])[:4]:
            if not isinstance(doc, dict):
                continue
            knowledge.append({
                'title': doc.get('title', ''),
                'excerpt': str(doc.get('content') or '')[:240],
                'source': doc.get('document_id', ''),
            })

        return {
            'business': {
                'name': req.business_name or branding.get('business_name', ''),
                'category': req.business_category or branding.get('business_category', ''),
                'location': req.location or branding.get('location', ''),
                'audience': req.target_audience,
                'services': (branding.get('services') or [])[:8],
                'supervisor_instruction': getattr(req, 'current_supervisor_instruction', ''),
            },
            'research': research,
            'knowledge': knowledge,
        }

    @staticmethod
    def _page_content_sections(artifact: WebsiteGenerationArtifact, path: str) -> List[Dict[str, Any]]:
        """Phase 47.18 (Part D): the ContentEngine artifact sections for a
        page (index-aligned with the architecture section list)."""
        pages = getattr(artifact.content, 'pages', None) or {}
        page = pages.get(path) or {}
        sections = page.get('sections')
        return sections if isinstance(sections, list) else []

    @staticmethod
    def _page_seo(artifact: WebsiteGenerationArtifact, path: str) -> Dict[str, Any]:
        pages = getattr(artifact.content, 'pages', None) or {}
        seo = (pages.get(path) or {}).get('seo') or {}
        return seo if isinstance(seo, dict) else {}

    def _generate_section(self, section: str, component_name: str, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime', modular_blueprint_dict: dict, selected_component: dict = None,
                          page_path: str = '/', section_index: int = 0,
                          page_sections: Optional[List[Dict[str, Any]]] = None,
                          valid_routes: Optional[List[str]] = None,
                          generation_context: Optional[Dict[str, Any]] = None,
                          hero_image_path: Optional[str] = None,
                          hero_image_content: Optional[str] = None,
                          hero_image_alt: Optional[str] = None) -> str:
        source_code = (selected_component or {}).get('code')
        if source_code and source_code != "/* Code generated by Orchestrator */":
            return self._adapt_source_component(
                source_code, component_name, selected_component
            )

        # Phase 47.18 (Part D): the section's copy comes from the ContentEngine
        # artifact (index-aligned, type-aligned fallback).
        content_body = ''
        content_heading = ''
        if page_sections:
            matched = None
            if section_index < len(page_sections):
                matched = page_sections[section_index]
            else:
                section_lower = str(section).lower()
                for candidate in page_sections:
                    if str(candidate.get('type', '')).lower() == section_lower:
                        matched = candidate
                        break
            if matched:
                content_body = str(matched.get('body', ''))
                content_heading = str(matched.get('semantic_heading', ''))

        # Phase 47.23 (ADR-0075): payload contract hardening. The copy and
        # the route contract are inlined into the task as LITERAL TEXT â€” the
        # previous context keys ("content", "content_heading",
        # "available_routes") whose values were code-shaped invited models
        # to copy the key names as undeclared identifiers (the observed
        # `content_heading is not defined` failure class). The context now
        # carries only metadata that cannot be mistaken for source
        # identifiers.
        task = (
            f"Generate a valid React component declaration named {component_name} "
            f"for the {section} section. Return only the declaration; do not "
            "include imports or a default export."
        )
        if content_heading:
            safe_heading = content_heading.replace('"', '\\"')
            task += f' Include a heading with the exact literal text "{safe_heading}".'
        if content_body:
            task += (
                " Render this body copy faithfully as paragraph text "
                "(it is literal copy, NOT code or variables): "
                + content_body
            )
        if valid_routes:
            task += (
                " Only link internally to these routes: "
                + ", ".join(valid_routes) + "."
            )
        if hero_image_path:
            hero_alt = (hero_image_alt or 'hero visual').replace('"', '')
            task += (
                f" Render the hero visual at {hero_image_path} as an <img> "
                f'inside this section with alt text "{hero_alt}".'
            )
        task += (
            " Reference no variables other than the ones you declare inside "
            "this module; use only identifiers you have defined. "
            + _TOKEN_VOCABULARY_PROMPT +
            " Prefer plain <a> elements for "
            "internal links. You may use lucide-react icons (e.g. ArrowRight, "
            "Star, Check, MapPin) by their JSX tag name like <ArrowRight /> â€” "
            "imports are provided automatically; do not write import statements."
        )

        # Phase 47.26 (ADR-0078): the theme payload for LLM sections carries
        # only the palette/fonts + the EXACT token names â€” the full
        # design_tokens dict (with its misleading 'prefix' hint) previously
        # invited the model to invent `--nx-*` variables.
        theme_dict = dict(artifact.theme.__dict__) if hasattr(artifact.theme, '__dict__') else {}
        theme_dict.pop('design_tokens', None)

        payload = {
            "task": task,
            "page_path": page_path,
            "section_type": section,
            "theme": theme_dict,
            "theme_css_variables": _TOKEN_VOCABULARY_PROMPT,
            "blueprint": modular_blueprint_dict,
            "selected_component": selected_component,
            "renderer_provider": str((artifact.design or {}).get("provider") or "react"),
            "business": (generation_context or {}).get('business', {}),
            "research": (generation_context or {}).get('research', []),
            "knowledge": (generation_context or {}).get('knowledge', []),
        }
        # Phase 47.19 (Part C): the hero asset reference reaches the section
        # only when a real hero visual actually exists (never fabricated).
        if hero_image_path:
            payload["hero_image_path"] = hero_image_path
        if hero_image_content:
            payload["hero_image_content"] = hero_image_content
        try:
            response = runtime.ai.generate("ai_code_patch", payload)
            return self._strip_code_fences(response.get("full_content", ""))
        except Exception as e:
            raise RuntimeError(f"Failed to generate required section {section}: {e}") from e

    @staticmethod
    def _strip_code_fences(code: str) -> str:
        """Remove Markdown code fences a real LLM may wrap around a section.

        Providers (e.g. MiniMax) frequently emit ```` ```jsx ... ``` ````
        despite the "return only the declaration" instruction. Fences leave
        the component un-declared at runtime (the text becomes a template
        literal), so strip the outer fence markers and keep the code body.
        """
        text = (code or '').strip()
        if not text:
            return ''
        # Remove a leading fence line that may carry a language tag.
        m = re.match(r'^```[a-zA-Z0-9_+-]*\s*\n(.*)\n```\s*$', text, re.DOTALL)
        if m:
            return m.group(1).strip()
        # Tolerate fences that are the entire first/last lines without an
        # inner wrapper (multiple blocks are not expected for one section).
        if text.startswith('```'):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines).strip()
        return text

    # ------------------------------------------------------------------
    # Phase 47.18 (Part F): CTA route integrity
    # ------------------------------------------------------------------

    _HREF_RE = re.compile(r'href="(/[^"]*)"')

    @classmethod
    def _enforce_route_integrity(cls, code: str, valid_routes: List[str]) -> str:
        """Every internal href must resolve against the authoritative route
        contract. Trailing-slash variants normalize to the canonical route;
        unknown internal destinations resolve to home rather than shipping a
        broken link. External URLs (http/https/mailto/tel/#) are untouched.
        """
        if not valid_routes:
            return code
        canonical = {r.rstrip('/'): r for r in valid_routes}

        def _replace(match):
            href = match.group(1)
            key = href.rstrip('/')
            if key in canonical:
                return 'href="%s"' % canonical[key]
            # Unknown internal destination: resolve to home, never 404.
            home = canonical.get('') or canonical.get('/') or valid_routes[0]
            return 'href="%s"' % home

        return cls._HREF_RE.sub(_replace, code)

    # ------------------------------------------------------------------
    # Phase 47.18 (Part E): site layout materialization
    # ------------------------------------------------------------------

    @staticmethod
    def _route_label(path: str) -> str:
        segment = path.strip('/')
        if not segment:
            return 'Home'
        return ' '.join(part.capitalize() for part in re.split(r'[-_]+', segment))

    def _build_site_layout(self, artifact: WebsiteGenerationArtifact, valid_routes: List[str]) -> str:
        """Header + navigation + footer materialized from the SAME
        authoritative page set the router uses. The nav links are generated
        from the route contract, so they are valid by construction."""
        req = artifact.requirements
        business = (req.business_name
                    or (req.branding or {}).get('business_name')
                    or 'Studio')
        location = req.location or (req.branding or {}).get('location', '')
        nav_items = ', '.join(
            "{{ href: '{path}', label: '{label}' }}".format(
                path=path, label=self._route_label(path))
            for path in valid_routes
        )
        footer_location = " &middot; " + location if location else ""
        # Phase 47.41: products-capable projects get the app-level cart
        # entry point (nav badge + drawer) in the site chrome. The state
        # itself is owned by CartProvider (src/lib/cart.js) mounted at the
        # App entry — SiteLayout only CONSUMES it.
        has_cart = 'products' in self._client_api_capabilities(artifact)
        cart_header = ''
        cart_footer_mount = ''
        cart_state = ''
        if has_cart:
            cart_state = (
                "  const cart = useCart();\n"
                "  const [cartOpen, setCartOpen] = React.useState(false);\n"
            )
            cart_header = (
                "        <button type=\"button\" onClick={() => setCartOpen(true)}\n"
                "          aria-label={'Open cart (' + cart.count + ' items)'}\n"
                "          style={{ fontFamily: 'var(--font-body, Inter, sans-serif)', fontSize: 14,\n"
                "            letterSpacing: '0.04em', color: 'var(--color-secondary, #6f6a63)',\n"
                "            background: 'transparent', border: '1px solid var(--color-border, #e5ded4)',\n"
                "            borderRadius: 'var(--radius-md, 8px)', padding: '8px 14px', cursor: 'pointer',\n"
                "            display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 88 }}>\n"
                "          Cart\n"
                "          <span aria-hidden=\"true\" style={{\n"
                "            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',\n"
                "            minWidth: 22, height: 22, borderRadius: 999, fontSize: 12,\n"
                "            background: 'var(--color-primary, #2563eb)', color: 'var(--color-background, #ffffff)',\n"
                "            fontWeight: 700 }}>{cart.count}</span>\n"
                "        </button>\n"
            )
            cart_footer_mount = (
                "      <CartDrawer\n"
                "        open={cartOpen}\n"
                "        items={cart.items.map(function(i) { return {\n"
                "          id: i.id, name: i.name,\n"
                "          price: i.price != null ? '$' + i.price.toFixed(2) : '',\n"
                "          image: i.image ? { src: i.image, alt: i.name } : null,\n"
                "          quantity: i.quantity } })}\n"
                "        subtotal={'$' + cart.subtotalValue.toFixed(2)}\n"
                "        onIncrement={cart.increment}\n"
                "        onDecrement={cart.decrement}\n"
                "        onRemove={cart.remove}\n"
                "        onContinueShopping={function() { setCartOpen(false) }}\n"
                "        onClose={function() { setCartOpen(false) }}\n"
                "      />\n"
            )
        # Phase 47.23 (ADR-0075): the site layout uses the theme's CSS
        # variables (fonts + palette) so the deterministic chrome is
        # typographically coherent with the theme materialized in tokens.css.
        return (
            "import React from 'react'\n"
            + ("import { useCart } from '../lib/cart.js'\n"
               "import CartDrawer from './CartDrawer.jsx'\n" if has_cart else "")
            + "\nconst NAV_ITEMS = [" + nav_items + "]\n\n"
            "function SiteLayout({ children }) {\n"
            + cart_state
            + "  return (\n"
            "    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>\n"
            "      <header style={{ position: 'sticky', top: 0, zIndex: 20, background: 'var(--color-background, #ffffff)',\n"
            "        borderBottom: '1px solid var(--color-border, #e5ded4)' }}>\n"
            "        <div style={{ maxWidth: 1120, margin: '0 auto', padding: '20px 24px',\n"
            "          display: 'flex', alignItems: 'center', justifyContent: 'space-between',\n"
            "          gap: 24, flexWrap: 'wrap' }}>\n"
            "          <a href=\"/\" style={{ fontFamily: 'var(--font-heading, Georgia, serif)', fontSize: 20,\n"
            "            color: 'var(--color-text, #1c1917)', textDecoration: 'none', letterSpacing: '0.02em' }}>\n"
            "            " + business.replace("'", "\\'") + "</a>\n"
            "          <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>\n"
            "          <nav aria-label=\"Primary\" style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>\n"
            "            {NAV_ITEMS.map(function(item) { return (\n"
            "              <a key={item.href} href={item.href}\n"
            "                style={{ fontFamily: 'var(--font-body, Inter, sans-serif)',\n"
            "                  fontSize: 14, letterSpacing: '0.08em', textTransform: 'uppercase',\n"
            "                  color: 'var(--color-secondary, #6f6a63)', textDecoration: 'none' }}>{item.label}</a>\n"
            "            ) })}\n"
            "          </nav>\n"
            + cart_header +
            "          </div>\n"
            "        </div>\n"
            "      </header>\n"
            "      <div style={{ flex: 1 }}>{children}</div>\n"
            + cart_footer_mount +
            "      <footer style={{ background: 'var(--color-foreground, #1c1917)', color: 'var(--color-background, #faf9f7)',\n"
            "        padding: '56px 24px', marginTop: 'auto' }}>\n"
            "        <div style={{ maxWidth: 1120, margin: '0 auto', display: 'flex',\n"
            "          justifyContent: 'space-between', gap: 24, flexWrap: 'wrap',\n"
            "          alignItems: 'center' }}>\n"
            "          <span style={{ fontFamily: 'var(--font-heading, Georgia, serif)', fontSize: 18, color: 'var(--color-background, #ffffff)' }}>\n"
            "            " + business.replace("'", "\\'") + "</span>\n"
            "          <span style={{ fontFamily: 'var(--font-body, Inter, sans-serif)',\n"
            "            fontSize: 13, letterSpacing: '0.08em' }}>\n"
            "            &copy; {new Date().getFullYear()}" + footer_location + "</span>\n"
            "        </div>\n"
            "      </footer>\n"
            "    </div>\n"
            "  )\n"
            "}\n\n"
            "export default SiteLayout\n"
        )

    # ------------------------------------------------------------------
    # Phase 47.18 (Part G): SEO materialization
    # ------------------------------------------------------------------

    def _materialize_seo(self, artifact: WebsiteGenerationArtifact,
                         runtime: 'GenerationRuntime', tasks: List[str]) -> None:
        """Patch the shipped index.html with the home-page SEO title and
        meta description from the ContentEngine artifact (business-name
        fallback). Per-page titles are set by each page module through
        document.title."""
        home_seo = self._page_seo(artifact, '/')
        req = artifact.requirements
        business = req.business_name or (req.branding or {}).get('business_name', '')
        title = home_seo.get('title') or (business + ' | ' + req.domain if business else '')
        description = home_seo.get('description', '')

        try:
            html = runtime.workspace.read_file('index.html')
        except Exception:
            return  # template not materialized â€” skip truthfully

        patched = html
        if title:
            safe_title = (
                title.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))
            patched = re.sub(
                r'<title>.*?</title>',
                lambda _m: '<title>%s</title>' % safe_title,
                patched, count=1, flags=re.DOTALL)
        if description:
            description_escaped = (
                description.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))
            if '<meta name="description"' in patched:
                patched = re.sub(
                    r'<meta name="description"[^>]*>',
                    '<meta name="description" content="%s">' % description_escaped,
                    patched, count=1)
            else:
                patched = patched.replace(
                    '</head>',
                    '  <meta name="description" content="%s">\n</head>' % description_escaped,
                    1)
        if patched != html:
            self._apply_patch('index.html', patched, runtime)
            tasks.append('index.html')

    @staticmethod
    def _find_selected_component(artifact: WebsiteGenerationArtifact, section: str):
        """Phase 47.24 (ADR-0076): token/alias-aware selection using the
        SAME semantic expansion as ComponentIntelligenceEngine (single
        matching vocabulary), with the source-code gate preserved â€” only
        nodes carrying REAL retrieved source qualify."""
        from odoo.addons.nexora_studio.services.generation.engines.component_intelligence_engine import (
            _expanded_tokens, _tokens)
        st = (str(section or '')).lower()
        if not st:
            return None
        section_tokens = _expanded_tokens(st)
        best = None
        best_match = (-1, -1, -1)  # (has_source_code, overlap_count, substring)
        for node in artifact.component_tree.nodes:
            if not isinstance(node, dict):
                continue
            metadata = node.get('metadata') or {}
            if not metadata.get('from_source'):
                continue
            code = node.get('code') or ''
            has_code = 1 if (code and '/* Code generated by Orchestrator */' not in code) else 0
            if not has_code:
                continue
            haystack = " ".join(filter(None, [
                str(metadata.get('semantic', '')),
                str(metadata.get('source_identifier', '')),
                str(node.get('component_id', '')),
            ])).lower()
            if not haystack:
                continue
            overlap = len(section_tokens & _tokens(haystack))
            compact = st.replace(' ', '')
            substring = 1 if (compact and compact in haystack.replace('_', '').replace('-', '')) else 0
            # Semantic relevance required â€” a source node never matches a
            # section it shares no semantics with (the 47.24 sanity run
            # showed zero-overlap nodes capturing every section).
            if overlap == 0 and substring == 0:
                continue
            match = (has_code, overlap, substring)
            if match > best_match:
                best_match = match
                best = node
        return best if best_match[0] == 1 else None

    @staticmethod
    def _adapt_source_component(code: str, component_name: str, selected_component: dict) -> str:
        default_named = re.search(
            r'\bexport\s+default\s+(?:function|class)\s+([A-Za-z_$][\w$]*)',
            code,
        )
        if default_named:
            original = default_named.group(1)
            code = re.sub(r'\bexport\s+default\s+', '', code, count=1)
            if original != component_name:
                code += f"\nconst {component_name} = {original}\n"
            return code

        declared = re.search(
            r'\b(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)',
            code,
        )
        if declared:
            original = declared.group(1)
            code = re.sub(r'\bexport\s+default\s+' + re.escape(original) + r'\b', '', code)
            if original != component_name:
                code += f"\nconst {component_name} = {original}\n"
            return code

        raise ValueError(
            "Selected source component does not contain an adaptable React declaration: "
            f"{selected_component.get('component_id')}"
        )

    def _fix_code(self, code: str, issues: list, runtime: 'GenerationRuntime') -> str:
        payload = {
            "task": "Fix the provided code based on review issues",
            "code": code,
            "issues": issues
        }
        try:
            response = runtime.ai.generate("ai_bug_fixing", payload)
            return self._strip_code_fences(response.get("full_content", code))
        except Exception as e:
            _logger.warning(f"Failed to fix code: {e}")
            return code

    def _apply_patch(self, path: str, code: str, runtime: 'GenerationRuntime') -> None:
        try:
            runtime.workspace.write_file(path, code)
        except Exception as e:
            _logger.error(f"Failed to apply patch to {path}: {e}")
            raise RuntimeError(f"Failed to apply required generated file {path}: {e}") from e

    @staticmethod
    def _page_module_name(path: str) -> str:
        slug = re.sub(r'[^A-Za-z0-9]+', '_', path.strip('/') or 'home').strip('_')
        return ''.join(part.capitalize() for part in slug.split('_')) + 'Page'

    @staticmethod
    def _section_component_name(section: str, index: int) -> str:
        slug = re.sub(r'[^A-Za-z0-9]+', '_', str(section)).strip('_') or 'Section'
        return ''.join(part.capitalize() for part in slug.split('_')) + f'Section{index + 1}'

    @staticmethod
    def _is_hero_section(section: str) -> bool:
        """The hero section is the one that owns the branded hero visual.
        Mirrors AssetEngine's hero-section rule (exact 'hero' or any
        hero-prefixed name)."""
        token = str(section or '').lower().strip()
        return token == 'hero' or token.startswith('hero')

    @staticmethod
    def _hero_image_payload(artifact: WebsiteGenerationArtifact) -> Optional[Dict[str, Any]]:
        """Locate the branded hero visual the AssetEngine produced (real SVG
        content), mapping it to a public asset path. Returns None when no
        hero visual exists â€” the asset reference is never fabricated."""
        assets = getattr(artifact, 'assets', None)
        images = getattr(assets, 'images', None) or []
        for img in images:
            if not isinstance(img, dict):
                continue
            if img.get('id') != 'hero_visual':
                continue
            content = img.get('content') or ''
            if '<svg' not in content:
                continue
            return {
                'path': '/hero-visual.svg',
                'content': content,
                'alt': (img.get('metadata') or {}).get('alt', 'hero visual'),
            }
        return None

    @staticmethod
    def _validate_section_module(component_name: str, code: str,
                                 known_identifiers=None) -> None:
        issues = CodeGenerationEngine._section_module_issues(
            component_name, code, known_identifiers=known_identifiers)
        if issues:
            raise ValueError(
                f"Generated section {component_name} failed validation: "
                + "; ".join(issues)
            )

    # ------------------------------------------------------------------
    # Phase 47.23 (ADR-0075): static identifier/import validation +
    # assembler-owned import scaffolding + deterministic fallback.
    # ------------------------------------------------------------------

    _STRING_RE = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`")
    _COMMENT_RE = re.compile(r'/\*.*?\*/|//[^\n]*', re.DOTALL)
    _DECL_RE = re.compile(r'\b(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)')
    _DESTRUCT_RE = re.compile(r'\b(?:const|let|var)\s+\[([^\]]+)\]')
    _PARAMS_RE = re.compile(
        r'\bfunction\s*(?:[A-Za-z_$][\w$]*\s*)?\(([^)]*)\)|\(([^()]*)\)\s*=>')
    # JSX expression containers: a bare identifier (or the base of a member
    # chain) inside braces â€” NOT a JS statement block (identifier followed
    # by `:` or `(` is a block/object, not an expression container).
    _JSX_EXPR_RE = re.compile(r'\{\s*([A-Za-z_$][\w$]*)\s*(?:\.|\})')
    _ATTR_EXPR_RE = re.compile(r'[A-Za-z_$][\w$-]*=\{\s*([A-Za-z_$][\w$]*)\s*(?:\.|\})')
    _JSX_TAG_RE = re.compile(r'</?\s*([A-Z][\w$]*)')
    _IMPORT_RE = re.compile(r'\bimport\s+[^;\'"]*?\s*from\s*[\'"]([^\'"]+)[\'"]|\bimport\s+[\'"]([^\'"]+)[\'"]|\brequire\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)')

    @classmethod
    def _strip_strings_and_comments(cls, code: str) -> str:
        text = cls._COMMENT_RE.sub(' ', code or '')
        text = cls._STRING_RE.sub(' ', text)
        return text

    @classmethod
    def _collect_declared_identifiers(cls, code: str) -> set:
        declared = set()
        for m in cls._DECL_RE.finditer(code):
            declared.add(m.group(1))
        for m in cls._DESTRUCT_RE.finditer(code):
            for part in m.group(1).split(','):
                token = part.strip()
                if token and re.match(r'^[A-Za-z_$][\w$]*$', token):
                    declared.add(token)
        for m in cls._PARAMS_RE.finditer(code):
            group = m.group(1) or m.group(2) or ''
            for part in group.split(','):
                token = part.strip().strip('{}').split('=')[0].strip()
                if token and re.match(r'^[A-Za-z_$][\w$]*$', token):
                    declared.add(token)
        return declared

    @classmethod
    def _section_module_issues(cls, component_name: str, code: str,
                               known_identifiers=None) -> List[str]:
        """Deterministic static validation of one generated section module.

        Checks (extends, does not replace, _validate_section_module):
          * required component declaration
          * no default export
          * imports restricted to the assembler's known specifiers
          * every bare expression / attribute / JSX component identifier is
            either declared in the module, a known construct the assembler
            can import (Link, whitelisted lucide icons, materialized
            external components), or a JS/browser global â€” undefined
            identifier references (the `content_heading` / un-imported
            `<Link>` failure classes from the 47.22 audit) are caught here,
            BEFORE browser validation, with a structured reason.
        """
        if not code:
            return ['empty_module']
        issues = []
        declaration = re.compile(
            rf'\b(?:function|class|const|let|var)\s+{re.escape(component_name)}\b'
        )
        if not declaration.search(code):
            issues.append(f'missing_declaration:{component_name}')
        if re.search(r'\bexport\s+default\b', code):
            issues.append('default_export_present')

        # Import specifier whitelist: the assembler owns import paths.
        for m in cls._IMPORT_RE.finditer(code):
            specifier = m.group(1) or m.group(2) or m.group(3)
            if specifier and specifier not in _ALLOWED_IMPORT_SPECIFIERS:
                issues.append(f'non_whitelisted_import:{specifier}')
                break

        text = cls._strip_strings_and_comments(code)
        declared = cls._collect_declared_identifiers(text)
        allowed = (declared | _SAFE_GLOBAL_IDENTIFIERS
                   | set(_KNOWN_SECTION_IMPORTS)
                   | _LUCIDE_ICON_WHITELIST
                   | set(known_identifiers or ()))

        # Invalid token sequences: `var` is a JS declaration keyword and can
        # never be directly followed by `(` in valid code â€” the observed
        # failure class is a model emitting CSS var(...) syntax inside JS
        # object literals (esbuild: Unexpected "var").
        if re.search(r'\bvar\s*\(', text):
            issues.append('invalid_token:var_paren')

        # Structural balance: valid JS/JSX has balanced braces/brackets/
        # parens once strings and comments are stripped.
        for opener, closer in (('{', '}'), ('[', ']'), ('(', ')')):
            depth = 0
            for ch in text:
                if ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth < 0:
                        break
            if depth != 0:
                issues.append('unbalanced:%s%s' % (opener, closer))
                break

        # JSX closing tags must terminate with '>' — a closing tag followed
        # by whitespace/`)` and no '>' (the observed `</article        )`
        # esbuild failure class) is always invalid.
        if re.search(r'</[A-Za-z][\w-]*\s+[^>\s]', text):
            issues.append('invalid_token:unclosed_jsx_close')

        for m in cls._JSX_EXPR_RE.finditer(text):
            ident = m.group(1)
            if ident not in allowed:
                issues.append(f'undefined_identifier:{ident}')
                break
        if not any(i.startswith('undefined_identifier:') for i in issues):
            for m in cls._ATTR_EXPR_RE.finditer(text):
                ident = m.group(1)
                if ident not in allowed:
                    issues.append(f'undefined_identifier:{ident}')
                    break
        if not any(i.startswith('undefined_identifier:') for i in issues):
            for m in cls._JSX_TAG_RE.finditer(text):
                tag = m.group(1)
                if tag not in allowed:
                    issues.append(f'undefined_component:{tag}')
                    break
        return issues

    @classmethod
    def _required_known_imports(cls, code: str) -> List[str]:
        """Assembler-owned import scaffolding: the FIXED known-import lines
        for constructs the section actually uses. Injected only when the
        module does not already carry the whitelisted import itself (the
        model never controls import paths â€” only the fixed table emits)."""
        imports = []
        if re.search(r'<Link[\s>]|</Link>', code or ''):
            if not re.search(
                    r'import\s+\{[^}]*\bLink\b[^}]*\}\s*from\s*[\'"]react-router-dom[\'"]',
                    code):
                imports.append(_KNOWN_SECTION_IMPORTS['Link'])
        # Phase 47.24 (ADR-0076): whitelisted lucide icons used as JSX tags
        # get the FIXED lucide-react import (identifier-bound, safe).
        text = cls._strip_strings_and_comments(code or '')
        used_icons = sorted(set(cls._JSX_TAG_RE.findall(text))
                            & _LUCIDE_ICON_WHITELIST)
        if used_icons and not re.search(
                r'import\s+\{[^}]*\}\s*from\s*[\'"]lucide-react[\'"]', code):
            imports.append('import { %s } from \'lucide-react\'' % ', '.join(used_icons))
        return imports

    @staticmethod
    def _jsx_text_literal(value: str) -> str:
        """Escape literal copy into a JSX string expression so arbitrary
        client text (quotes, braces, newlines) can never break the module."""
        escaped = (value or '').replace('\\', '\\\\').replace("'", "\\'")
        escaped = escaped.replace('\n', '\\n').replace('\r', '')
        return "{'%s'}" % escaped

    # ------------------------------------------------------------------
    # Phase 47.24 (ADR-0076): stock photo + external component
    # materialization and deterministic pattern sections.
    # ------------------------------------------------------------------

    @staticmethod
    def _materialize_stock_images(artifact: WebsiteGenerationArtifact,
                                  runtime: 'GenerationRuntime'):
        """Download the AssetEngine's stock-photo entries into Vite's public
        directory. Returns ({entry_id: {path, alt}}, evidence). Failures are
        skipped â€” the deterministic SVG hero remains the floor."""
        from odoo.addons.nexora_studio.services.providers.asset import pexels_provider
        materialized: Dict[str, Dict[str, str]] = {}
        evidence: List[Dict[str, Any]] = []
        images = getattr(artifact.assets, 'images', None) or []
        for img in images:
            if not isinstance(img, dict):
                continue
            remote_url = img.get('remote_url')
            if not remote_url:
                continue
            entry_id = str(img.get('id') or 'stock')
            out_rel = 'public/images/%s.jpg' % entry_id
            try:
                content = pexels_provider.download_photo(remote_url)
                if not content:
                    evidence.append({'id': entry_id, 'role': img.get('role'),
                                     'failed': True})
                    continue
                runtime.workspace.write_binary(out_rel, content)
                materialized[entry_id] = {
                    'path': '/images/%s.jpg' % entry_id,
                    'alt': str((img.get('metadata') or {}).get('alt')
                               or 'image'),
                }
                evidence.append({'id': entry_id, 'role': img.get('role'),
                                 'bytes': len(content),
                                 'remote': True})
            except Exception as e:
                _logger.warning("Stock image %s materialization failed: %s",
                                entry_id, e)
                evidence.append({'id': entry_id, 'role': img.get('role'),
                                 'failed': True})
        return materialized, evidence

    _NAMED_EXPORT_RE = re.compile(r'export\s*\{([^}]*)\}')
    _DEFAULT_EXPORT_RE = re.compile(
        r'export\s+default\s+(?:function\s+|class\s+)?([A-Za-z_$][\w$]*)')
    _EXPORT_DECL_RE = re.compile(
        r'export\s+(?:function|const|class|let|var)\s+([A-Za-z_$][\w$]*)')

    # TypeScript markers: shadcn registry uses .tsx with generics.
    _TS_MARKER_RE = re.compile(
        r'forwardRef<|HTMLAttributes|React\.FC<|interface\s+[A-Z]|'
        r':\s*(?:string|number|boolean|void)\b')

    @classmethod
    def _external_module_ext(cls, code: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        files = (metadata or {}).get('files') or []
        if any(str(f.get('path', '')).endswith('.tsx') for f in files if isinstance(f, dict)):
            return 'tsx'
        if cls._TS_MARKER_RE.search(code or ''):
            return 'tsx'
        return 'jsx'

    @classmethod
    def _parse_module_exports(cls, code: str):
        """(named exports, default export name) for a retrieved module."""
        named = []
        m = cls._NAMED_EXPORT_RE.search(code or '')
        if m:
            for part in m.group(1).split(','):
                token = part.strip().split(' as ')[0].strip()
                if token:
                    named.append(token)
        named.extend(cls._EXPORT_DECL_RE.findall(code or ''))
        default = None
        dm = cls._DEFAULT_EXPORT_RE.search(code or '')
        if dm:
            default = dm.group(1)
        named = list(dict.fromkeys(named))
        return named, default

    @staticmethod
    def _external_module_name(component_id: str) -> str:
        tail = str(component_id or 'Component').rsplit('/', 1)[-1]
        return ''.join(part.capitalize() for part in re.split(r'[^A-Za-z0-9]+', tail)) or 'Component'

    def _materialize_external_components(self, artifact: WebsiteGenerationArtifact,
                                          runtime: 'GenerationRuntime'):
        """Write source-backed component_tree nodes as their own modules
        under src/components/external/ (same ownership precedent as
        SiteLayout.jsx). Returns (known imports {identifier: import line},
        evidence). The assembler â€” never the LLM â€” controls import paths.

        Phase 47.40: after the component_tree nodes, the visual
        direction's curated effect components (ThemeEngine-owned decision,
        bounded to zero-dependency React Bits entries) are materialized
        FROM the already-discovered candidate_components the canonical
        ComponentDiscoveryEngine published on the artifact — no new
        fetch, no second registry, no arbitrary source."""
        known_imports: Dict[str, str] = {}
        evidence: List[Dict[str, Any]] = []
        for node in getattr(artifact.component_tree, 'nodes', None) or []:
            if not isinstance(node, dict):
                continue
            metadata = node.get('metadata') or {}
            code = node.get('code') or ''
            if not metadata.get('from_source'):
                continue
            if not code or '/* Code generated by Orchestrator */' in code:
                continue
            comp_id = str(node.get('component_id')
                          or metadata.get('source_identifier') or 'Component')
            name = self._external_module_name(comp_id)
            module_code = code
            ext = self._external_module_ext(module_code, metadata)
            named, default = self._parse_module_exports(module_code)
            if not named and not default:
                declared = re.search(
                    r'\b(?:function|const|class)\s+([A-Za-z_$][\w$]*)', module_code)
                if declared:
                    module_code += '\nexport { %s }\n' % declared.group(1)
                    named = [declared.group(1)]
                else:
                    continue

            # Phase 47.25 (ADR-0077): native components are ALREADY
            # materialized by the provider scaffold at workspace_path â€”
            # register the import line against the existing file (writing
            # the code only as a fallback if the file is absent). No
            # duplicate copies under external/.
            workspace_path = metadata.get('workspace_path')
            if metadata.get('source_provider') == 'native_library' and workspace_path:
                try:
                    if not runtime.workspace.exists(workspace_path):
                        runtime.workspace.write_file(workspace_path, module_code)
                        evidence.append({'component_id': comp_id,
                                         'path': workspace_path,
                                         'kind': 'native-written'})
                    else:
                        evidence.append({'component_id': comp_id,
                                         'path': workspace_path,
                                         'kind': 'native'})
                except Exception as e:
                    _logger.warning("Native component %s failed: %s",
                                    workspace_path, e)
                    continue
                # Native library modules use default exports.
                main = default or (named[0] if named else name)
                import_line = "import %s from '../%s'" % (
                    main, workspace_path.replace('src/', '', 1))
                for ident in ([main] if default else named[:8]):
                    known_imports[ident] = import_line
                continue

            # CSS sidecars (React Bits JS-CSS variants) land next to the
            # module so their relative imports resolve unchanged.
            for fname, content in (metadata.get('auxiliary_files') or {}).items():
                side_rel = 'src/components/external/%s' % fname
                try:
                    runtime.workspace.write_file(side_rel, str(content or ''))
                    evidence.append({'component_id': comp_id, 'path': side_rel,
                                     'kind': 'auxiliary'})
                except Exception as e:
                    _logger.warning("Auxiliary file %s failed: %s", side_rel, e)
            file_rel = 'src/components/external/%s.%s' % (name, ext)
            try:
                runtime.workspace.write_file(file_rel, module_code)
            except Exception as e:
                _logger.warning("External component %s failed: %s", file_rel, e)
                continue
            if default:
                import_line = "import %s from '../components/external/%s.%s'" % (default, name, ext)
                known_imports[default] = import_line
                exports = [default]
            else:
                exports = named[:8]
                import_line = "import { %s } from '../components/external/%s.%s'" % (
                    ', '.join(exports), name, ext)
                for ident in exports:
                    known_imports[ident] = import_line
            evidence.append({
                'component_id': comp_id,
                'path': file_rel,
                'exports': exports,
                'provider': metadata.get('source_provider'),
                'kind': 'module',
            })
        # Phase 47.40: curated effect components selected by the visual
        # direction. Source comes EXCLUSIVELY from the candidates the
        # canonical discovery already fetched; a missing candidate means
        # the effect is truthfully not applied (the builders compose the
        # plain fallback — deterministic either way).
        for effect in self._visual_direction(artifact)['effects']:
            if effect in known_imports:
                continue
            package = self._find_candidate_package(artifact, effect)
            if package is None:
                _logger.info("Visual-direction effect %s not present in the "
                             "discovered candidates; plain composition used.",
                             effect)
                continue
            metadata = dict(getattr(package, 'metadata', None) or {})
            code = str(metadata.get('source_code') or '')
            if not code:
                continue
            name = self._external_module_name(effect)
            ext = self._external_module_ext(code, metadata)
            named, default = self._parse_module_exports(code)
            main = default or (named[0] if named else name)
            for fname, content in (metadata.get('auxiliary_files') or {}).items():
                side_rel = 'src/components/external/%s' % fname
                try:
                    runtime.workspace.write_file(side_rel, str(content or ''))
                    evidence.append({'component_id': effect, 'path': side_rel,
                                     'kind': 'auxiliary'})
                except Exception as e:
                    _logger.warning("Auxiliary file %s failed: %s", side_rel, e)
            file_rel = 'src/components/external/%s.%s' % (name, ext)
            try:
                runtime.workspace.write_file(file_rel, code)
            except Exception as e:
                _logger.warning("Effect component %s failed: %s", file_rel, e)
                continue
            import_line = "import %s from '../components/external/%s.%s'" % (
                main, name, ext)
            known_imports[main] = import_line
            evidence.append({
                'component_id': 'react_bits/%s' % effect,
                'path': file_rel,
                'exports': [main],
                'provider': 'react_bits',
                'kind': 'visual_effect',
            })
        return known_imports, evidence

    @staticmethod
    def _find_candidate_package(artifact: WebsiteGenerationArtifact,
                                component_name: str):
        """The already-discovered ComponentPackage for a curated component
        (by source identifier), from the candidate_components the
        ComponentDiscoveryEngine published on the artifact. Returns None
        when the component was not discovered — never fetches."""
        metadata = getattr(artifact, 'generation_metadata', None) or {}
        candidates = metadata.get('candidate_components') or []
        for candidate in candidates:
            pkg = (candidate.get('package')
                   if isinstance(candidate, dict) else candidate)
            if pkg is None:
                continue
            metadata = getattr(pkg, 'metadata', None) or {}
            if (str(metadata.get('source_identifier') or '') == component_name
                    or str(getattr(pkg, 'component_id', '')
                           ).rsplit('/', 1)[-1] == component_name):
                return pkg
        return None

    @staticmethod
    def _section_copy(page_sections: Optional[List[Dict[str, Any]]],
                      section_index: int, section_type: str):
        """ContentEngine copy for a pattern section (index-aligned, then
        type-aligned). Returns (heading, body)."""
        if not page_sections:
            return '', ''
        matched = None
        if section_index < len(page_sections):
            matched = page_sections[section_index]
        else:
            want = section_type.lower()
            for candidate in page_sections:
                if str(candidate.get('type', '')).lower() == want:
                    matched = candidate
                    break
        if not matched:
            return '', ''
        return (str(matched.get('semantic_heading', '')),
                str(matched.get('body', '')))

    @staticmethod
    def _client_api_capabilities(artifact) -> set:
        """Phase 47.36: the Project Capability Contract's Client-API
        bindable capabilities for this artifact (platform-owned, no LLM).
        Only capabilities with an existing Phase 47.35 Client API
        operation can produce a frontend binding."""
        capabilities = set(
            getattr(getattr(artifact, 'requirements', None),
                    'capabilities', None) or [])
        return capabilities & {'products', 'leads'}

    @staticmethod
    def _hero_subtitle(text: str, budget: int = 200) -> str:
        """Phase 47.39A: bounded subtitle preserving word/sentence boundary.

        The previous ``[:200]`` slice cut mid-word (5/5 proven — ``retent``
        etc.). This trims at the last sentence- or word-boundary within the
        budget; a single over-long word is hard-cut. Bounded, no new
        architecture.
        """
        if not text:
            return ''
        paragraph = str(text).split('\n\n')[0].strip()
        if len(paragraph) <= budget:
            return paragraph
        cut = paragraph[:budget].rstrip()
        # Prefer a sentence boundary (``. ``) nearest the end.
        last_sentence = cut.rfind('. ')
        if last_sentence >= max(40, budget - 90):
            return cut[:last_sentence + 1].rstrip()
        last_space = cut.rfind(' ')
        if last_space >= max(20, budget - 60):
            return cut[:last_space].rstrip()
        return cut

    @staticmethod
    def _hero_cta_label(artifact) -> str:
        """Phase 47.39A: CTA label is the brief's CTA when available.

        Previous ``services[0]`` heuristic produced a generic ``Get started``
        on all 5 sites, ignoring the briefs' real CTAs (``Reserve a table``,
        ``Shop collection`` …). The brief CTA is carried in branding. Bounded.
        """
        branding = getattr(getattr(artifact, 'requirements', None), 'branding', None) or {}
        brief_cta = str(branding.get('cta') or '').strip()
        if brief_cta:
            return brief_cta[:40]
        services = branding.get('services') or []
        if services:
            first_service = str(services[0]).lower()
            if 'design' in first_service or 'creative' in first_service:
                return 'View work'
            if 'consult' in first_service or 'advisor' in first_service:
                return 'Book a call'
            if 'develop' in first_service or 'build' in first_service:
                return 'Start project'
        return 'Get started'

    @staticmethod
    def _hero_cta_route(valid_routes, artifact=None) -> str:
        """Phase 47.39A: CTA destination prefers ``/contact``; without it,
        picks the most CTA-relevant non-home route (word overlap between CTA
        label and route name) so ``Reserve a table`` -> ``/reservations``
        and ``Shop collection`` -> ``/products`` instead of looping home.

        Deterministic, no second routing system.
        """
        routes = list(valid_routes or ['/'])
        if '/contact' in routes:
            return '/contact'
        branding = getattr(getattr(artifact, 'requirements', None), 'branding', None) or {} if artifact else {}
        cta_words = set(str(branding.get('cta') or '').lower().split())
        cta_route = None
        best_overlap = 0
        for route in routes:
            if route == '/':
                continue
            token = route.strip('/').lower()
            # token substring overlap (``reserve`` ~ ``reservations``)
            overlap = sum(1 for w in cta_words if w and (w in token or token in w))
            if overlap > best_overlap:
                best_overlap = overlap
                cta_route = route
        if cta_route:
            return cta_route
        for route in routes:
            if route != '/':
                return route
        return routes[0] if routes else '/'

    @staticmethod
    def _hero_badge(artifact) -> str:
        """Phase 47.29: deterministic Hero eyebrow from existing brief
        signals — the business category (or domain) cleaned to a short
        label. Bounded to 40 chars; empty when no signal exists (the
        native Hero hides the badge cleanly)."""
        req = getattr(artifact, 'requirements', None)
        if req is None:
            return ''
        branding = getattr(req, 'branding', None) or {}
        raw = (getattr(req, 'business_category', '')
               or branding.get('business_category')
               or getattr(req, 'domain', '') or '')
        label = str(raw).strip()
        if not label:
            return ''
        # Category phrases like "restaurant business" reduce to the
        # meaningful eyebrow ("Restaurant").
        words = [w for w in label.split() if w.strip()]
        while len(words) > 1 and words[-1].lower() in (
                'business', 'service', 'services', 'company', 'website'):
            words = words[:-1]
        label = ' '.join(words).strip(' -–—:')
        return label[:40]

    @staticmethod
    def _section_image(stock_images: Dict[str, Dict[str, str]],
                       section: str):
        """Phase 47.29: the stock image assigned to a specific section —
        the AssetEngine's per-section entry (stock_section_<type>) first,
        then the legacy shared 'stock_section' slot for compatibility.
        Returns the entry dict or None."""
        per_section = stock_images.get('stock_section_%s'
                                        % str(section or '').lower())
        return per_section or stock_images.get('stock_section')

    # ------------------------------------------------------------------
    # Phase 47.40: visual-direction consumption. ThemeEngine owns the
    # decision (generation_metadata['visual_direction']); these builders
    # apply it through bounded design-token variants. Every helper is a
    # pure function with a backward-compatible default, so artifacts
    # predating the contract keep the exact previous behavior.
    # ------------------------------------------------------------------

    _VD_AXIS_VALUES = {
        'density': ('compact', 'standard', 'airy'),
        'corner_style': ('sharp', 'soft', 'rounded'),
        'depth_level': ('flat', 'subtle', 'elevated'),
        'motion_level': ('none', 'subtle', 'standard', 'expressive'),
        'composition_style': ('editorial', 'centered', 'grid', 'immersive'),
        'hero_variant': ('split', 'centered', 'fullscreen'),
        'secondary_hero_variant': ('split', 'centered'),
    }

    @classmethod
    def _visual_direction(cls, artifact: WebsiteGenerationArtifact) -> Dict[str, Any]:
        """Validated visual direction from the artifact (ThemeEngine
        contract). Unknown/absent fields fall back to the previous
        universal behavior."""
        metadata = getattr(artifact, 'generation_metadata', None) or {}
        raw = dict(metadata.get('visual_direction') or {})
        vd = {'present': bool(raw)}
        for axis, allowed in cls._VD_AXIS_VALUES.items():
            value = str(raw.get(axis) or '').strip()
            vd[axis] = value if value in allowed else ''
        vd['effects'] = [str(e) for e in (raw.get('effects') or [])
                         if str(e) in ('SpotlightCard', 'StarBorder')][:2]
        return vd

    @classmethod
    def _hero_variant(cls, vd: Dict[str, Any], is_home: bool,
                      hero_path: Optional[str]) -> str:
        """Phase 47.40: deterministic hero-variant selection from the
        visual direction and page purpose — replacing the universal
        ``split iff image exists`` rule. Falls back to the legacy rule
        when no visual direction exists (backward compatibility)."""
        variant = vd.get('hero_variant' if is_home else 'secondary_hero_variant', '')
        if not variant:
            # Legacy behavior (no visual direction on the artifact).
            return 'split' if hero_path else 'centered'
        if not hero_path and variant in ('split', 'fullscreen'):
            # The split/fullscreen compositions are image-led; without
            # imagery the centered variant is the honest composition.
            return 'centered'
        return variant

    @staticmethod
    def _section_max_width(vd: Dict[str, Any], default: int) -> int:
        """Bounded section measure per composition style."""
        return {
            'editorial': 880, 'centered': 720, 'grid': 1080,
            'immersive': 1140,
        }.get(vd.get('composition_style', ''), default)

    @staticmethod
    def _card_min_width(vd: Dict[str, Any]) -> int:
        """Card-grid density: the auto-fit minmax floor."""
        return {'compact': 200, 'standard': 240, 'airy': 280}.get(
            vd.get('density', ''), 240)

    @staticmethod
    def _gallery_geometry(vd: Dict[str, Any]) -> str:
        """Gallery geometry family per composition style — bounded to the
        three implemented variants."""
        return {
            'immersive': 'masonry', 'editorial': 'feature',
            'grid': 'uniform', 'centered': 'uniform',
        }.get(vd.get('composition_style', ''), 'uniform')

    @staticmethod
    def _section_items(page_sections: Optional[List[Dict[str, Any]]],
                       section_index: int, section_type: str) -> List[Dict[str, str]]:
        """Phase 47.27 (ADR-0079): the canonical structured items for a
        pattern section (index-aligned, then type-aligned) — the
        ContentArtifact's optional `items` array."""
        if not page_sections:
            return []
        matched = None
        if section_index < len(page_sections):
            matched = page_sections[section_index]
        else:
            want = section_type.lower()
            for candidate in page_sections:
                if str(candidate.get('type', '')).lower() == want:
                    matched = candidate
                    break
        if not matched:
            return []
        items = matched.get('items')
        if not isinstance(items, list):
            return []
        return [i for i in items if isinstance(i, dict)]

    def _external_wrapper(self, selected_component: Optional[dict],
                          external_imports: Dict[str, str]):
        """Usage info for the external/native component matched to a pattern
        section: (main identifier, import line, card-family exports,
        organism flag, native flag)."""
        if not selected_component:
            return None
        metadata = selected_component.get('metadata') or {}
        comp_id = str(selected_component.get('component_id')
                      or metadata.get('source_identifier') or '')
        named, default = self._parse_module_exports(selected_component.get('code') or '')
        main = default or (named[0] if named else None)
        if not main or main not in external_imports:
            return None
        has_card_family = bool(
            ('%sHeader' % main) in external_imports
            and ('%sContent' % main) in external_imports
            and ('%sTitle' % main) in external_imports)
        return {
            'main': main,
            'import_line': external_imports[main],
            'is_default': bool(default),
            'card_family': has_card_family,
            'named': named,
            'source': comp_id,
            'is_native': metadata.get('source_provider') == 'native_library',
            'is_organism': bool(metadata.get('organism')),
            'organism_name': metadata.get('source_identifier') if metadata.get('organism') else None,
        }

    def _build_pattern_section(self, section: str, component_name: str,
                               artifact: WebsiteGenerationArtifact,
                               page_sections: Optional[List[Dict[str, Any]]],
                               section_index: int,
                               selected_component: Optional[dict],
                               external_imports: Dict[str, str],
                               stock_images: Dict[str, Dict[str, str]],
                               valid_routes: List[str],
                               available_effects=None,
                               page_path: str = ''):
        """Deterministic pattern-section builder (no LLM call). Returns
        (code, import lines) or None when the section has nothing
        materializable to render (e.g. Gallery without images)."""
        heading, body = self._section_copy(page_sections, section_index, section)
        wrapper = self._external_wrapper(selected_component, external_imports)
        imports: List[str] = []
        if wrapper:
            main = wrapper['main']
            is_native = bool(
                selected_component
                and (selected_component.get('metadata') or {}).get(
                    'source_provider') == 'native_library')
            if is_native:
                # Phase 47.25 (ADR-0077): native components import from the
                # provider-scaffold location â€” the line materialization
                # already registered against the existing workspace file.
                line = external_imports.get(main) or wrapper['import_line']
            else:
                module = self._external_module_name(wrapper['source'])
                ext = self._external_module_ext(
                    selected_component.get('code', '') if selected_component else '',
                    selected_component.get('metadata') if selected_component else {})
                if wrapper['card_family']:
                    wanted = [n for n in wrapper['named']
                              if n in (main, main + 'Header', main + 'Title',
                                       main + 'Content')]
                    line = "import { %s } from '../components/external/%s.%s'" % (
                        ', '.join(dict.fromkeys([main] + wanted)), module, ext)
                elif wrapper['is_default']:
                    line = "import %s from '../components/external/%s.%s'" % (main, module, ext)
                else:
                    line = "import { %s } from '../components/external/%s.%s'" % (
                        ', '.join(wrapper['named'][:4] or [main]), module, ext)
            imports.append(line)

        builder = getattr(self, '_pattern_%s' % section.lower(), None)
        if builder is None:
            return None
        # Phase 47.40: effects apply ONLY when the curated component
        # actually materialized (the plain composition is the
        # deterministic fallback — a missing candidate never breaks
        # generation). The mapping is {effect_name: import_line} using the
        # assembler's OWN registered lines — builders never fabricate
        # import paths. Callers may pass the resolved mapping explicitly
        # (testing/evidence); by default it derives from the materialized
        # external imports.
        if available_effects is None:
            available_effects = {
                e: external_imports[e]
                for e in self._visual_direction(artifact)['effects']
                if e in external_imports}
        result = builder(component_name, artifact, heading, body, wrapper,
                         stock_images, valid_routes, section_index,
                         page_sections, available_effects=available_effects,
                         page_path=page_path)
        if result is None:
            return None
        code, extra_imports = result
        imports.extend(extra_imports)
        return code, imports

    # -- individual pattern section builders (deterministic) ------------

    def _featuregrid_organism(self, component_name, heading, subtitle,
                              items, paragraphs, aria_label,
                              effect='', effect_import=''):
        """Phase 47.25 (ADR-0077): native FeatureGrid organism composition —
        declared data array + prop-driven render of the REAL component.

        Phase 47.40A: when a compatible allowlisted effect is selected AND
        materialized, the organism passes it as ``ItemWrapper`` to the
        native FeatureGrid so each Card renders inside the effect component.
        When no effect is selected the output is identical to the previous
        behavior (no ItemWrapper prop)."""
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  const features = [')
        for idx, item in enumerate(items):
            desc = paragraphs[idx + 1] if idx + 1 < len(paragraphs) else ''
            lines.append('    {')
            lines.append('      title: %s,' % self._js_string_literal(item))
            if desc:
                lines.append('      description: %s,' % self._js_string_literal(desc))
            lines.append('    },')
        lines.append('  ]')
        lines.append('  return (')
        lines.append('    <FeatureGrid data-nexora-source="native/FeatureGrid" '
                     'aria-label=%s' % self._jsx_text_literal(aria_label))
        lines.append('      title=%s' % self._jsx_text_literal(heading or 'Our Work'))
        if subtitle:
            lines.append('      subtitle=%s' % self._jsx_text_literal(subtitle))
        if effect:
            lines.append('      ItemWrapper={%s}' % effect)
        lines.append('      features={features} />')
        lines.append('  )')
        lines.append('}')
        extra_imports = [effect_import] if effect and effect_import else []
        return '\n'.join(lines) + '\n', extra_imports

    def _pattern_servicesgrid(self, component_name, artifact, heading, body,
                              wrapper, stock_images, valid_routes, section_index,
                              page_sections, available_effects=None, page_path=''):
        """available_effects (Phase 47.40): {effect_name: import_line} for
        the curated effects that actually materialized — the import lines
        are the assembler's own registrations, never builder-fabricated."""
        # Phase 47.39A (verified defect #4): prefer canonical ContentEngine
        # structured items — the LLM's real service descriptions — over the
        # static brief service names; only fall back to branding when no
        # items exist (the pre-existing binding discarded generated copy).
        structured_items = self._section_items(page_sections, section_index, 'ServicesGrid')
        if structured_items:
            services = [str(i.get('title') or i.get('name') or '').strip()
                        for i in structured_items[:6]]
            services = [s for s in services if s]
            paragraphs = [str(i.get('body') or i.get('description') or '').strip()
                          for i in structured_items[:6]]
        else:
            req = artifact.requirements
            branding = req.branding or {}
            services = [str(s) for s in (branding.get('services') or
                                         (req.goals or []))[:6] if str(s).strip()]
            if not services:
                services = ['Services', 'Approach', 'Process'][:3]
            paragraphs = [p.strip() for p in (body or '').split('\n\n') if p.strip()]
            if not paragraphs:
                paragraphs = ['']
            # For FeaturesGrid vs ServicesGrid offset: the heading sentence
            # lives in paragraphs[0]; item descriptions are paragraphs[1+].
            if len(paragraphs) == 1 and not paragraphs[0]:
                paragraphs = [''] + paragraphs

        # Phase 47.25 (ADR-0077): the native FeatureGrid organism composes
        # the whole section when it matched (it renders items as cards).
        if (wrapper and wrapper.get('is_native')
                and wrapper.get('main') == 'FeatureGrid'):
            # FeatureGrid organism's ``subtitle`` is the first body paragraph
            # (the section intro); descriptions are carried per item. When
            # items carry their own bodies, use the first body as subtitle
            # and remaining bodies as per-item descriptions.
            subtitle = paragraphs[0] if paragraphs else ''
            # If we came from structured items, paragraphs are exactly the
            # per-item bodies (no intro paragraph); use body as intro when
            # the section body has content and items lack bodies.
            if structured_items and not any(paragraphs):
                alt_paragraphs = [p.strip() for p in (body or '').split('\n\n') if p.strip()]
                if alt_paragraphs:
                    subtitle = alt_paragraphs[0]
                    # Keep one-paragraph intro style; per-item descriptions
                    # fall back to empty (rare degenerate artifact).
            # Phase 47.40A: resolve the canonical selected effect before
            # delegating to the native organism.
            effects = dict(available_effects or {})
            effect_import = effects.get('SpotlightCard', '')
            effect = 'SpotlightCard' if effect_import else ''
            return self._featuregrid_organism(
                component_name, heading, subtitle, services, paragraphs,
                'services grid', effect=effect, effect_import=effect_import)

        section_entry = self._section_image(stock_images, 'ServicesGrid')
        section_img = (section_entry or {}).get('path')
        vd = self._visual_direction(artifact)
        max_width = self._section_max_width(vd, 1080)
        card_min = self._card_min_width(vd)
        effects = dict(available_effects or {})
        effect_line = effects.get('SpotlightCard', '')
        effect = 'SpotlightCard' if effect_line else ''
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="services section" style={{ '
                      "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                      "background: 'var(--color-card, #ffffff)' }}>")
        lines.append("      <div style={{ maxWidth: %d, margin: '0 auto' }}>" % max_width)
        if heading:
            lines.append("        <h2 style={{ fontFamily: "
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, marginBottom: "
                         "'var(--spacing-md, 1rem)', color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        if section_img:
            alt = (section_entry or {}).get('alt', 'services')
            lines.append('        <img src="%s" alt="%s" style={{ width: '
                         % (section_img, str(alt).replace('"', ''))
                         + "'100%', maxWidth: 640, height: 'auto', borderRadius: "
                         "'var(--radius-md, 8px)', marginBottom: "
                         "'var(--spacing-lg, 2rem)' }} />")
        if paragraphs[0]:
            lines.append("        <p style={{ fontSize: 'var(--body, 1rem)', "
                         "lineHeight: 1.7, color: 'var(--color-secondary, #475569)', "
                         "marginBottom: 'var(--spacing-lg, 2rem)' }}>")
            lines.append('          ' + self._jsx_text_literal(paragraphs[0]))
            lines.append('        </p>')
        lines.append("        <div style={{ display: 'grid', "
                     "gridTemplateColumns: 'repeat(auto-fit, minmax(%dpx, 1fr))', "
                     "gap: 'var(--spacing-lg, 2rem)' }}>" % card_min)
        icons = ['Briefcase', 'Layers', 'Target', 'Compass', 'Lightbulb', 'Box']
        for idx, service in enumerate(services):
            desc = paragraphs[idx + 1] if idx + 1 < len(paragraphs) else ''
            icon = icons[idx % len(icons)]
            source_attr = str(wrapper['source']).replace('"', '') if wrapper else ''
            lines.extend(self._service_item_lines(wrapper, icon, service, desc,
                                                  source_attr, effect=effect))
        lines.append('        </div>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        icons_used = sorted({icons[i % len(icons)] for i in range(len(services))})
        lucide_import = "import { %s } from 'lucide-react'" % ', '.join(icons_used)
        imports = [lucide_import]
        if effect:
            imports.append(effect_line)
        return code, imports

    def _service_item_lines(self, wrapper, icon, service, desc, source_attr,
                            effect=''):
        """One service entry â€” composed inside the REAL external component
        when one matched (card family or single-component wrapper)."""
        item_style = ("border: '1px solid var(--color-border, #e2e8f0)', "
                      "borderRadius: 'var(--radius-lg, 12px)', "
                      "padding: 'var(--spacing-lg, 2rem)'")
        icon_line = ('            <%s size={22} aria-hidden="true" '
                     'style={{ color: ' % icon
                     + "'var(--color-primary, #3f5c76)', marginBottom: "
                     "'var(--spacing-sm, 0.5rem)' }} />")
        title_line = ("            <h3 style={{ fontFamily: "
                      "'var(--font-heading, Inter, sans-serif)', fontSize: "
                      "'1.125rem', fontWeight: 600, color: "
                      "'var(--color-text, #0f172a)' }}>")
        desc_style = ("fontSize: '0.9375rem', lineHeight: 1.6, color: "
                      "'var(--color-secondary, #475569)', marginTop: "
                      "'var(--spacing-xs, 0.25rem)'")

        if wrapper and wrapper.get('card_family'):
            main = wrapper['main']
            data_attr = ' data-nexora-source="%s"' % source_attr if source_attr else ''
            lines = [
                '          <%s%s style={{ %s }}>' % (main, data_attr, item_style),
                '            <%s>' % (main + 'Header'),
                '              <%s>' % (main + 'Title'),
                '                ' + self._jsx_text_literal(service),
                '              </%s>' % (main + 'Title'),
                '            </%s>' % (main + 'Header'),
                icon_line.replace('            ', '            '),
                '            <%s>' % (main + 'Content'),
            ]
            if desc:
                lines.append('              <p style={{ %s }}>' % desc_style)
                lines.append('                ' + self._jsx_text_literal(desc))
                lines.append('              </p>')
            lines.append('            </%s>' % (main + 'Content'))
            lines.append('          </%s>' % main)
            return lines

        if wrapper:
            main = wrapper['main']
            data_attr = ' data-nexora-source="%s"' % source_attr if source_attr else ''
            lines = [
                '          <%s%s style={{ %s }}>' % (main, data_attr, item_style),
                icon_line,
                title_line,
                '              ' + self._jsx_text_literal(service),
                '            </h3>',
            ]
            if desc:
                lines.append('            <p style={{ %s }}>' % desc_style)
                lines.append('              ' + self._jsx_text_literal(desc))
                lines.append('            </p>')
            lines.append('          </%s>' % main)
            return lines

        data_attr = ' data-nexora-source="determinant:servicesgrid"'
        # Phase 47.40: when the visual direction's effects budget selected
        # the curated zero-dependency SpotlightCard (and it materialized),
        # the plain fallback item composes inside it (children composition;
        # the assembler injects the fixed external import line).
        open_tag = ('          <%s style={{ %s }}>' % (effect, item_style)
                    if effect
                    else '          <div%s style={{ %s }}>' % (data_attr, item_style))
        close_tag = ('          </%s>' % effect if effect else '          </div>')
        lines = [
            open_tag,
            icon_line,
            title_line,
            '              ' + self._jsx_text_literal(service),
            '            </h3>',
        ]
        if desc:
            lines.append('            <p style={{ %s }}>' % desc_style)
            lines.append('              ' + self._jsx_text_literal(desc))
            lines.append('            </p>')
        lines.append(close_tag)
        return lines

    def _pattern_testimonial(self, component_name, artifact, heading, body,
                             wrapper, stock_images, valid_routes, section_index,
                             page_sections, available_effects=(), page_path=''):
        if not body:
            body = 'Trusted by clients who value considered work.'
        req = artifact.requirements
        attribution = (req.business_name
                       or (req.branding or {}).get('business_name') or '')

        # Phase 47.25 (ADR-0077): the native Testimonial organism composes
        # directly with props when it matched this section.
        if wrapper and wrapper.get('is_native') and wrapper.get('main') == 'Testimonial':
            lines = []
            lines.append('function %s() {' % component_name)
            lines.append('  return (')
            lines.append('    <section aria-label="testimonial section" style={{ '
                         "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                         "background: 'var(--color-background, #f8fafc)' }}>")
            lines.append('      <div style={{ maxWidth: 640, margin: \'0 auto\' }}>')
            data_attr = ' data-nexora-source="native/Testimonial"'
            lines.append('        <Testimonial%s quote=%s author=%s%s />' % (
                data_attr,
                self._jsx_text_literal(body),
                self._jsx_text_literal(attribution or 'Client'),
                (' role=%s' % self._jsx_text_literal(heading))
                if heading else ''))
            lines.append('      </div>')
            lines.append('    </section>')
            lines.append('  )')
            lines.append('}')
            code = '\n'.join(lines) + '\n'
            # Quote/Star icons fall away â€” the organism carries the visual.
            return code, []

        lines = []
        vd = self._visual_direction(artifact)
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="testimonial section" style={{ '
                     "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                     "background: 'var(--color-background, #f8fafc)' }}>")
        lines.append("      <div style={{ maxWidth: %d, margin: '0 auto', "
                     "textAlign: 'center' }}>"
                     % self._section_max_width(vd, 820))
        lines.append('        <Quote size={28} aria-hidden="true" style={{ color: '
                     "'var(--color-primary, #3f5c76)', margin: "
                     "'0 auto var(--spacing-md, 1rem)' }} />")
        if heading:
            lines.append('        <h2 style={{ fontFamily: '
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, color: "
                         "'var(--color-text, #0f172a)', marginBottom: "
                         "'var(--spacing-md, 1rem)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        lines.append('        <blockquote style={{ fontSize: '
                     "'1.125rem', lineHeight: 1.7, color: "
                     "'var(--color-text, #0f172a)', fontStyle: 'italic' }}>")
        lines.append('          ' + self._jsx_text_literal(body))
        lines.append('        </blockquote>')
        if attribution:
            lines.append('        <p style={{ marginTop: '
                         "'var(--spacing-md, 1rem)', fontSize: "
                         "'0.875rem', letterSpacing: '0.04em', color: "
                         "'var(--color-secondary, #475569)' }}>")
            lines.append('          ' + self._jsx_text_literal(attribution))
            lines.append('        </p>')
        lines.append('        <div style={{ display: \'flex\', gap: '
                     "'var(--spacing-xs, 0.25rem)', justifyContent: 'center', "
                     "marginTop: 'var(--spacing-sm, 0.5rem)' }}>")
        for star in range(5):
            lines.append('          <Star size={16} aria-hidden="true" style={{ '
                         "fill: 'var(--color-primary, #3f5c76)', color: "
                         "'var(--color-primary, #3f5c76)' }} />")
        lines.append('        </div>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, ["import { Quote, Star } from 'lucide-react'"]

    def _pattern_contactcta(self, component_name, artifact, heading, body,
                            wrapper, stock_images, valid_routes, section_index,
                            page_sections, available_effects=None, page_path=''):
        req = artifact.requirements
        branding = req.branding or {}
        business = (req.business_name or branding.get('business_name') or '')
        location = req.location or branding.get('location', '')
        contact_route = self._hero_cta_route(valid_routes, artifact)
        label = self._hero_cta_label(artifact)
        # Phase 47.40: section measure from the visual direction; the
        # curated StarBorder effect (zero dependencies) may wrap the
        # fallback CTA anchor for expressive directions — only when it
        # actually materialized (the import line is the assembler's own
        # registration).
        vd = self._visual_direction(artifact)
        star_line = dict(available_effects or {}).get('StarBorder', '')
        star_border = bool(star_line)
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="contact section" style={{ '
                      "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                      "background: 'var(--color-primary, #3f5c76)' }}>")
        lines.append("      <div style={{ maxWidth: %d, margin: '0 auto', "
                     "textAlign: 'center', color: "
                     "'var(--color-primary-foreground, #ffffff)' }}>"
                     % self._section_max_width(vd, 820))
        if heading:
            lines.append('        <h2 style={{ fontFamily: '
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, marginBottom: "
                         "'var(--spacing-md, 1rem)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        if body:
            lines.append('        <p style={{ fontSize: ' + "'1.0625rem'"
                         + ', lineHeight: 1.7, opacity: 0.92, marginBottom: '
                         + "'var(--spacing-lg, 2rem)' }}>")
            lines.append('          ' + self._jsx_text_literal(body))
            lines.append('        </p>')
        lines.append('        <div style={{ display: \'flex\', '
                     'flexDirection: \'column\', gap: '
                     "'var(--spacing-sm, 0.5rem)', alignItems: 'center', "
                     "marginBottom: 'var(--spacing-lg, 2rem)', fontSize: "
                     "'0.9375rem' }}>")
        if location:
            lines.append('          <span style={{ display: \'inline-flex\', '
                         'alignItems: \'center\', gap: '
                         "'var(--spacing-xs, 0.25rem)' }}>")
            lines.append('            <MapPin size={16} aria-hidden="true" />')
            lines.append('            ' + self._jsx_text_literal(location))
            lines.append('          </span>')
        if business:
            lines.append('          <span style={{ display: \'inline-flex\', '
                         'alignItems: \'center\', gap: '
                         "'var(--spacing-xs, 0.25rem)' }}>")
            lines.append('            <Building2 size={16} aria-hidden="true" />')
            lines.append('            ' + self._jsx_text_literal(business))
            lines.append('          </span>')
        lines.append('        </div>')
        # Phase 47.25 (ADR-0077): the native Button component composes the
        # CTA when it matched this section.
        if (wrapper and wrapper.get('is_native')
                and wrapper.get('main') == 'Button'):
            lines.append('        <Button data-nexora-source="native/Button" '
                         'href="%s" variant="primary" size="lg" '
                         'style={{ display: \'inline-flex\', alignItems: '
                         '\'center\', gap: \'var(--spacing-xs, 0.25rem)\' }}>'
                         % contact_route)
            lines.append('          ' + self._jsx_text_literal(label))
            lines.append('          <ArrowRight size={18} aria-hidden="true" />')
            lines.append('        </Button>')
        else:
            if star_border:
                # Phase 47.40: expressive directions wrap the fallback CTA
                # in the curated zero-dependency StarBorder (children
                # composition; assembler-owned fixed import).
                lines.append('        <StarBorder as="a" href="%s" '
                             'data-nexora-source="react_bits/StarBorder" '
                             'color="var(--color-accent, #b45309)" '
                             'speed="8s" '
                             'backgroundColor='
                             '"var(--color-primary-foreground, #ffffff)" '
                             'textColor="var(--color-primary, #3f5c76)" '
                             'borderColor="transparent" '
                             'style={{ display: \'inline-flex\' }}>'
                             % contact_route)
                lines.append('          ' + self._jsx_text_literal(label))
                lines.append('          <ArrowRight size={18} aria-hidden="true" />')
                lines.append('        </StarBorder>')
            else:
                lines.append('        <a href="%s" style={{ display: ' % contact_route
                             + "'inline-flex', alignItems: 'center', gap: "
                             "'var(--spacing-xs, 0.25rem)', padding: "
                             "'0.75rem 1.5rem', borderRadius: "
                             "'var(--radius-md, 8px)', background: "
                             "'var(--color-primary-foreground, #ffffff)', color: "
                             "'var(--color-primary, #3f5c76)', fontWeight: 600, "
                             "textDecoration: 'none' }}>")
                lines.append('          ' + self._jsx_text_literal(label))
                lines.append('          <ArrowRight size={18} aria-hidden="true" />')
                lines.append('        </a>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        imports = ["import { MapPin, Building2, ArrowRight } from 'lucide-react'"]
        if star_border:
            imports.append(star_line)
        return code, imports

    def _pattern_contactform(self, component_name, artifact, heading, body,
                             wrapper, stock_images, valid_routes, section_index,
                             page_sections, available_effects=(), page_path=''):
        """Phase 47.36 (leads capability): lead capture bound to the Client
        API — composes the native ContactForm organism with the real
        submit mode (onSubmitLead) wired to the ONE canonical clientApi
        module (POST /api/v1/client/leads).

        Contract:
          * only the allowlisted lead fields (name, email, message) are
            submitted — the payload is narrower than the internal Odoo
            schema and contains no model/method/db selector
          * the native ContactForm owns validation UX, duplicate-submit
            protection, and sanitized error states; server-side
            validation and authorization remain authoritative
          * same-origin relative request; no credential in browser code
        Only ArchitectureEngine injects this section (contact page of a
        lead-capable project) — it never appears for static projects. A
        section named ContactForm without the leads capability is
        truthfully skipped (Gallery precedent), never silently rendered.
        """
        if 'leads' not in self._client_api_capabilities(artifact):
            return None
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  const submitLead = clientApi.createLead;')
        lines.append('  return (')
        lines.append('    <ContactForm data-nexora-source="native/ContactForm"')
        if heading:
            lines.append('      title=%s' % self._jsx_text_literal(heading))
        lines.append('      onSubmitLead={submitLead} />')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, [
            "import ContactForm from '../components/ContactForm.jsx'",
            "import { clientApi } from '../lib/clientApi.js'",
        ]

    # ------------------------------------------------------------------
    # Phase 47.26 (ADR-0078) builders: deterministic secondary hero
    # (native Hero organism) + Pricing / FAQ sections (native organisms,
    # hybrid copy parsed from the ContentEngine artifact).
    # ------------------------------------------------------------------

    def _build_secondary_hero(self, section, component_name, page_sections,
                              section_index, hero_display, valid_routes,
                              runtime, artifact=None):
        """Deterministic secondary-page hero composing the native Hero
        organism (guaranteed scaffold file; assembler-owned fixed import —
        the SiteLayout precedent). Returns (code, imports, mode)."""
        heading, body = self._section_copy(page_sections, section_index, section)
        if not heading:
            heading = str(section)
        if not body:
            body = ''

        native_hero_available = True
        try:
            native_hero_available = runtime.workspace.exists(
                'src/components/Hero.jsx')
        except Exception:
            native_hero_available = False

        hero_path = (hero_display or {}).get('path')
        hero_alt = (hero_display or {}).get('alt', 'hero visual')
        cta_route = self._hero_cta_route(valid_routes, artifact)
        cta_label = self._hero_cta_label(artifact)

        # Phase 47.29: deterministic badge/eyebrow from brief data (the
        # business category or domain — real client signals, never
        # invented). Phase 47.40: the layout variant comes from the
        # ThemeEngine visual direction (composition style + page
        # purpose) — no longer the universal split-iff-image rule.
        hero_badge = self._hero_badge(artifact)
        hero_variant = self._hero_variant(
            self._visual_direction(artifact), is_home=False, hero_path=hero_path)

        if native_hero_available:
            lines = []
            lines.append('function %s() {' % component_name)
            lines.append('  return (')
            props = [
                'data-nexora-source="native/Hero"',
                'variant="%s"' % hero_variant,
                'title=%s' % self._jsx_text_literal(heading),
            ]
            if hero_badge:
                props.append('badge=%s' % self._jsx_text_literal(hero_badge))
            if body:
                subtitle = self._hero_subtitle(body, 200)
                props.append('subtitle=%s' % self._jsx_text_literal(subtitle))
            if hero_path:
                props.append('image={{ src: "%s", alt: "%s" }}'
                             % (hero_path, str(hero_alt).replace('"', '')))
            props.append('cta={{ label: %s, href: "%s" }}'
                         % (self._js_string_literal(cta_label), cta_route))
            lines.append('    <Hero')
            for prop in props:
                lines.append('      %s' % prop)
            lines.append('    />')
            lines.append('  )')
            lines.append('}')
            code = '\n'.join(lines) + '\n'
            return (code, ["import Hero from '../components/Hero.jsx'"],
                    'deterministic')

        # Fallback: themed deterministic hero (native file unexpectedly
        # absent — e.g. a future non-react renderer).
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="%s hero" style={{ '
                     % str(section).lower())
        lines.append("      padding: 'var(--spacing-xl, 4rem) "
                     "var(--spacing-md, 1rem)', ")
        lines.append("      background: 'var(--color-card, #ffffff)' }}>")
        lines.append("      <div style={{ maxWidth: 880, margin: '0 auto' }}>")
        if hero_path:
            lines.append('        <img src="%s" alt="%s" style={{ width: '
                         % (hero_path, str(hero_alt).replace('"', ''))
                         + "'100%', maxWidth: 480, height: 'auto', "
                         "borderRadius: 'var(--radius-md, 8px)', marginBottom: "
                         "'var(--spacing-lg, 2rem)' }} />")
        lines.append("        <h1 style={{ fontFamily: "
                     "'var(--font-heading, Inter, sans-serif)', fontSize: "
                     "'var(--h1, 2.25rem)', fontWeight: 600, color: "
                     "'var(--color-text, #0f172a)' }}>")
        lines.append('          ' + self._jsx_text_literal(heading))
        lines.append('        </h1>')
        if body:
            lines.append("        <p style={{ fontSize: 'var(--body, 1rem)', "
                         "lineHeight: 1.7, color: "
                         "'var(--color-secondary, #475569)', marginTop: "
                         "'var(--spacing-md, 1rem)' }}>")
            lines.append('          ' + self._jsx_text_literal(body[:400]))
            lines.append('        </p>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, [], 'deterministic'

    def _build_deterministic_home_hero(self, component_name: str,
                                       artifact: WebsiteGenerationArtifact,
                                       page_sections: List[Dict[str, Any]],
                                       hero_display: Optional[Dict[str, Any]],
                                       valid_routes: List[str],
                                       runtime: 'GenerationRuntime'):
        """Phase 47.28: Deterministic home Hero candidate using ONLY
        platform-owned data — ContentArtifact copy, AssetEngine imagery,
        ThemeEngine tokens, native Hero organism, native Button.

        This is the evidence-gated alternative to the LLM-generated home Hero.
        Returns (code, imports, mode) like _build_secondary_hero."""
        # Home page is always index 0, section 0
        heading, body = self._section_copy(page_sections, 0, 'Hero')
        if not heading:
            req = artifact.requirements
            business = (req.business_name
                        or (req.branding or {}).get('business_name')
                        or req.domain or 'Welcome')
            heading = business
        if not body:
            body = ''

        native_hero_available = True
        try:
            native_hero_available = runtime.workspace.exists(
                'src/components/Hero.jsx')
        except Exception:
            native_hero_available = False

        hero_path = (hero_display or {}).get('path')
        hero_alt = (hero_display or {}).get('alt', 'hero visual')
        cta_route = self._hero_cta_route(valid_routes, artifact)
        cta_label = self._hero_cta_label(artifact)

        # Phase 47.29: deterministic badge/eyebrow from brief data (the
        # business category or domain — real client signals, never
        # invented), and Phase 47.40: a layout variant driven by the
        # ThemeEngine visual direction (composition style) and the home
        # page purpose — no longer merely whether an image exists.
        hero_badge = self._hero_badge(artifact)
        hero_variant = self._hero_variant(
            self._visual_direction(artifact), is_home=True, hero_path=hero_path)

        if native_hero_available:
            lines = []
            lines.append('function %s() {' % component_name)
            lines.append('  return (')
            props = [
                'data-nexora-source="native/Hero"',
                'variant="%s"' % hero_variant,
                'title=%s' % self._jsx_text_literal(heading),
            ]
            if hero_badge:
                props.append('badge=%s' % self._jsx_text_literal(hero_badge))
            if body:
                subtitle = self._hero_subtitle(body, 200)
                props.append('subtitle=%s' % self._jsx_text_literal(subtitle))
            if hero_path:
                props.append('image={{ src: "%s", alt: "%s" }}'
                             % (hero_path, str(hero_alt).replace('"', '')))
            props.append('cta={{ label: %s, href: "%s" }}'
                         % (self._js_string_literal(cta_label), cta_route))
            # Note: secondaryCta not passed to avoid React warning on DOM element
            # (native Hero accesses it via props.secondaryCta but spread passes to section)
            lines.append('    <Hero')
            for prop in props:
                lines.append('      %s' % prop)
            lines.append('    />')
            lines.append('  )')
            lines.append('}')
            code = '\n'.join(lines) + '\n'
            return (code, ["import Hero from '../components/Hero.jsx'"],
                    'deterministic')

        # Fallback: themed deterministic hero (centered variant, no image)
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="home hero" style={{ ')
        lines.append("      padding: 'var(--spacing-2xl, 6rem) 0', ")
        lines.append("      minHeight: '70vh', ")
        lines.append("      display: 'flex', alignItems: 'center', ")
        lines.append("      justifyContent: 'center', textAlign: 'center', ")
        lines.append("      background: 'var(--color-background, #f8fafc)' }}>")
        lines.append("      <div className='container' style={{ maxWidth: 800, padding: '0 var(--spacing-md, 1rem)' }}>")
        if hero_path:
            lines.append('        <img src="%s" alt="%s" style={{ width: '
                         % (hero_path, str(hero_alt).replace('"', ''))
                         + "'100%', maxWidth: 600, height: 'auto', "
                         "borderRadius: 'var(--radius-lg, 12px)', marginBottom: "
                         "'var(--spacing-xl, 3rem)' }} />")
        lines.append("        <h1 style={{ fontFamily: ")
        lines.append("          'var(--font-heading, Georgia, serif)', ")
        lines.append("          fontSize: 'calc(2.5rem + 2vw)', fontWeight: 800, ")
        lines.append("          lineHeight: 1.15, marginBottom: ")
        lines.append("          'var(--spacing-lg, 2rem)', color: ")
        lines.append("          'var(--color-text, #0f172a)' }}>")
        lines.append('          ' + self._jsx_text_literal(heading))
        lines.append('        </h1>')
        if body:
            lines.append("        <p style={{ fontSize: '1.25rem', ")
            lines.append("          color: 'var(--color-secondary, #475569)', ")
            lines.append("          lineHeight: 1.6, marginBottom: ")
            lines.append("          'var(--spacing-xl, 3rem)', maxWidth: 640, ")
            lines.append("          marginLeft: 'auto', marginRight: 'auto' }}>")
            lines.append('          ' + self._jsx_text_literal(body[:400]))
            lines.append('        </p>')
        lines.append("        <div style={{ display: 'flex', gap: '1rem', ")
        lines.append("          justifyContent: 'center', flexWrap: 'wrap' }}>")
        lines.append('          <Button data-nexora-source="native/Button" '
                     'href="%s" variant="primary" size="lg">' % cta_route)
        lines.append('            ' + self._jsx_text_literal(cta_label))
        lines.append('          </Button>')
        lines.append('          <Button data-nexora-source="native/Button" '
                     'href="%s" variant="outline" size="lg">' % cta_route)
        lines.append('            ' + self._jsx_text_literal('Learn more'))
        lines.append('          </Button>')
        lines.append('        </div>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        imports = [
            "import Button from '../components/Button.jsx'",
        ]
        if hero_path:
            # No Hero import needed for fallback
            pass
        return code, imports, 'deterministic'

    @staticmethod
    def _parse_plan_blocks(body: str) -> List[Dict[str, str]]:
        """Parse 'Plan name — price' blocks (blank-line separated) from the
        ContentEngine pricing copy. First line: 'Name — price'; following
        lines: features. A block only counts as a plan when it carries a
        name/price separator — unstructured prose falls back. Bounded,
        order-preserving."""
        plans = []
        for block in (body or '').split('\n\n'):
            block = block.strip()
            if not block:
                continue
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
            first = lines[0]
            name, price, found = first, '', False
            for sep in (' — ', ' - ', ' – ', ': '):
                if sep in first:
                    name, _, price = first.partition(sep)
                    name, price = name.strip(), price.strip()
                    found = True
                    break
            if not found:
                continue
            features = [l for l in lines[1:]][:6]
            plans.append({'title': name[:40] or 'Plan',
                          'price': price[:24], 'features': features})
            if len(plans) >= 3:
                break
        return plans

    @staticmethod
    def _parse_faq_blocks(body: str) -> List[Dict[str, str]]:
        """Parse Q&A blocks (blank-line separated) from the ContentEngine
        FAQ copy: first line = question (ideally ending in '?'), remaining
        lines = answer. Bounded, order-preserving."""
        faqs = []
        for block in (body or '').split('\n\n'):
            block = block.strip()
            if not block:
                continue
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
            question = lines[0].rstrip('?').strip()
            answer = ' '.join(lines[1:])[:400]
            faqs.append({'question': question[:120], 'answer': answer})
            if len(faqs) >= 5:
                break
        return faqs

    @staticmethod
    def _parse_menu_blocks(body: str) -> List[Dict[str, str]]:
        """Phase 47.29: parse "Item name - price" menu blocks (blank-line
        separated, price-like right side required) from the ContentEngine
        menu copy — the same grammar the prompt instructs for models that
        omit structured items. First line: 'Name - price'; following
        lines: description. Bounded, order-preserving; returns [] when the
        body does not follow the priced-block grammar."""
        items = []
        for block in (body or '').split('\n\n'):
            block = block.strip()
            if not block:
                continue
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
            first = lines[0]
            name, price, found = first, '', False
            for sep in (' — ', ' - ', ' – ', ': '):
                if sep in first:
                    name, _, price = first.partition(sep)
                    name, price = name.strip(), price.strip()
                    found = True
                    break
            if not found or not name:
                continue
            if not re.search(r'[$€£¥₹]|\d', price or ''):
                continue
            description = ' '.join(lines[1:])[:200]
            items.append({'title': name[:60], 'price': price[:24],
                          'body': description})
            if len(items) >= 6:
                break
        return items

    def _pattern_pricing(self, component_name, artifact, heading, body,
                         wrapper, stock_images, valid_routes, section_index,
                         page_sections, available_effects=(), page_path=''):
        """SaaS pricing section — composes the native PricingCard organisms
        from the ContentArtifact's STRUCTURED items (canonical — ADR-0079)
        with the prose plan-block parsing as the bounded fallback."""
        contact_route = '/contact' if '/contact' in (valid_routes or []) else \
            ((valid_routes or ['/'])[0])

        # Phase 47.27 (ADR-0079): structured items are the canonical path;
        # prose parsing remains the fallback for models that omit items.
        plans = []
        items = self._section_items(page_sections, section_index, 'Pricing')
        for item in items[:3]:
            title = str(item.get('title') or '').strip()
            price = str(item.get('price') or '').strip()
            features_text = str(item.get('body') or '').strip()
            features = [f.strip() for f in
                        features_text.replace(';', '\n').split('\n')
                        if f.strip()][:6]
            if title:
                plans.append({'title': title[:40], 'price': price[:24],
                              'features': features})
        if not plans:
            plans = self._parse_plan_blocks(body)

        # The native PricingCard is a scaffold file (guaranteed by the
        # provider scaffold); compose the organisms when plans parsed.
        if plans:
            vd = self._visual_direction(artifact)
            lines = []
            lines.append('function %s() {' % component_name)
            lines.append('  const plans = [')
            for idx, plan in enumerate(plans):
                lines.append('    {')
                lines.append('      title: %s,' % self._js_string_literal(plan['title']))
                lines.append('      price: %s,' % self._js_string_literal(plan['price'] or 'Custom'))
                lines.append('      isPopular: %s,' % ('true' if idx == 1 and len(plans) > 1 else 'false'))
                lines.append('      features: [')
                for feat in plan['features']:
                    lines.append('        %s,' % self._js_string_literal(feat))
                lines.append('      ],')
                lines.append('    },')
            lines.append('  ]')
            lines.append('  return (')
            lines.append('    <section aria-label="pricing section" style={{ '
                          "padding: 'var(--spacing-xl, 4rem) "
                          "var(--spacing-md, 1rem)', "
                          "background: 'var(--color-card, #ffffff)' }}>")
            lines.append("      <div style={{ maxWidth: %d, margin: '0 auto' }}>"
                         % self._section_max_width(vd, 1080))
            if heading:
                lines.append("        <h2 style={{ fontFamily: "
                             "'var(--font-heading, Inter, sans-serif)', "
                             "fontSize: 'var(--h2, 1.875rem)', fontWeight: 600, "
                             "marginBottom: 'var(--spacing-lg, 2rem)', color: "
                             "'var(--color-text, #0f172a)' }}>")
                lines.append('          ' + self._jsx_text_literal(heading))
                lines.append('        </h2>')
            lines.append("        <div style={{ display: 'flex', flexWrap: "
                         "'wrap', gap: 'var(--spacing-lg, 2rem)', "
                         "justifyContent: 'center' }}>")
            lines.append('          {plans.map(function(plan, idx) { return (')
            lines.append('            <PricingCard')
            lines.append('              key={idx}')
            lines.append('              data-nexora-source="native/PricingCard"')
            lines.append('              title={plan.title}')
            lines.append('              price={plan.price}')
            lines.append('              isPopular={plan.isPopular}')
            lines.append('              features={plan.features}')
            lines.append('              cta={{ label: \'Choose plan\', href: '
                         '\'%s\' }}' % contact_route)
            lines.append('            />')
            lines.append('          ) })}')
            lines.append('        </div>')
            lines.append('      </div>')
            lines.append('    </section>')
            lines.append('  )')
            lines.append('}')
            code = '\n'.join(lines) + '\n'
            return code, ["import PricingCard from '../components/PricingCard.jsx'"]

        # Fallback: themed pricing list from the raw body.
        if not body:
            return None
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="pricing section" style={{ '
                     "padding: 'var(--spacing-xl, 4rem) "
                     "var(--spacing-md, 1rem)' }}>")
        lines.append("      <div style={{ maxWidth: 720, margin: '0 auto' }}>")
        if heading:
            lines.append("        <h2 style={{ fontFamily: "
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, marginBottom: "
                         "'var(--spacing-md, 1rem)', color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        lines.append("        <p style={{ fontSize: 'var(--body, 1rem)', "
                     "lineHeight: 1.7, color: "
                     "'var(--color-secondary, #475569)' }}>")
        lines.append('          ' + self._jsx_text_literal(body))
        lines.append('        </p>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        return '\n'.join(lines) + '\n', []

    def _pattern_faq(self, component_name, artifact, heading, body,
                     wrapper, stock_images, valid_routes, section_index,
                     page_sections, available_effects=(), page_path=''):
        """FAQ section — composes the native FAQ organism from the
        ContentArtifact's STRUCTURED items (canonical — ADR-0079) with the
        prose Q&A-block parsing as the bounded fallback."""
        faqs = []
        items = self._section_items(page_sections, section_index, 'FAQ')
        for item in items[:5]:
            question = str(item.get('question') or item.get('title') or '').strip()
            answer = str(item.get('answer') or item.get('body') or '').strip()
            if question:
                faqs.append({'question': question[:120], 'answer': answer[:400]})
        if not faqs:
            faqs = self._parse_faq_blocks(body)
        if not faqs:
            if not body:
                return None
            faqs = [{'question': heading or 'Questions',
                     'answer': body[:400]}]

        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  const faqs = [')
        for faq in faqs:
            lines.append('    {')
            lines.append('      question: %s,' % self._js_string_literal(faq['question']))
            lines.append('      answer: %s,' % self._js_string_literal(faq['answer']))
            lines.append('    },')
        lines.append('  ]')
        lines.append('  return (')
        lines.append('    <FAQ data-nexora-source="native/FAQ"')
        lines.append('      title=%s' % self._jsx_text_literal(heading or 'Frequently Asked Questions'))
        lines.append('      items={faqs} />')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, ["import FAQ from '../components/FAQ.jsx'"]

    # ------------------------------------------------------------------
    # Phase 47.25 (ADR-0077) pattern sections: About / FeatureGrid /
    # MenuHighlights — domain-appropriate composition reusing the existing
    # builders' vocabulary and the matched native/external components.
    # ------------------------------------------------------------------

    def _pattern_content(self, component_name, artifact, heading, body,
                         wrapper, stock_images, valid_routes, section_index,
                         page_sections, available_effects=(), page_path=''):
        """Phase 47.27 (ADR-0079): deterministic Content section — the
        ContentArtifact already carries the full copy (verified by the
        runtime probe: the LLM call was only converting known copy into
        predictable titled-card JSX). Renders heading + copy blocks as
        themed cards; blocks come from the structured items when present,
        else from title-line + paragraph parsing of the body (the same
        shape the ContentEngine reliably produces)."""
        if not heading and not body:
            return None

        # Structured items (canonical) take precedence; else parse blocks.
        items = self._section_items(page_sections, section_index, 'Content')
        blocks = []
        if items:
            for item in items[:6]:
                title = str(item.get('title') or item.get('question') or '').strip()
                text = str(item.get('body') or item.get('answer') or '').strip()
                if title or text:
                    blocks.append((title, text))
        if not blocks and body:
            for block in body.split('\n\n'):
                block = block.strip()
                if not block:
                    continue
                block_lines = [l.strip() for l in block.split('\n') if l.strip()]
                if not block_lines:
                    continue
                if len(block_lines) == 1:
                    # A single-line block: a standalone paragraph.
                    blocks.append(('', block_lines[0]))
                else:
                    # Title line + paragraph body (the ContentEngine's
                    # reliable structure for service/detail sections).
                    blocks.append((block_lines[0][:80],
                                   ' '.join(block_lines[1:])[:2000]))

        section_entry = self._section_image(stock_images, 'Content')
        section_img = (section_entry or {}).get('path')
        contact_route = '/contact' if '/contact' in (valid_routes or []) else \
            ((valid_routes or ['/'])[0])

        lines = []
        vd = self._visual_direction(artifact)
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="content section" style={{ '
                      "padding: 'var(--spacing-xl, 4rem) "
                      "var(--spacing-md, 1rem)' }}>")
        lines.append("      <div style={{ maxWidth: %d, margin: '0 auto' }}>"
                     % self._section_max_width(vd, 880))
        if heading:
            lines.append("        <h2 style={{ fontFamily: "
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, marginBottom: "
                         "'var(--spacing-lg, 2rem)', color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        if section_img:
            alt = (section_entry or {}).get('alt', 'content')
            lines.append('        <img src="%s" alt="%s" style={{ width: '
                         % (section_img, str(alt).replace('"', ''))
                         + "'100%', maxWidth: 640, height: 'auto', borderRadius: "
                         "'var(--radius-md, 8px)', marginBottom: "
                         "'var(--spacing-lg, 2rem)' }} />")
        lines.append("        <div style={{ display: 'grid', gap: "
                     "'var(--spacing-lg, 2rem)' }}>")
        for block_title, block_body in blocks[:6]:
            lines.append('          <article style={{ background: '
                         "'var(--color-card, #ffffff)', border: "
                         "'1px solid var(--color-border, #e2e8f0)', borderRadius: "
                         "'var(--radius-lg, 12px)', padding: "
                         "'var(--spacing-lg, 2rem)' }}>")
            if block_title:
                lines.append("            <h3 style={{ fontFamily: "
                             "'var(--font-heading, Inter, sans-serif)', "
                             "fontSize: '1.25rem', fontWeight: 600, color: "
                             "'var(--color-primary, #3f5c76)', marginBottom: "
                             "'var(--spacing-sm, 0.5rem)' }}>")
                lines.append('              ' + self._jsx_text_literal(block_title))
                lines.append('            </h3>')
            if block_body:
                lines.append("            <p style={{ fontSize: "
                             "'var(--body, 1rem)', lineHeight: 1.7, color: "
                             "'var(--color-secondary, #475569)', margin: 0 }}>")
                lines.append('              ' + self._jsx_text_literal(block_body))
                lines.append('            </p>')
            lines.append('          </article>')
        if not blocks and body:
            # Unparseable body: render it as one honest paragraph.
            lines.append("          <p style={{ fontSize: 'var(--body, 1rem)', "
                         "lineHeight: 1.7, color: "
                         "'var(--color-secondary, #475569)' }}>")
            lines.append('            ' + self._jsx_text_literal(body[:2000]))
            lines.append('          </p>')
        lines.append("        </div>")
        if valid_routes and len(valid_routes) > 1:
            lines.append("        <nav aria-label=\"Section navigation\" style={{ "
                         "marginTop: 'var(--spacing-lg, 2rem)', display: 'flex', "
                         "flexWrap: 'wrap', gap: 'var(--spacing-md, 1rem)' }}>")
            for route in valid_routes[:4]:
                label = self._route_label(route)
                lines.append('          <a href="%s" style={{ color: '
                             "'var(--color-primary, #3f5c76)', textDecoration: "
                             "'none', fontSize: '0.875rem' }}>%s</a>"
                             % (route, label))
            lines.append('        </nav>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        return '\n'.join(lines) + '\n', []

    def _pattern_about(self, component_name, artifact, heading, body,
                       wrapper, stock_images, valid_routes, section_index,
                       page_sections, available_effects=(), page_path=''):
        if not heading and not body:
            return None
        req = artifact.requirements
        business = (req.business_name or (req.branding or {}).get('business_name')
                    or req.domain or 'Our story')
        section_entry = self._section_image(stock_images, 'About')
        section_img = (section_entry or {}).get('path')
        # Phase 47.40: composition variant from the visual direction —
        # editorial/immersive directions get the asymmetric offset
        # composition (text column + offset image), everything else keeps
        # the stacked composition. Bounded to the two implemented forms.
        vd = self._visual_direction(artifact)
        offset = (vd.get('composition_style') in ('editorial', 'immersive')
                  and bool(section_img) and bool(heading))
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="about section" style={{ '
                      "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)' }}>")
        if offset:
            lines.append("      <div style={{ maxWidth: %d, margin: '0 auto', "
                         "display: 'flex', flexWrap: 'wrap', alignItems: "
                         "'center', gap: 'var(--spacing-xl, 4rem)' }}>"
                         % self._section_max_width(vd, 880))
            lines.append("        <div style={{ flex: '1 1 320px', "
                         "minWidth: 280 }}>")
        else:
            lines.append("      <div style={{ maxWidth: %d, margin: '0 auto', "
                         "display: 'flex', flexDirection: 'column', gap: "
                         "'var(--spacing-lg, 2rem)', alignItems: 'flex-start' }}>"
                         % self._section_max_width(vd, 880))
        if heading:
            lines.append("        <h2 style={{ fontFamily: "
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        if offset:
            # The text column closes before the image column opens.
            lines.append("        </div>")
        if section_img:
            alt = (section_entry or {}).get('alt', 'about')
            if offset:
                lines.append('        <div style={{ flex: \'1 1 300px\', '
                             'minWidth: 260, marginLeft: \'auto\' }}>')
                lines.append('          <img src="%s" alt="%s" style={{ width: '
                             % (section_img, str(alt).replace('"', ''))
                             + "'100%', height: 'auto', borderRadius: "
                             "'var(--radius-lg, 12px)', boxShadow: "
                             "'var(--shadow-md, none)' }} />")
                lines.append('        </div>')
            else:
                lines.append('        <img src="%s" alt="%s" style={{ width: '
                             % (section_img, str(alt).replace('"', ''))
                             + "'100%', maxWidth: 480, height: 'auto', borderRadius: "
                             "'var(--radius-md, 8px)' }} />")
        if offset and body:
            # Body paragraphs flow under the two columns in the offset
            # composition (magazine-style pull text).
            lines.append("        <div style={{ flexBasis: '100%', "
                         "maxWidth: 720, marginTop: "
                         "'var(--spacing-lg, 2rem)' }}>")
        if body:
            lines.append("        <p style={{ fontSize: 'var(--body, 1rem)', "
                         "lineHeight: 1.7, color: "
                         "'var(--color-secondary, #475569)' }}>")
            lines.append('          ' + self._jsx_text_literal(body))
            lines.append('        </p>')
        if offset and body:
            lines.append('        </div>')
        lines.append("        <p style={{ fontSize: '0.875rem', letterSpacing: "
                     "'0.04em', color: 'var(--color-primary, #3f5c76)', "
                     "fontWeight: 600, flexBasis: '100%' }}>")
        lines.append('          ' + self._jsx_text_literal(business))
        lines.append('        </p>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        return '\n'.join(lines) + '\n', []

    def _pattern_featuregrid(self, component_name, artifact, heading, body,
                             wrapper, stock_images, valid_routes, section_index,
                             page_sections, available_effects=None, page_path=''):
        """SaaS feature grid — composes the native FeatureGrid organism with
        props when it matched; falls back to the themed item grid."""
        # Phase 47.39A (verified defect #4): the LLM's generated FeatureGrid
        # structured items carry full title + body; the previous binding used
        # only brief service names and lost generated copy.
        structured_items = self._section_items(page_sections, section_index, 'FeatureGrid')
        if structured_items:
            features_src = [str(i.get('title') or i.get('name') or '').strip()
                            for i in structured_items[:6]]
            features_src = [t for t in features_src if t]
            # Structured item bodies ARE the per-feature descriptions; the
            # section body's first paragraph is the intro/subtitle. Carry
            # them separately so ``_featuregrid_organism`` can render
            # descriptions alongside titles (preserving the LLM's creative
            # copy without second generation).
            item_descriptions = [str(i.get('body') or i.get('description') or '').strip()
                                 for i in structured_items[:6]]
            if not features_src:
                # Degenerate item shape — fall back to the old source.
                req = artifact.requirements
                branding = req.branding or {}
                features_src = [str(s) for s in (branding.get('services') or
                                                 (req.goals or []))[:6]
                                if str(s).strip()] or ['Feature', 'Platform', 'Workflow'][:3]
                item_descriptions = []
            # The intro/subtitle remains the section body (not an item body).
            intro_paragraphs = [p.strip() for p in (body or '').split('\n\n') if p.strip()]
            subtitle = intro_paragraphs[0] if intro_paragraphs else (structured_items[0].get('body', '')[:400] if structured_items else '')
            # Feed item descriptions as the ``paragraphs`` tail so the
            # organism renders per-feature text (``paragraphs[idx+1]``).
            paragraphs = [subtitle] + item_descriptions
        else:
            req = artifact.requirements
            branding = req.branding or {}
            features_src = [str(s) for s in (branding.get('services') or
                                             (req.goals or []))[:6]
                            if str(s).strip()]
            if not features_src:
                features_src = ['Feature', 'Platform', 'Workflow'][:3]
            paragraphs = [p.strip() for p in (body or '').split('\n\n') if p.strip()]
            subtitle = paragraphs[0] if paragraphs else ''

        if wrapper and wrapper.get('is_native') and wrapper.get('main') == 'FeatureGrid':
            # Native organism composition: declared data + prop-driven render.
            # Phase 47.40A: resolve the canonical selected effect before
            # delegating to the native organism.
            effects = dict(available_effects or {})
            effect_import = effects.get('SpotlightCard', '')
            effect = 'SpotlightCard' if effect_import else ''
            return self._featuregrid_organism(
                component_name, heading, subtitle, features_src, paragraphs,
                'features grid', effect=effect, effect_import=effect_import)

        # Themed fallback (same shape as the services grid, feature-typed).
        vd = self._visual_direction(artifact)
        effects = dict(available_effects or {})
        effect_line = effects.get('SpotlightCard', '')
        effect = 'SpotlightCard' if effect_line else ''
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="features section" style={{ '
                      "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                      "background: 'var(--color-card, #ffffff)' }}>")
        lines.append("      <div style={{ maxWidth: %d, margin: '0 auto' }}>"
                     % self._section_max_width(vd, 1080))
        if heading:
            lines.append("        <h2 style={{ fontFamily: "
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, marginBottom: "
                         "'var(--spacing-md, 1rem)', color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        if subtitle:
            lines.append("        <p style={{ fontSize: 'var(--body, 1rem)', "
                         "lineHeight: 1.7, color: "
                         "'var(--color-secondary, #475569)', marginBottom: "
                         "'var(--spacing-lg, 2rem)' }}>")
            lines.append('          ' + self._jsx_text_literal(subtitle))
            lines.append('        </p>')
        lines.append("        <div style={{ display: 'grid', "
                     "gridTemplateColumns: 'repeat(auto-fit, minmax(%dpx, 1fr))', "
                     "gap: 'var(--spacing-lg, 2rem)' }}>" % self._card_min_width(vd))
        icons = ['Zap', 'TrendingUp', 'Layers', 'Shield', 'Sparkles', 'Box']
        for idx, feat in enumerate(features_src):
            desc = paragraphs[idx + 1] if idx + 1 < len(paragraphs) else ''
            icon = icons[idx % len(icons)]
            source_attr = str(wrapper['source']).replace('"', '') if wrapper else ''
            if effect:
                item = ('          <%s data-nexora-source="react_bits/%s" '
                        "style={{ border: "
                        "'1px solid var(--color-border, #e2e8f0)', borderRadius: "
                        "'var(--radius-lg, 12px)', padding: "
                        "'var(--spacing-lg, 2rem)' }}>" % (effect, effect))
                closing = '          </%s>' % effect
            else:
                item = ('          <div data-nexora-source="determinant:featuregrid" '
                        "style={{ border: "
                        "'1px solid var(--color-border, #e2e8f0)', borderRadius: "
                        "'var(--radius-lg, 12px)', padding: "
                        "'var(--spacing-lg, 2rem)' }}>")
                closing = '          </div>'
            lines.append(item)
            lines.append('            <%s size={22} aria-hidden="true" '
                         'style={{ color: ' % icon
                         + "'var(--color-primary, #3f5c76)', marginBottom: "
                         "'var(--spacing-sm, 0.5rem)' }} />")
            lines.append("            <h3 style={{ fontFamily: "
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'1.125rem', fontWeight: 600, color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('              ' + self._jsx_text_literal(feat))
            lines.append('            </h3>')
            if desc:
                lines.append("            <p style={{ fontSize: '0.9375rem', "
                             "lineHeight: 1.6, color: "
                             "'var(--color-secondary, #475569)', marginTop: "
                             "'var(--spacing-xs, 0.25rem)' }}>")
                lines.append('              ' + self._jsx_text_literal(desc))
                lines.append('            </p>')
            lines.append(closing)
        lines.append('        </div>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        icons_used = sorted({icons[i % len(icons)] for i in range(len(features_src))})
        imports = ["import { %s } from 'lucide-react'" % ', '.join(icons_used)]
        if effect:
            imports.append(effect_line)
        return code, imports

    def _menuhighlights_api_bound(self, component_name, heading):
        """Phase 47.36 (products capability): MenuHighlights bound to the
        Client API — the native ProductGrid organism renders LIVE products
        from the client's own Odoo DB through the ONE canonical clientApi
        module (GET /api/v1/client/products).

        Contract:
          * explicit projection only — the API's (name, price, sku)
            projection maps to ProductGrid's (title, price, badge); no
            arbitrary Odoo fields exist on this path
          * deterministic loading / empty / error states — a backend
            failure is never masked as live data and never silently falls
            back to static content (one canonical source: the API)
          * same-origin relative request; no credential in browser code
            (authentication is attached server-side by the runtime proxy)
        """
        title = self._jsx_text_literal(heading or 'Our menu')
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  const productsState = useClientProducts(6);')
        lines.append('  if (productsState.loading) {')
        lines.append('    return (')
        lines.append('      <section aria-label="featured menu items" style={{ '
                     "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                     "textAlign: 'center', color: "
                     "'var(--color-secondary, #475569)' }}>")
        lines.append('        <div className="container">')
        lines.append("          <p role=\"status\">Loading our menu…</p>")
        lines.append('        </div>')
        lines.append('      </section>')
        lines.append('    );')
        lines.append('  }')
        lines.append('  if (productsState.error) {')
        lines.append('    return (')
        lines.append('      <section aria-label="featured menu items" style={{ '
                     "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                     "textAlign: 'center', color: "
                     "'var(--color-secondary, #475569)' }}>")
        lines.append('        <div className="container">')
        lines.append('          <p role="alert">Our menu is temporarily '
                     'unavailable. Please check back shortly.</p>')
        lines.append('        </div>')
        lines.append('      </section>')
        lines.append('    );')
        lines.append('  }')
        lines.append('  const products = (productsState.products || []).map('
                     '(p) => ({')
        lines.append('    title: p.name,')
        lines.append("    price: p.price != null ? String(p.price) : '—',")
        lines.append("    badge: p.sku || ''")
        lines.append('  }));')
        lines.append('  if (products.length === 0) {')
        lines.append('    return (')
        lines.append('      <section aria-label="featured menu items" style={{ '
                     "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
                     "textAlign: 'center', color: "
                     "'var(--color-secondary, #475569)' }}>")
        lines.append('        <div className="container">')
        lines.append('          <p>Our menu is being updated. Please check '
                     'back soon.</p>')
        lines.append('        </div>')
        lines.append('      </section>')
        lines.append('    );')
        lines.append('  }')
        lines.append('  return (')
        lines.append('    <ProductGrid data-nexora-source="native/ProductGrid"')
        lines.append('      title=%s' % title)
        lines.append('      products={products} />')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, [
            "import ProductGrid from '../components/ProductGrid.jsx'",
            "import { useClientProducts } from '../lib/clientApi.js'",
        ]

    def _catalog_surface(self, component_name):
        """Phase 47.41: the ecommerce catalog surface (products capability,
        /products route). ONE bounded discovery owner:

          * search query, category, sort, pagination state live HERE (the
            page-level catalog owner) — never inside ProductGrid
          * product data comes from the ONE canonical clientApi module
            (bounded catalog query; no arbitrary fields)
          * ProductGrid/CatalogGrid remain presentation organisms: they
            receive the resolved collection + callbacks
          * PDP via /products?id=<id> — the URL query param is read with
            the EXISTING routing mechanism (pathname routing is untouched;
            no second router)
          * add-to-cart consumes the app-level cart owner (useCart)

        Returns (code, import lines); static-validation clean.
        """
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  const cart = useCart();')
        lines.append('  const [detailId] = useState(function() {')
        lines.append("    return new URLSearchParams(window.location.search).get('id');")
        lines.append('  });')
        lines.append('  const [detailState, setDetailState] = '
                     'useState({ loading: false, product: null, error: null });')
        lines.append('  const [searchText, setSearchText] = useState(\'\');')
        lines.append("  const [activeQuery, setActiveQuery] = useState('');")
        lines.append("  const [category, setCategory] = useState('');")
        lines.append("  const [sort, setSort] = useState('relevance');")
        lines.append('  const [page, setPage] = useState(0);')
        lines.append('  const [categories, setCategories] = useState([]);')
        lines.append('  const [state, setState] = '
                     'useState({ loading: true, products: [], total: 0, error: null });')
        lines.append('  const PAGE_SIZE = 24;')
        lines.append('  useEffect(function() {')
        lines.append('    let cancelled = false;')
        lines.append('    clientApi.categories()')
        lines.append('      .then(function(cats) { if (!cancelled) setCategories(cats); })')
        lines.append('      .catch(function() {});')
        lines.append('    return function() { cancelled = true; };')
        lines.append('  }, []);')
        lines.append('  useEffect(function() {')
        lines.append('    let cancelled = false;')
        lines.append('    setState({ loading: true, products: [], total: 0, error: null });')
        lines.append('    clientApi.catalog({')
        lines.append('      query: activeQuery,')
        lines.append('      categoryId: category ? Number(category) : null,')
        lines.append('      sort: sort,')
        lines.append('      limit: PAGE_SIZE,')
        lines.append('      offset: page * PAGE_SIZE,')
        lines.append('    })')
        lines.append('      .then(function(data) {')
        lines.append('        if (!cancelled) {')
        lines.append('          setState({ loading: false, products: data.products, '
                     'total: data.total, error: null });')
        lines.append('        }')
        lines.append('      })')
        lines.append('      .catch(function() {')
        lines.append('        if (!cancelled) {')
        lines.append('          setState({ loading: false, products: [], total: 0, '
                     "error: 'unavailable' });")
        lines.append('        }')
        lines.append('      });')
        lines.append('    return function() { cancelled = true; };')
        lines.append('  }, [activeQuery, category, sort, page]);')
        lines.append('  useEffect(function() {')
        lines.append('    if (!detailId) return undefined;')
        lines.append('    let cancelled = false;')
        lines.append('    setDetailState({ loading: true, product: null, error: null });')
        lines.append('    clientApi.productDetail(detailId)')
        lines.append('      .then(function(p) {')
        lines.append('        if (!cancelled) {')
        lines.append('          setDetailState({ loading: false, product: p, error: null });')
        lines.append('        }')
        lines.append('      })')
        lines.append('      .catch(function() {')
        lines.append('        if (!cancelled) {')
        lines.append('          setDetailState({ loading: false, product: null, error: \'notfound\' });')
        lines.append('        }')
        lines.append('      });')
        lines.append('    return function() { cancelled = true; };')
        lines.append('  }, [detailId]);')
        # --- PDP branch (/products?id=<id>) ---
        lines.append('  if (detailId) {')
        lines.append('    const dp = detailState.product;')
        lines.append('    const detailProduct = dp ? {')
        lines.append('      id: dp.id,')
        lines.append('      name: dp.name,')
        lines.append('      category: dp.category,')
        lines.append('      sku: dp.sku,')
        lines.append("      price: dp.price != null ? '$' + Number(dp.price).toFixed(2) : '',")
        lines.append("      compareAt: dp.compareAt != null ? '$' + Number(dp.compareAt).toFixed(2) : null,")
        lines.append('      inStock: dp.inStock !== false,')
        lines.append('      description: dp.descriptionFull || dp.description,')
        lines.append('      images: dp.image ? [{ src: dp.image, alt: dp.name }] : [],')
        lines.append('    } : null;')
        lines.append('    return (')
        lines.append('      <ProductDetail')
        lines.append('        data-nexora-source="native/ProductDetail"')
        lines.append('        product={detailProduct}')
        lines.append('        loading={detailState.loading}')
        lines.append('        error={detailState.error}')
        lines.append('        onAddToCart={function() {')
        lines.append('          if (dp) {')
        lines.append('            cart.add({ id: dp.id, name: dp.name, price: dp.price, image: dp.image });')
        lines.append('          }')
        lines.append('        }}')
        lines.append('        onBack={function() { window.location.href = \'/products\'; }}')
        lines.append('      />')
        lines.append('    );')
        lines.append('  }')
        # --- catalog branch (bounded discovery) ---
        lines.append('  const totalPages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));')
        lines.append('  const products = state.products.map(function(p) {')
        lines.append('    return {')
        lines.append('      id: p.id,')
        lines.append('      title: p.name,')
        lines.append("      price: p.price != null ? '$' + Number(p.price).toFixed(2) : '',")
        lines.append("      compareAt: p.compareAt != null ? '$' + Number(p.compareAt).toFixed(2) : null,")
        lines.append('      category: p.category,')
        lines.append('      inStock: p.inStock !== false,')
        lines.append("      badge: p.inStock === false ? 'Unavailable' : '',")
        lines.append("      image: p.image ? { src: p.image, alt: p.name } : null,")
        lines.append('      onAddToCart: function() { cart.add(p); },')
        lines.append("      href: '/products?id=' + p.id,")
        lines.append('    };')
        lines.append('  });')
        lines.append('  const categoryOptions = categories.map(function(c) {')
        lines.append('    return (')
        lines.append('      <option key={c.id} value={c.id}>{c.name} ({c.productCount})</option>')
        lines.append('    );')
        lines.append('  });')
        lines.append('  return (')
        lines.append('    <section aria-label="product catalog" style={{ '
                     "padding: 'var(--spacing-xl, 3rem) var(--spacing-md, 1rem)' }}>")
        lines.append('      <div className="container">')
        lines.append('        <form role="search" aria-label="Product search" onSubmit={function(e) {')
        lines.append('          e.preventDefault();')
        lines.append('          setPage(0);')
        lines.append('          setActiveQuery(searchText.trim());')
        lines.append('        }} style={{ display: \'flex\', gap: \'0.75rem\', flexWrap: \'wrap\', '
                     'marginBottom: \'1.25rem\' }}>')
        lines.append('          <input type="search" value={searchText}')
        lines.append('            onChange={function(e) { setSearchText(e.target.value); }}')
        lines.append('            placeholder="Search products"')
        lines.append('            aria-label="Search products"')
        lines.append("            style={{ flex: '1 1 260px', padding: '10px 14px', fontSize: '0.95rem',")
        lines.append("              border: '1px solid var(--color-border, #e2e8f0)',")
        lines.append("              borderRadius: 'var(--radius-md, 8px)', background: 'var(--color-background, #fff)',")
        lines.append("              color: 'var(--color-text, #1c1917)' }} />")
        lines.append('          <Button variant="primary" type="submit">Search</Button>')
        lines.append('        </form>')
        lines.append('        <div aria-label="Catalog filters" style={{ display: \'flex\', gap: \'0.75rem\', '
                     'flexWrap: \'wrap\', alignItems: \'center\', marginBottom: \'1.5rem\' }}>')
        lines.append('          <select value={category}')
        lines.append('            onChange={function(e) { setPage(0); setCategory(e.target.value); }}')
        lines.append('            aria-label="Filter by category"')
        lines.append("            style={{ padding: '9px 12px', fontSize: '0.9rem',")
        lines.append("              border: '1px solid var(--color-border, #e2e8f0)',")
        lines.append("              borderRadius: 'var(--radius-md, 8px)', background: 'var(--color-background, #fff)',")
        lines.append("              color: 'var(--color-text, #1c1917)' }}>")
        lines.append('            <option value="">All categories</option>')
        lines.append('            {categoryOptions}')
        lines.append('          </select>')
        lines.append('          <select value={sort}')
        lines.append('            onChange={function(e) { setPage(0); setSort(e.target.value); }}')
        lines.append('            aria-label="Sort products"')
        lines.append("            style={{ padding: '9px 12px', fontSize: '0.9rem',")
        lines.append("              border: '1px solid var(--color-border, #e2e8f0)',")
        lines.append("              borderRadius: 'var(--radius-md, 8px)', background: 'var(--color-background, #fff)',")
        lines.append("              color: 'var(--color-text, #1c1917)' }}>")
        lines.append("            <option value=\"relevance\">Newest</option>")
        lines.append("            <option value=\"price_asc\">Price: Low to High</option>")
        lines.append("            <option value=\"price_desc\">Price: High to Low</option>")
        lines.append("            <option value=\"name_asc\">Name: A to Z</option>")
        lines.append('          </select>')
        lines.append('        </div>')
        lines.append('        {state.error ? (')
        lines.append('          <p role="alert" style={{ textAlign: \'center\', padding: \'2rem 0\', '
                     "color: 'var(--color-secondary, #6f6a63)' }}>")
        lines.append('            The catalog is temporarily unavailable. Please try again shortly.')
        lines.append('          </p>')
        lines.append('        ) : (')
        lines.append('          <CatalogGrid data-nexora-source="native/CatalogGrid"')
        lines.append('            products={products}')
        lines.append('            loading={state.loading}')
        lines.append('            resultCount={state.total}')
        lines.append('            emptyMessage={activeQuery ? '
                     "'No products match your search.' : 'The catalog is empty.'} />")
        lines.append('        )}')
        lines.append('        {state.total > PAGE_SIZE ? (')
        lines.append('          <Pagination')
        lines.append('            currentPage={page + 1}')
        lines.append('            totalPages={totalPages}')
        lines.append('            onPageChange={function(next) { setPage(next - 1); }} />')
        lines.append('        ) : null}')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, [
            "import { useState, useEffect } from 'react'",
            "import CatalogGrid from '../components/CatalogGrid.jsx'",
            "import ProductDetail from '../components/ProductDetail.jsx'",
            "import Pagination from '../components/Pagination.jsx'",
            "import Button from '../components/Button.jsx'",
            "import clientApi from '../lib/clientApi.js'",
            "import { useCart } from '../lib/cart.js'",
        ]

    def _pattern_menuhighlights(self, component_name, artifact, heading, body,
                                wrapper, stock_images, valid_routes, section_index,
                                page_sections, available_effects=(), page_path=''):
        """Restaurant featured menu items — composes the native ProductGrid
        organism from the ContentArtifact's STRUCTURED items when they
        carry item+price data (canonical — ADR-0079); otherwise the
        matched card/feature-grid component composes each dish with
        menu-typed semantics throughout."""
        # Phase 47.36 (products capability): the Client API binding is the
        # canonical source — live products from the client's own Odoo DB
        # replace the compile-time static items (single source; no
        # ambiguous precedence between static and live data).
        # Phase 47.41: on the ecommerce catalog route (products capability)
        # the /products page composes the FULL catalog surface (bounded
        # discovery state + ProductGrid presentation + PDP via ?id=) —
        # the home/restaurant featured strip keeps the 47.36 contract.
        if ('products' in self._client_api_capabilities(artifact)
                and page_path in ('/products', '/shop')):
            return self._catalog_surface(component_name)
        if 'products' in self._client_api_capabilities(artifact):
            return self._menuhighlights_api_bound(component_name, heading)
        # Phase 47.27 (ADR-0079): structured items with prices compose the
        # native ProductGrid (real item + price data, not regex products).
        items = self._section_items(page_sections, section_index,
                                    'MenuHighlights')
        if not items:
            # Phase 47.29: the prompt's instructed prose fallback ("Item
            # name - price" blocks) parses deterministically here for
            # artifacts that predate the ContentEngine normalization (the
            # same fallback precedent as Pricing/FAQ prose parsing).
            items = self._parse_menu_blocks(body)
        products = []
        for item in items[:6]:
            title = str(item.get('title') or item.get('name') or '').strip()
            price = str(item.get('price') or '').strip()
            description = str(item.get('body') or item.get('description') or '').strip()
            badge = str(item.get('badge') or '').strip()
            if title:
                products.append({'title': title[:60], 'price': price[:24] or '—',
                                 'description': description[:200],
                                 'badge': badge[:20]})
        if products and any(p['price'] not in ('—', '') for p in products):
            lines = []
            lines.append('function %s() {' % component_name)
            lines.append('  const products = [')
            for product in products:
                lines.append('    {')
                lines.append('      title: %s,' % self._js_string_literal(product['title']))
                lines.append('      price: %s,' % self._js_string_literal(product['price']))
                if product['badge']:
                    lines.append('      badge: %s,' % self._js_string_literal(product['badge']))
                lines.append('    },')
            lines.append('  ]')
            lines.append('  return (')
            lines.append('    <ProductGrid data-nexora-source="native/ProductGrid"')
            lines.append('      title=%s' % self._jsx_text_literal(heading or 'Our menu'))
            lines.append('      products={products} />')
            lines.append('  )')
            lines.append('}')
            code = '\n'.join(lines) + '\n'
            return code, ["import ProductGrid from '../components/ProductGrid.jsx'"]

        # Menu-typed icon vocabulary (dishes, not briefcases).
        menu_icons = {'Briefcase': 'UtensilsCrossed', 'Layers': 'Coffee',
                      'Target': 'ChefHat', 'Compass': 'UtensilsCrossed',
                      'Lightbulb': 'Coffee', 'Box': 'ChefHat'}
        # Structured items without prices still feed the FeatureGrid
        # organism with real item data.
        if items:
            item_titles = [str(i.get('title') or i.get('name') or '').strip()
                           for i in items[:6]]
            item_titles = [t for t in item_titles if t]
            if item_titles:
                paragraphs = [str(i.get('body') or i.get('description') or '').strip()
                              for i in items[:6]]
                paragraphs = [p for p in paragraphs if p] or ['']
                return self._featuregrid_organism(
                    component_name, heading, paragraphs[0], item_titles,
                    paragraphs, 'featured menu items')
        # FeatureGrid organism path with menu label (when it matched).
        if (wrapper and wrapper.get('is_native')
                and wrapper.get('main') == 'FeatureGrid'):
            req = artifact.requirements
            branding = req.branding or {}
            items = [str(s) for s in (branding.get('services') or
                                      (req.goals or []))[:6]
                     if str(s).strip()] or ['Menu', 'Kitchen', 'Bar'][:3]
            paragraphs = [p.strip() for p in (body or '').split('\n\n')
                          if p.strip()] or ['']
            return self._featuregrid_organism(
                component_name, heading, paragraphs[0], items, paragraphs,
                'featured menu items')
        # Grid fallback: reuse the services-grid composition, menu-typed.
        result = self._pattern_servicesgrid(
            component_name, artifact, heading, body, wrapper,
            stock_images, valid_routes, section_index, page_sections,
            available_effects=available_effects)
        if result is None:
            return None
        code, imports = result
        code = code.replace('aria-label="services section"',
                            'aria-label="featured menu items"')
        code = code.replace('determinant:servicesgrid', 'determinant:menu')
        imports = [self._menu_icon_imports(line, menu_icons)
                   for line in imports]
        code = self._menu_icon_code(code, menu_icons)
        return code, imports

    @staticmethod
    def _menu_icon_imports(import_line, menu_icons):
        for original, replacement in menu_icons.items():
            import_line = import_line.replace(original, replacement)
        return import_line

    @staticmethod
    def _menu_icon_code(code, menu_icons):
        for original, replacement in menu_icons.items():
            code = code.replace('<%s ' % original, '<%s ' % replacement)
        return code

    @staticmethod
    def _js_string_literal(value: str) -> str:
        escaped = (value or '').replace('\\', '\\\\').replace("'", "\\'")
        escaped = escaped.replace('\n', '\\n').replace('\r', '')
        return "'%s'" % escaped

    def _pattern_gallery(self, component_name, artifact, heading, body,
                          wrapper, stock_images, valid_routes, section_index,
                          page_sections, available_effects=(), page_path=''):
        gallery = [v for k, v in sorted(stock_images.items())
                   if k.startswith('stock_gallery')]
        if not gallery:
            return None
        # Phase 47.40: gallery geometry from the visual direction —
        # bounded to three implemented variants (uniform grid / feature
        # lead image / masonry columns). Pure CSS differences; the same
        # stock imagery and tokens.
        vd = self._visual_direction(artifact)
        geometry = self._gallery_geometry(vd)
        lines = []
        lines.append('function %s() {' % component_name)
        lines.append('  return (')
        lines.append('    <section aria-label="gallery section" style={{ '
                      "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)' }}>")
        lines.append("      <div style={{ maxWidth: %d, margin: '0 auto' }}>"
                     % self._section_max_width(vd, 1080))
        if heading:
            lines.append('        <h2 style={{ fontFamily: '
                         "'var(--font-heading, Inter, sans-serif)', fontSize: "
                         "'var(--h2, 1.875rem)', fontWeight: 600, marginBottom: "
                         "'var(--spacing-lg, 2rem)', color: "
                         "'var(--color-text, #0f172a)' }}>")
            lines.append('          ' + self._jsx_text_literal(heading))
            lines.append('        </h2>')
        if geometry == 'masonry':
            # Masonry: CSS multi-columns with natural image heights —
            # the immersive/portfolio presentation.
            lines.append("        <div style={{ columns: '320px', "
                         "columnGap: 'var(--spacing-md, 1rem)' }}>")
            for img in gallery:
                alt = (img.get('alt') or 'gallery image').replace('"', '')
                lines.append('          <img src="%s" alt="%s" loading="lazy" '
                             'style={{ width: ' % (img.get('path'), alt)
                             + "'100%', height: 'auto', display: 'block', "
                             "marginBottom: 'var(--spacing-md, 1rem)', "
                             "borderRadius: 'var(--radius-md, 8px)' }} />")
            lines.append('        </div>')
        elif geometry == 'feature':
            # Feature: the first image spans two columns (lead image),
            # the rest fill the uniform grid — the editorial presentation.
            lines.append("        <div style={{ display: 'grid', "
                         "gridTemplateColumns: "
                         "'repeat(auto-fit, minmax(280px, 1fr))', gap: "
                         "'var(--spacing-md, 1rem)' }}>")
            for idx, img in enumerate(gallery):
                alt = (img.get('alt') or 'gallery image').replace('"', '')
                span = ("gridColumn: 'span 2', " if idx == 0 else '')
                aspect = ("aspectRatio: '16 / 10', " if idx == 0
                          else "aspectRatio: '4 / 3', ")
                lines.append('          <img src="%s" alt="%s" loading="lazy" '
                             'style={{ width: ' % (img.get('path'), alt)
                             + "'100%', height: '100%', objectFit: 'cover', "
                             + aspect + span
                             + "borderRadius: 'var(--radius-md, 8px)' }} />")
            lines.append('        </div>')
        else:
            # Uniform grid (previous behavior — centered/grid directions).
            lines.append("        <div style={{ display: 'grid', "
                         "gridTemplateColumns: "
                         "'repeat(auto-fit, minmax(260px, 1fr))', gap: "
                         "'var(--spacing-md, 1rem)' }}>")
            for img in gallery:
                alt = (img.get('alt') or 'gallery image').replace('"', '')
                lines.append('          <img src="%s" alt="%s" loading="lazy" '
                             'style={{ width: ' % (img.get('path'), alt)
                             + "'100%', height: '100%', objectFit: 'cover', "
                             "aspectRatio: '4 / 3', borderRadius: "
                             "'var(--radius-md, 8px)' }} />")
            lines.append('        </div>')
        lines.append('      </div>')
        lines.append('    </section>')
        lines.append('  )')
        lines.append('}')
        code = '\n'.join(lines) + '\n'
        return code, []

    def _deterministic_section_fallback(self, component_name: str, section: str,
                                        page_sections: Optional[List[Dict[str, Any]]],
                                        section_index: int,
                                        hero_image_path: Optional[str] = None) -> str:
        """Phase 47.23 (ADR-0075): safe deterministic section â€” valid React
        using ONLY scaffold dependencies, literal copy from the ContentEngine
        artifact, plain <a> internal links (route-integrity enforced by the
        caller). The deterministic code fallback mirrors ContentEngine's
        fallback contract: valid LLM output is never replaced; only invalid
        output degrades here."""
        heading = ''
        body = ''
        if page_sections:
            matched = None
            if section_index < len(page_sections):
                matched = page_sections[section_index]
            else:
                section_lower = str(section).lower()
                for candidate in page_sections:
                    if str(candidate.get('type', '')).lower() == section_lower:
                        matched = candidate
                        break
            if matched:
                heading = str(matched.get('semantic_heading', '') or matched.get('type', ''))
                body = str(matched.get('body', ''))
        if not heading:
            heading = str(section) + ' Section'
        if not body:
            body = 'Editable content for ' + str(section) + '.'

        safe_section = str(section).replace('"', '')
        hero_img = ''
        if hero_image_path:
            hero_img = (
                '      <img src="' + hero_image_path + '" alt="' + safe_section
                + ' section visual" style={{ width: \'100%\', maxWidth: 640, '
                  'height: \'auto\', borderRadius: \'var(--radius-md, 8px)\', '
                  'marginBottom: \'var(--spacing-lg, 2rem)\' }} />\n'
            )
        heading_tag = 'h1' if self._is_hero_section(section) else 'h2'
        lines = [
            'function ' + component_name + '() {',
            '  return (',
            '    <section aria-label="' + safe_section + ' section" style={{ '
            "padding: 'var(--spacing-xl, 4rem) var(--spacing-md, 1rem)', "
            "maxWidth: 960, margin: '0 auto' }}>",
        ]
        lines.append(hero_img)
        lines += [
            '      <' + heading_tag + ' id="' + component_name + '-heading" '
            'style={{ fontSize: ' + ("'var(--h1, 2.25rem)'" if heading_tag == 'h1'
                                     else "'var(--h2, 1.875rem)'") + ', '
            "fontFamily: 'var(--font-heading, Inter, sans-serif)', fontWeight: 600, "
            "marginBottom: 'var(--spacing-md, 1rem)', color: "
            "'var(--color-text, #0f172a)' }}>",
            '        ' + self._jsx_text_literal(heading),
            '      </' + heading_tag + '>',
            '      <p style={{ fontSize: ' + "'var(--body, 1rem)'" + ', '
            "lineHeight: 1.7, color: 'var(--color-secondary, #475569)' }}>",
            '        ' + self._jsx_text_literal(body),
            '      </p>',
            '    </section>',
            '  )',
            '}',
        ]
        return '\n'.join(lines) + '\n'

    @staticmethod
    def _build_page_module(page_name: str, modules: list, section_names: list,
                           extra_imports: list = None, extra_tags: list = None,
                           seo_title: str = None) -> str:
        rendered_sections = '\n'.join(
            f'      <{section_name} />' for section_name in section_names
        )
        extra_tags_block = '\n'.join(f'      {tag}' for tag in (extra_tags or []))
        body_sections = '\n'.join(
            block for block in (extra_tags_block, rendered_sections) if block
        )
        imports_block = '\n'.join(dict.fromkeys(extra_imports or []))
        imports_block = (imports_block + '\n') if imports_block else ''
        # Phase 47.18 (Part G): per-page document title from the content SEO
        # artifact, set through React's effect hook (no new router needed).
        title_effect = ''
        if seo_title:
            safe_title = seo_title.replace('\\', '\\\\').replace("'", "\\'")
            title_effect = (
                f"  React.useEffect(function() {{\n"
                f"    document.title = '{safe_title}'\n"
                f"  }}, [])\n"
            )
        page_code = (
            "import React from 'react'\n"
            + imports_block
            + "\n"
            + "\n\n".join(modules)
            + f"\n\nfunction {page_name}() {{\n"
            + title_effect
            + "  return (\n    <main>\n"
            + body_sections
            + "\n    </main>\n  )\n}\n\n"
            + f"export default {page_name}\n"
        )
        # Phase 47.25 (ADR-0077): the assembler owns import hygiene. LLM
        # sections may self-carry a whitelisted import (e.g. lucide icons)
        # despite the instruction not to; combined with the assembler's
        # per-section import lines this produced duplicate BINDINGS from
        # the same module (esbuild: "Identifier 'X' has already been
        # declared" â€” the observed E2E 500 class). Merge ALL single-line
        # import statements per module specifier into one statement.
        return CodeGenerationEngine._merge_page_imports(page_code)

    _IMPORT_LINE_RE = re.compile(
        r"^import\s+(?P<clause>[^'\";\n]+?)\s+from\s+['\"](?P<spec>[^'\"]+)['\"]\s*;?\s*$")

    @staticmethod
    def _merge_page_imports(code: str) -> str:
        """Deterministic import merging for an assembled page module.

        Groups every single-line `import ... from '<module>'` statement by
        module specifier and rebuilds ONE merged statement per module
        (default binding, namespace binding, union of named bindings) at
        the top of the file. Non-import lines keep their order. Multi-line
        import statements are left untouched.
        """
        grouped: Dict[str, Dict[str, Any]] = {}
        body_lines = []
        for line in (code or '').split('\n'):
            m = CodeGenerationEngine._IMPORT_LINE_RE.match(line.strip())
            if not m:
                body_lines.append(line)
                continue
            clause = m.group('clause').strip()
            spec = m.group('spec')
            entry = grouped.setdefault(
                spec, {'default': None, 'ns': None, 'named': []})
            ns_m = re.match(r'^\*\s+as\s+([A-Za-z_$][\w$]*)$', clause)
            if ns_m:
                if not entry['ns']:
                    entry['ns'] = ns_m.group(1)
                continue
            if '{' in clause:
                pre, _, named_part = clause.partition('{')
                pre = pre.strip().rstrip(',').strip()
                if pre and not entry['default']:
                    entry['default'] = pre
                for part in named_part.rstrip('}').split(','):
                    token = part.strip()
                    if token and token not in entry['named']:
                        entry['named'].append(token)
            else:
                if not entry['default']:
                    entry['default'] = clause
        if not grouped:
            return code
        merged_lines = []
        for spec, entry in grouped.items():
            parts = []
            if entry['ns']:
                parts.append('* as %s' % entry['ns'])
            elif entry['default']:
                parts.append(entry['default'])
            if entry['named']:
                parts.append('{ %s }' % ', '.join(entry['named']))
            if parts:
                merged_lines.append("import %s from '%s'" % (', '.join(parts), spec))
        return '\n'.join(merged_lines) + '\n\n' + '\n'.join(body_lines).lstrip('\n')

    def _build_app_entry(self, component_hierarchy: dict,
                         artifact: Optional[WebsiteGenerationArtifact] = None) -> str:
        pages = [
            data.get('path', '/')
            for data in component_hierarchy.values()
            if data.get('type') == 'page'
        ]
        pages = list(dict.fromkeys(pages or ['/']))
        imports = ["import SiteLayout from './components/SiteLayout.jsx'"]
        routes = []
        for path in pages:
            module_name = self._page_module_name(path)
            filename = 'index' if path == '/' else f"{path.strip('/')}.tsx"
            imports.append(f"import {module_name} from './pages/{filename}'")
            routes.append(f"  '{path}': {module_name},")
        # Phase 47.41: for products-capable projects the app-level cart
        # owner (provider-scaffold src/lib/cart.js) wraps the router at
        # the entry composition point — ONE state owner above all pages.
        cart_wrap = 'products' in self._client_api_capabilities(artifact) if artifact else False
        if cart_wrap:
            imports.append("import { CartProvider } from './lib/cart.js'")
        body = (
            "function App() {\n"
            + "  const Page = routes[window.location.pathname] || routes['/']\n"
            + "  return (\n"
            + "    <SiteLayout>\n"
            + "      <Page />\n"
            + "    </SiteLayout>\n"
            + "  )\n"
            + "}\n\nexport default App\n"
        )
        if cart_wrap:
            body = body.replace(
                "export default App\n",
                "export default function AppWithCart() {\n"
                "  return (\n"
                "    <CartProvider>\n"
                "      <App />\n"
                "    </CartProvider>\n"
                "  )\n"
                "}\n")
        return (
            "import React from 'react'\n"
            + "\n".join(imports)
            + "\n\nconst routes = {\n"
            + "\n".join(routes)
            + "\n}\n\n" + body
        )

