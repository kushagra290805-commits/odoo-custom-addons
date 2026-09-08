import dataclasses
import logging
import re
from typing import Any, List, Dict, Optional, Tuple
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Assets
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet

_logger = logging.getLogger(__name__)

_ICON_TYPES = {'icon'}
_FONT_TYPES = {'font', 'typography'}
_IMAGE_TYPES = {'image', 'photo', 'picture', 'illustration', 'texture', 'logo', 'banner', 'background'}

class AssetEngine(BaseGenerationEngine):
    """
    Deterministic asset planning/normalization.

    Phase 47.7 / U7: consumes normalized DesignAsset contracts through the
    existing artifact/source channels and incorporates them into the existing
    Assets representation (images/icons/fonts). No binary acquisition or
    materialization happens here: a DesignAsset is recorded with its existing
    materialization status (default NOT materialized) and full provenance.
    Design assets whose type has no existing Assets bucket are preserved as
    deferred references on the artifact for later materialization phases.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing AssetEngine (Deterministic)...")

        req = artifact.requirements

        # 1. Deterministic calculation of required assets from architecture
        required_images = []
        required_icons = set()

        for comp in artifact.component_tree.nodes:
            ctype = comp.get("component_id", "").lower()
            if ctype == "hero": required_images.append(f"hero_bg_{req.domain.lower()}")
            if ctype == "features":
                required_icons.add("zap")
                required_icons.add("shield")
            if ctype == "nav":
                required_icons.add("menu")

        # Phase 47.19 (Part C): a genuine, branded hero visual is DEMANDED
        # only when the architecture genuinely places a Hero section in a
        # page (or a hero-family component - not the exact 'hero' token,
        # which the U7 contract maps to hero_bg_*). When demanded, the visual
        # is a real, deterministic branded SVG with full provenance - closing
        # the 47.18 consumption gap (Assets 2/10) at the source.
        hero_visual_demanded = self._hero_visual_required(artifact)

        images = []
        icons = []
        seen_assets = set()
        features = ProviderFeatureSet(supports_json_mode=False)

        if hero_visual_demanded:
            images.append({
                "id": "hero_visual",
                "format": "svg",
                "content": self._build_hero_visual(
                    req.business_name or req.branding.get("business_name", "") or req.domain,
                    req.domain,
                ),
                "metadata": {
                    "alt": f"{req.business_name or req.domain} hero visual",
                    "ownership": "nexora_generated",
                    "generated": True,
                },
            })
            seen_assets.add("hero_visual")

        # 2. Re-use existing / Deduplicate / Optimize
        for img_id in required_images:
            if img_id in seen_assets: continue
            seen_assets.add(img_id)

            # Use Asset Bridge Provider
            try:
                # In production, this might fetch from an internal stock library or generate
                res = self.orchestrator.execute(ProviderCategory.ASSET, "optimize_asset", {"content": f"<svg id='{img_id}'></svg>"}, features)
                content = res.data.get("content", f"<svg id='{img_id}'></svg>") if res.success else f"<svg id='{img_id}'></svg>"

                images.append({
                    "id": img_id,
                    "format": "svg",
                    "content": content,
                    "metadata": {"alt": f"{img_id.replace('_', ' ')}", "ownership": "nexora_generated"}
                })
            except Exception as e:
                _logger.warning(f"Asset bridge failure for {img_id}: {str(e)}")

        for icon in required_icons:
            if icon in seen_assets: continue
            seen_assets.add(icon)

            icons.append({
                "id": icon,
                "format": "svg",
                "content": f"<svg data-lucide='{icon}'></svg>",
                "metadata": {"ownership": "lucide-react"}
            })

        # Phase 47.23 (ADR-0075): the font plan mirrors the ThemeEngine
        # selection (the canonical font owner) instead of a fixed Inter —
        # the actual webfont materialization happens in the rendering
        # provider scaffold.
        theme_fonts = [
            getattr(artifact.theme, 'font_heading', ''),
            getattr(artifact.theme, 'font_body', ''),
        ]
        fonts = []
        for family in dict.fromkeys(filter(None, [f.strip() for f in theme_fonts]) or ['Inter']):
            fonts.append({
                "family": family,
                "weights": [400, 500, 600, 700],
                "metadata": {"ownership": "google_fonts"},
            })

        # 3. Phase 47.7 / U7 — consume normalized DesignAsset contracts.
        try:
            design_assets, asset_provider_errors = self._collect_design_assets(artifact, runtime)
        except ValueError as e:
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                metadata={"asset_status": "malformed_artifact"},
                error=str(e),
            )

        # 3.5 Phase 47.24 (ADR-0076): optional stock photography through the
        # ONE new external resource provider (Pexels). The AssetEngine owns
        # provider selection, request, normalization, role assignment and
        # failure handling; intents are STRUCTURAL (role/subject), derived
        # from the brief + the selected page pattern. Any failure is
        # gracefully skipped — the deterministic SVG hero remains the floor
        # and image retrieval is never a hard dependency.
        stock_entries, stock_evidence = self._collect_stock_photos(artifact, runtime)
        for entry in stock_entries:
            if entry['id'] in seen_assets:
                continue
            seen_assets.add(entry['id'])
            images.append(entry)

        incorporated = []
        deferred = []
        for design_asset in design_assets:
            entry = self._design_asset_entry(design_asset)
            if entry["id"] in seen_assets:
                continue
            bucket = self._asset_bucket(design_asset.type)
            if bucket == 'image':
                seen_assets.add(entry["id"])
                images.append(entry)
                incorporated.append(entry)
            elif bucket == 'icon':
                seen_assets.add(entry["id"])
                icons.append(entry)
                incorporated.append(entry)
            elif bucket == 'font':
                seen_assets.add(entry["id"])
                fonts.append(entry)
                incorporated.append(entry)
            else:
                # No existing Assets bucket for this type — preserve the
                # reference honestly for later materialization phases.
                deferred.append(entry)

        new_generation_metadata = dict(artifact.generation_metadata or {})
        if deferred:
            new_generation_metadata["design_assets_deferred"] = (
                list(new_generation_metadata.get("design_assets_deferred") or []) + deferred
            )

        model = Assets(images=images, icons=icons, fonts=fonts)
        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(assets=model, generation_metadata=new_generation_metadata),
            metadata={
                "design_assets_incorporated": len(incorporated),
                "design_assets_deferred": len(deferred),
                "asset_provider_errors": asset_provider_errors,
                "stock_provider": stock_evidence.get('provider'),
                "stock_photos": stock_evidence.get('photos', []),
                "stock_cache_hits": stock_evidence.get('cache_hits', 0),
            },
            error=None
        )

    # ------------------------------------------------------------------
    # Phase 47.24 (ADR-0076): stock photography (Pexels)
    # ------------------------------------------------------------------

    def _collect_stock_photos(self, artifact: WebsiteGenerationArtifact,
                              runtime: 'GenerationRuntime'):
        """Role-tagged stock photo collection through the existing AssetEngine
        owner. Returns (image entries, evidence dict). Never raises.

        Phase 47.28: Adds deterministic relevance ranking for Pexels results.
        Candidates are scored against section context (type, heading, domain,
        content) instead of accepting the first match."""
        evidence = {'provider': None, 'photos': [], 'cache_hits': 0}
        try:
            from odoo.addons.nexora_studio.services.providers.asset import pexels_provider
            env = getattr(runtime, 'env', None)
            if not pexels_provider.is_configured(env):
                evidence['provider'] = 'unconfigured'
                return [], evidence
            evidence['provider'] = 'pexels'

            req = artifact.requirements
            category = (getattr(req, 'business_category', '')
                        or (req.branding or {}).get('business_category')
                        or req.domain or 'business')
            pattern = artifact.generation_metadata.get('page_pattern') or {}
            all_sections = list(pattern.get('home_sections') or []) + \
                list(pattern.get('secondary_sections') or [])
            # Fallback: read the actual architecture sections when the
            # pattern metadata is absent (e.g. direct engine tests).
            if not all_sections:
                hierarchy = getattr(artifact.architecture, 'component_hierarchy', None) or {}
                for page in hierarchy.values():
                    if isinstance(page, dict):
                        all_sections.extend(page.get('sections') or [])

            subject = str(category).strip() or 'business'
            intents = self._build_stock_intents(artifact, all_sections, subject)

            entries = []
            used_photo_ids = set()
            for intent in intents:
                role = intent['role']
                section_type = (intent.get('context') or {}).get('section_type') or ''
                results, _ = pexels_provider.search_photos(
                    env, intent['query'], orientation=intent['orientation'],
                    per_page=8)  # Fetch more candidates for ranking
                evidence['cache_hits'] = pexels_provider.cache_hits
                picked = 0
                wanted = 3 if role == 'gallery' else 1
                # Phase 47.28: rank results by relevance to the intent context
                ranked = self._rank_stock_candidates(results, intent, artifact)
                for photo in ranked:
                    if picked >= wanted:
                        break
                    if photo['photo_id'] in used_photo_ids:
                        continue
                    used_photo_ids.add(photo['photo_id'])
                    # Phase 47.29: section entries carry a PER-SECTION id
                    # (stock_section_<type>) so each section type gets its
                    # own (uniquely assigned) image instead of every
                    # section sharing one 'stock_section' slot — the
                    # AssetEngine dedup no longer discards the other
                    # section photos, and the renderer can address each
                    # section's image deterministically.
                    entry_id = 'stock_%s%s' % (
                        (role + '_' + str(section_type).lower()) if role == 'section' else role,
                        picked + 1 if role == 'gallery' else '')
                    entries.append({
                        'id': entry_id,
                        'format': 'jpg',
                        'role': role,
                        'section_type': section_type,
                        'remote_url': photo['remote_url'],
                        'content': None,
                        'metadata': {
                            'ownership': 'pexels',
                            'alt': photo['alt'] or ('%s %s' % (subject, role)),
                            'photographer': photo['photographer'],
                            'license': photo['license'],
                            'source_url': photo['source_url'],
                            'query': intent['query'],
                            'width': photo['width'],
                            'height': photo['height'],
                            'remote': True,
                            'relevance_score': photo.get('_relevance_score', 0),
                        },
                    })
                    evidence['photos'].append({
                        'id': entry_id, 'role': role,
                        'section_type': section_type,
                        'photo_id': photo['photo_id'],
                        'query': intent['query'],
                        'relevance_score': photo.get('_relevance_score', 0),
                    })
                    picked += 1
            return entries, evidence
        except Exception as e:
            _logger.warning("AssetEngine: stock photo collection failed: %s", e)
            evidence['provider'] = 'error'
            return [], evidence

    def _build_stock_intents(self, artifact: WebsiteGenerationArtifact,
                             all_sections: List[str], subject: str) -> List[Dict[str, Any]]:
        """Build structural intents for stock photo collection with enriched
        context for relevance ranking (Phase 47.28).

        Phase 47.29: section queries are SUBJECT-AWARE — the brief's domain
       /category drives the candidate pool (a restaurant About section
        searches restaurant imagery, not a generic office) instead of a
        domain-agnostic fixed phrase. Structural roles and deterministic
        intent order are unchanged."""
        intents = [{'role': 'hero', 'query': subject,
                    'orientation': 'landscape',
                    'context': {'section_type': 'Hero', 'page': 'home',
                                'domain': subject}}]
        # Gallery intent with section-specific context
        if any(s == 'Gallery' for s in all_sections):
            intents.append({'role': 'gallery', 'query': subject + ' interior detail',
                            'orientation': 'landscape',
                            'context': {'section_type': 'Gallery', 'page': 'home',
                                        'domain': subject}})
        # Section-specific intents: subject + short section phrase.
        section_contexts = {
            'ServicesGrid': 'team workspace',
            'FeatureGrid': 'software dashboard interface',
            'MenuHighlights': 'food dishes',
            'Pricing': 'pricing plans',
            'FAQ': 'customer support',
            'Testimonial': 'happy customer',
            'About': 'team office',
            'ContactCTA': 'business meeting',
        }
        for section in all_sections:
            if section in section_contexts:
                intents.append({
                    'role': 'section',
                    'query': (subject + ' ' + section_contexts[section]).strip(),
                    'orientation': 'landscape',
                    'context': {'section_type': section, 'page': 'home',
                                'domain': subject},
                })
        return intents

    def _rank_stock_candidates(self, candidates: List[Dict[str, Any]],
                               intent: Dict[str, Any],
                               artifact: WebsiteGenerationArtifact) -> List[Dict[str, Any]]:
        """Deterministic relevance ranking for Pexels candidates (Phase 47.28).

        Scores each candidate against the intent context using:
        - Alt text keyword overlap with domain/section keywords
        - Aspect ratio suitability (landscape for hero/section)
        - Photographer diversity (avoid same photographer for multiple roles)
        - Image dimensions (prefer higher resolution for hero)

        Returns candidates sorted by relevance score (highest first).
        """
        if not candidates:
            return []

        context = intent.get('context', {})
        section_type = context.get('section_type', '')
        domain = context.get('domain', '').lower()
        role = intent.get('role', '')

        # Build keyword sets for scoring
        domain_keywords = set(domain.split())
        section_keywords = self._section_keywords(section_type)
        role_keywords = self._role_keywords(role)
        all_keywords = domain_keywords | section_keywords | role_keywords

        scored = []
        for photo in candidates:
            score = 0.0
            alt = (photo.get('alt') or '').lower()

            # 1. Keyword overlap in alt text (primary signal)
            alt_words = set(re.findall(r'[a-z]+', alt))
            overlap = len(all_keywords & alt_words)
            score += overlap * 2.0

            # 2. Aspect ratio suitability
            width = photo.get('width') or 0
            height = photo.get('height') or 0
            if width and height:
                ratio = width / height
                if role == 'hero' and 1.5 <= ratio <= 2.5:  # landscape preferred
                    score += 1.5
                elif role == 'gallery' and 1.2 <= ratio <= 1.8:
                    score += 1.0
                elif role == 'section' and 1.3 <= ratio <= 2.0:
                    score += 1.0

            # 3. Resolution preference (higher is better for hero)
            if role == 'hero' and width >= 1920:
                score += 1.0
            elif width >= 1200:
                score += 0.5

            # 4. Avoid duplicate photographers across roles (handled at collection level)
            # 5. Deterministic tie-breaker: photo_id for stable ordering
            score += (photo.get('photo_id') or 0) * 1e-9

            photo['_relevance_score'] = round(score, 3)
            scored.append(photo)

        # Sort by relevance descending, then by photo_id for determinism
        scored.sort(key=lambda p: (-p.get('_relevance_score', 0), p.get('photo_id', 0)))
        return scored

    @staticmethod
    def _section_keywords(section_type: str) -> set:
        """Keywords associated with each section type for relevance scoring."""
        mapping = {
            'Hero': {'hero', 'banner', 'landing', 'header', 'showcase'},
            'ServicesGrid': {'service', 'workspace', 'team', 'office', 'professional', 'meeting'},
            'FeatureGrid': {'feature', 'dashboard', 'software', 'app', 'ui', 'interface', 'technology'},
            'MenuHighlights': {'food', 'restaurant', 'dish', 'plated', 'cuisine', 'kitchen', 'meal'},
            'Pricing': {'pricing', 'plan', 'comparison', 'tier', 'subscription', 'price'},
            'FAQ': {'support', 'help', 'question', 'answer', 'faq', 'customer', 'service'},
            'Testimonial': {'review', 'testimonial', 'customer', 'happy', 'client', 'quote'},
            'About': {'team', 'office', 'company', 'story', 'about', 'founder', 'culture'},
            'ContactCTA': {'contact', 'meeting', 'handshake', 'business', 'email', 'form'},
            'Gallery': {'interior', 'venue', 'space', 'atmosphere', 'detail', 'ambience'},
        }
        return mapping.get(section_type, set())

    @staticmethod
    def _role_keywords(role: str) -> set:
        """Keywords associated with each photo role."""
        mapping = {
            'hero': {'hero', 'banner', 'landing', 'wide', 'panoramic', 'showcase'},
            'section': {'section', 'content', 'illustration', 'detail', 'medium'},
            'gallery': {'gallery', 'detail', 'closeup', 'interior', 'ambience', 'atmosphere'},
        }
        return mapping.get(role, set())

    # ------------------------------------------------------------------
    # Canonical DesignAsset consumption (Phase 47.7 / U7)
    # ------------------------------------------------------------------

    def _collect_design_assets(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime'):
        """Collect normalized DesignAsset values through existing channels:
        values already published on the artifact by upstream stages, plus
        SEARCH-capable sources via the existing source framework. Optional
        provider failures are isolated; malformed DesignAsset contracts raise
        ValueError (stage failure)."""
        from odoo.addons.nexora_studio.services.source_framework.domain_models import DesignAsset

        collected = []
        provider_errors: List[Dict[str, str]] = []

        for item in (artifact.generation_metadata or {}).get('design_assets') or []:
            collected.append(self._coerce_design_asset(item, 'artifact.generation_metadata'))

        try:
            env = runtime.env
        except Exception:
            env = None
        if env:
            from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager
            try:
                provider_manager = ProviderManager(env)
                provider_manager.load_from_registry()
                providers = provider_manager.get_capable_providers('SEARCH')
            except Exception as exc:
                provider_errors.append({
                    'provider': 'source_framework',
                    'operation': 'load',
                    'error': str(exc),
                })
                providers = []

            query = f"{artifact.requirements.domain} design assets"
            for provider_id in providers:
                try:
                    results = provider_manager.route_request(provider_id, 'search', query)
                except Exception as exc:
                    provider_errors.append({
                        'provider': provider_id,
                        'operation': 'search',
                        'error': str(exc),
                    })
                    continue
                for item in results or []:
                    if isinstance(item, DesignAsset):
                        collected.append(self._validate_design_asset(item, provider_id))
                    # ComponentPackage / documents belong to their own paths.

        return collected, provider_errors

    @classmethod
    def _coerce_design_asset(cls, item, source_label):
        from odoo.addons.nexora_studio.services.source_framework.domain_models import DesignAsset
        if isinstance(item, DesignAsset):
            return cls._validate_design_asset(item, source_label)
        if isinstance(item, dict):
            fields = {
                key: value for key, value in item.items()
                if key in DesignAsset.__dataclass_fields__
            }
            try:
                design_asset = DesignAsset(**fields)
            except TypeError as exc:
                raise ValueError(
                    f"Malformed DesignAsset from {source_label}: {exc}"
                ) from exc
            return cls._validate_design_asset(design_asset, source_label)
        raise ValueError(
            f"Malformed DesignAsset from {source_label}: "
            f"got {type(item).__name__}, expected DesignAsset"
        )

    @staticmethod
    def _validate_design_asset(item, source_label):
        if not item.asset_id or not item.name or not item.type:
            raise ValueError(
                f"Malformed DesignAsset from {source_label}: "
                "asset_id/name/type contract violated"
            )
        if item.metadata is not None and not isinstance(item.metadata, dict):
            raise ValueError(
                f"Malformed DesignAsset from {source_label}: metadata must be a dict"
            )
        return item

    @staticmethod
    def _asset_bucket(asset_type: str) -> Optional[str]:
        normalized = str(asset_type or '').strip().lower()
        if normalized in _ICON_TYPES:
            return 'icon'
        if normalized in _FONT_TYPES:
            return 'font'
        if normalized in _IMAGE_TYPES:
            return 'image'
        return None

    @staticmethod
    def _design_asset_entry(asset) -> Dict[str, Any]:
        """Serialize a canonical DesignAsset into the existing Assets entry
        shape. Materialization is NEVER claimed: the recorded status is the
        one already defined on the artifact (default False)."""
        provenance = asset.provenance
        metadata = dict(asset.metadata or {})
        if asset.design_tokens is not None and dataclasses.is_dataclass(asset.design_tokens):
            metadata.setdefault('design_tokens', dataclasses.asdict(asset.design_tokens))
        return {
            "id": asset.asset_id,
            "name": asset.name,
            "type": asset.type,
            "url": asset.url,
            "format": metadata.get("format"),
            "content": metadata.get("content"),
            "materialized": bool(metadata.get("materialized", False)),
            "license": getattr(provenance, 'license', None) if provenance else None,
            "provenance": (
                dataclasses.asdict(provenance)
                if provenance and dataclasses.is_dataclass(provenance)
                else provenance
            ),
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Phase 47.19 (Part C) — branded hero visual
    # ------------------------------------------------------------------

    @classmethod
    def _hero_visual_required(cls, artifact: WebsiteGenerationArtifact) -> bool:
        """True when the architecture genuinely places a Hero on a page.

        The exact component_token 'hero' is NOT considered here: the U7
        contract established that as the hero_bg_<domain> background
        placeholder. A hero-family component (hero_section, hero banner,
        ...) or a page section named Hero drives the branded visual."""
        hierarchy = getattr(artifact.architecture, 'component_hierarchy', None)
        if hierarchy:
            for page in (hierarchy or {}).values():
                if not isinstance(page, dict):
                    continue
                sections = [str(s).lower() for s in (page.get('sections') or [])]
                if any(s == 'hero' or s.startswith('hero') for s in sections):
                    return True
        for node in getattr(artifact.component_tree, 'nodes', None) or []:
            ctype = str(node.get('component_id', '')).lower()
            semantic = str((node.get('metadata') or {}).get('semantic', '')).lower()
            for token in (ctype, semantic):
                if token and token != 'hero' and 'hero' in token:
                    return True
        return False

    @staticmethod
    def _build_hero_visual(business_name: str, domain: str) -> str:
        """Produce a deterministic, branded hero visual (SVG).

        Not an LLM call and not fetched from any external stock library: a
        genuine, self-contained gradient + abstract line composition carrying
        the business name and domain. Deterministic by design so that the
        output is reproducible and carries no licensing surface."""
        name = (business_name or domain or 'Nexora Studio').strip()
        domain = (domain or 'Studio').strip()
        safe_name = (name
                     .replace('&', '&amp;')
                     .replace('<', '&lt;')
                     .replace('>', '&gt;'))
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" '
            'role="img" aria-label="' + safe_name + ' hero visual">'
            '<defs>'
            '<linearGradient id="heroSky" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#1c1917"/>'
            '<stop offset="1" stop-color="#3b2f2b"/>'
            '</linearGradient>'
            '<linearGradient id="heroAccent" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#d6b58a"/>'
            '<stop offset="1" stop-color="#a8845c"/>'
            '</linearGradient>'
            '</defs>'
            '<rect width="1200" height="800" fill="url(#heroSky)"/>'
            '<g stroke="url(#heroAccent)" stroke-width="3" fill="none" '
            'opacity="0.85">'
            '<path d="M120 640 L420 320 L720 600 L1080 240"/>'
            '<path d="M120 680 L300 500 L520 660 L760 440 L1080 560"/>'
            '</g>'
            '<circle cx="960" cy="180" r="60" fill="none" stroke="url(#heroAccent)" '
            'stroke-width="4"/>'
            '<circle cx="960" cy="180" r="24" fill="url(#heroAccent)"/>'
            '<text x="120" y="720" font-family="Inter, system-ui, sans-serif" '
            'font-size="64" font-weight="700" fill="#f5efe6">' + safe_name +
            '</text>'
            '<text x="122" y="760" font-family="Inter, system-ui, sans-serif" '
            'font-size="28" fill="#d6b58a" letter-spacing="4">' + domain.upper() +
            '</text>'
            '</svg>'
        )
