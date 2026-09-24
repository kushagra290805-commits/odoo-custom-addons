# -*- coding: utf-8 -*-
import logging
import json
import re
from typing import Any, Dict, List, Optional

from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Content

_logger = logging.getLogger(__name__)

# Phase 47.20C: canonical inline schema description for the generate_content
# prompt. The AIRuntimeAdapter excludes 'response_format' from the prompt
# context and the OpenRouter adapter does not transmit response_format (many
# free models reject it), so the schema must be stated in the prompt itself
# for the LLM to have any contract to follow. This mirrors the response_format
# schema below exactly (single source of truth kept adjacent).
_CONTENT_SCHEMA_PROMPT = (
    "Return ONLY a single JSON object (no markdown fence, no commentary) of shape: "
    '{"pages": {"/<path>": {"seo": {"title": string, "description": string}, '
    '"metadata": {"status": "draft"}, "sections": [{"type": string, '
    '"semantic_heading": string, "aria_label": string, "body": string, '
    '"items": [{"title": string, "body": string, "price": string, '
    '"question": string, "answer": string, "badge": string, '
    '"category": string}]}]}}} '
    "where \"pages\" is an OBJECT keyed by page path (never an array). "
    "Use the page map keys exactly. Write real, client-specific body copy "
    "grounded in the provided business/positioning/research/knowledge context "
    "and the exact client brief (authoritative). "
    "\"items\" is REQUIRED for every Pricing, FAQ, and "
    "MenuHighlights/Product section. Use exactly these item fields: "
    "Pricing items: {\"title\": plan name, \"price\": price string, "
    "\"body\": features separated by semicolons}. "
    "FAQ items: {\"question\": full question, \"answer\": 1-3 sentence "
    "answer}. "
    "MenuHighlights/Product items: {\"title\": dish/product name, "
    "\"price\": price string, \"body\": short description}. "
    "Example Pricing section entry: {\"type\": \"Pricing\", "
    "\"semantic_heading\": \"Pricing\", \"aria_label\": \"pricing\", "
    "\"body\": \"Choose the plan that fits.\", \"items\": ["
    "{\"title\": \"Starter\", \"price\": \"$29/mo\", "
    "\"body\": \"5 dashboards; email support\"}, "
    "{\"title\": \"Pro\", \"price\": \"$79/mo\", "
    "\"body\": \"Unlimited dashboards; priority support\"}]}. "
    "Every item MUST be an object with those exact string keys — never "
    "an array, never a nested object per field. "
    "Keep body copy on every section as well (items complement it, not "
    "replace it). "
    "FACTUAL GROUNDING (mandatory): Only use the business facts supplied in "
    "the business context + raw brief (addresses, phone numbers, awards, "
    "named testimonials/authors, certifications, SLAs, years in business, "
    "locations, staff identities, statistics, guarantees, pricing facts, "
    "product claims). Do NOT invent concrete factual assertions the brief "
    "did not supply. Creative marketing language is allowed; fabricated "
    "factual claims are not (unsupported facts must simply be omitted). "
    "For sections of type \"Pricing\" without items: separate each plan "
    "with a blank line, first line exactly \"Plan name - price\", then one "
    "feature per line. "
    "For sections of type \"FAQ\" without items: separate each entry with "
    "a blank line, first line is the question (ending with ?), following "
    "lines the answer. "
    "For sections of type \"MenuHighlights\" without items: separate each "
    "item with a blank line, first line exactly \"Item name - price\", "
    "then a short description line."
)

# Phase 47.27 (ADR-0079): canonical structured-item field names accepted
# from the LLM's natural shapes, mapped onto the canonical item keys.
_ITEM_KEY_ALIASES = {
    'title': ('title', 'name', 'heading', 'label', 'plan', 'question'),
    'body': ('body', 'description', 'answer', 'text', 'value', 'details',
             'features'),
    'price': ('price', 'cost', 'amount'),
    'badge': ('badge', 'tag'),
    'category': ('category', 'cuisine', 'type'),
    'question': ('question', 'q'),
    'answer': ('answer', 'a'),
}

_ITEM_LIST_KEYS = ('items', 'list', 'faqs', 'plans', 'menu', 'products',
                   'features', 'entries')

_FENCE_RE = re.compile(r'^\s*```[a-zA-Z0-9_+-]*\s*\n*|\s*```\s*$')

# Phase 47.29: price-like token (currency symbol or digits) — guards the
# deterministic "Name - price" string/block repair against prose.
_PRICEISH_RE = re.compile(r'[$€£¥₹]|\d')


class ContentEngine(BaseGenerationEngine):
    def _validate_schema(self, content_data: Dict[str, Any]) -> bool:
        # Enforce structural strictness — the canonical ContentArtifact contract.
        if not isinstance(content_data, dict) or "pages" not in content_data:
            return False
        pages = content_data["pages"]
        if not isinstance(pages, dict) or not pages:
            return False
        for page_id, data in pages.items():
            if not isinstance(data, dict):
                return False
            if "seo" not in data or "metadata" not in data or "sections" not in data:
                return False
            if not isinstance(data["sections"], list):
                return False
            if "title" not in data["seo"]:
                return False
        return True

    # ------------------------------------------------------------------
    # Phase 47.18 (Part C): bounded, structured generation context built
    # from the EXISTING artifact contracts. No new models — these are plain
    # payload digests consumed through the existing AI-boundary prompt.
    # ------------------------------------------------------------------

    @staticmethod
    def _business_context(artifact: WebsiteGenerationArtifact) -> Dict[str, Any]:
        req = artifact.requirements
        branding = req.branding or {}
        return {
            'name': req.business_name or branding.get('business_name', ''),
            'category': req.business_category or branding.get('business_category', ''),
            'location': req.location or branding.get('location', ''),
            'audience': req.target_audience,
            'services': (branding.get('services') or [])[:8],
            'positioning': branding.get('positioning') or '',
            'differentiators': branding.get('differentiators') or '',
            'cta': branding.get('cta') or '',
            # Raw brief (bounded): the authoritative client fact base — the
            # model must not invent facts missing from it (fixes SLA/address/
            # testimonial invention). Bounded, no secrets.
            'brief': (req.raw_input or '')[:2000],
            'supervisor_instruction': getattr(req, 'current_supervisor_instruction', ''),
        }

    @staticmethod
    def _research_digest(artifact: WebsiteGenerationArtifact) -> List[Dict[str, Any]]:
        entries = (artifact.research or {}).get('business_data') or []
        digest = []
        for entry in entries[:6]:
            if not isinstance(entry, dict):
                continue
            payload = entry.get('payload') or {}
            digest.append({
                'title': payload.get('title') or payload.get('name', ''),
                'category': entry.get('category', ''),
                'address': payload.get('address') or payload.get('complete_address', ''),
                'rating': payload.get('rating'),
                'source': 'business_search',
                'provenance': entry.get('provenance'),
            })
        return digest

    @staticmethod
    def _knowledge_digest(artifact: WebsiteGenerationArtifact) -> List[Dict[str, Any]]:
        documents = (artifact.knowledge or {}).get('knowledge_documents') or []
        digest = []
        for doc in documents[:4]:
            if not isinstance(doc, dict):
                continue
            content = str(doc.get('content') or '')
            digest.append({
                'title': doc.get('title', ''),
                'excerpt': content[:280],
                'source': doc.get('document_id', ''),
                'provenance': doc.get('provenance'),
            })
        return digest

    # ------------------------------------------------------------------
    # Phase 47.20C: REAL LLM JSON contract repair. Real providers (OpenRouter)
    # return the JSON payload as a string — sometimes wrapped in a markdown
    # fence — and frequently in a natural "site + pages[]" shape even when the
    # prompt requests the canonical pages-object shape. These two members
    # normalize that real-world output into the canonical schema so valid LLM
    # content is no longer lost to the deterministic fallback. Deterministic
    # fallback remains for genuine failures (parse errors / unusable output).
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json_payload(raw: Any) -> Dict[str, Any]:
        """Deterministic extraction of the JSON object from an AI response.

        Accepts: already-parsed dict (mock/test contract) or a string that may
        carry a markdown fence / stray prose. Returns {} when unusable.

        Phase 47.29: weak free models occasionally emit structurally
        invalid JSON — mismatched closing brackets (a list closed with
        ``]`` where an object ``}`` was opened) or truncation (missing
        closers). A bounded deterministic bracket-balancing repair runs
        before giving up (no LLM call, no schema loosening — the result
        still passes _validate_schema or the fallback runs).
        """
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str) or not raw.strip():
            return {}
        text = _FENCE_RE.sub('', raw.strip())
        try:
            parsed = json.loads(text)
        except Exception:
            # Fenced-or-prose fallback: locate the outermost JSON object.
            start = text.find('{')
            if start == -1:
                return {}
            end = text.rfind('}')
            candidate = text[start:end + 1] if end > start else text[start:]
            try:
                parsed = json.loads(candidate)
            except Exception:
                repaired = ContentEngine._balance_json_brackets(candidate)
                if repaired is None:
                    return {}
                try:
                    parsed = json.loads(repaired)
                except Exception:
                    return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _balance_json_brackets(text: str):
        """Deterministic bracket repair for malformed LLM JSON.

        Rules (string-state aware):
          * a closing bracket whose type mismatches the open stack is
            replaced by the EXPECTED closer (``]`` closing a ``{`` -> ``}``);
          * stray closers with an empty stack are dropped;
          * missing closers at end-of-text are appended (truncation);
          * an unterminated string literal is closed.
        Returns the repaired string or None when nothing was extracted.
        """
        stack = []
        out = []
        in_string = False
        escaped = False
        for ch in text:
            if in_string:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                out.append(ch)
                continue
            if ch in '{[':
                stack.append(ch)
                out.append(ch)
                continue
            if ch in '}]':
                if stack:
                    expected = '}' if stack[-1] == '{' else ']'
                    out.append(ch if ch == expected else expected)
                    stack.pop()
                # Stray closer with an empty stack: dropped.
                continue
            if ch == ',' and not stack:
                continue
            out.append(ch)
        if in_string:
            out.append('"')
        while stack:
            out.append('}' if stack.pop() == '{' else ']')
        repaired = ''.join(out)
        return repaired if repaired.strip() else None

    def _normalize_content_schema(self, content: Any, artifact: WebsiteGenerationArtifact) -> Dict[str, Any]:
        """Normalize the LLM's output into the canonical ContentEngine schema.

        Handles the two real-world shapes (verified by the real-LLM probe):
          1. Canonical: {"pages": {"/": {seo, metadata, sections}}} — accepted
             as-is after section-level canonicalization.
          2. Natural LLM shape: {"site": {...}, "pages": [ {slug, sections:
             [ {type, editable: {heading/body/...}} ]} ]} — converted.
        Returns {} (schema-invalid) when no usable page data exists.
        """
        if not isinstance(content, dict):
            return {}

        raw_pages = content.get("pages")
        from_list_shape = isinstance(raw_pages, list)
        if from_list_shape:
            # Natural LLM shape: array of page objects keyed by "slug".
            pages_in = {}
            for page_obj in raw_pages:
                if not isinstance(page_obj, dict):
                    continue
                slug = page_obj.get("slug") or page_obj.get("path") or "/"
                if not isinstance(slug, str):
                    continue
                if not slug.startswith("/"):
                    slug = "/" + slug.lstrip("/")
                pages_in[slug] = page_obj
        elif isinstance(raw_pages, dict):
            pages_in = raw_pages
        else:
            return {}

        # Phase 47.29: deterministic page-key repair. Weak models ignore
        # the page map keys ("/home", "/Restaurant", case/spacing drift).
        # Keys are remapped onto the architecture's authoritative page
        # routes (exact, then case/slash-insensitive); a single returned
        # page lands on home when home was requested. Unmatched extra
        # pages are kept as-is (harmless); first occurrence wins.
        expected_routes = []
        hierarchy = getattr(getattr(artifact, 'architecture', None),
                            'component_hierarchy', None) or {}
        for page in hierarchy.values():
            if isinstance(page, dict) and page.get('type') == 'page':
                route = page.get('path') or '/'
                if route not in expected_routes:
                    expected_routes.append(route)
        if expected_routes:
            expected_lower = {
                route.lower().rstrip('/'): route
                for route in expected_routes}
            # Architecture-owned page names (page_home -> 'home') give a
            # second deterministic signal for keys like "/home".
            name_to_route = {}
            for comp_id, page in hierarchy.items():
                if isinstance(page, dict) and page.get('type') == 'page':
                    route = page.get('path') or '/'
                    name = str(comp_id)
                    if name.startswith('page_'):
                        name = name[len('page_'):]
                    name_to_route.setdefault(name.lower().strip('_'),
                                             route)
            remapped = {}
            has_unmatched = False
            for key, page_obj in pages_in.items():
                new_key = key
                if key not in expected_routes:
                    bare = str(key).lower().strip('/')
                    candidate = (expected_lower.get(bare)
                                 or name_to_route.get(bare))
                    if candidate:
                        new_key = candidate
                    else:
                        has_unmatched = True
                remapped.setdefault(new_key, page_obj)
            # A SINGLE page whose key matched no expected route is the
            # classic weak-model collapse (one page for a multi-page
            # site): it lands on home when home was requested. Multiple
            # unmatched pages are preserved untouched (no guessing).
            if ('/' in expected_routes and '/' not in remapped
                    and len(remapped) == 1 and has_unmatched):
                remapped['/'] = remapped.pop(next(iter(remapped)))
            pages_in = remapped

        normalized = {"pages": {}}
        req = artifact.requirements
        for slug, page_obj in pages_in.items():
            if not isinstance(page_obj, dict):
                continue

            # SEO derivation ONLY applies to the natural list shape (which
            # structurally carries no seo — deriving it is normalization, not
            # schema loosening). A canonical dict-shape page that is missing
            # seo entirely is a genuine schema violation: keep it missing so
            # _validate_schema rejects and the deterministic fallback runs.
            seo_title = ''
            seo_desc = ''
            explicit_seo = page_obj.get("seo") if isinstance(page_obj.get("seo"), dict) else None
            if explicit_seo is not None:
                seo_title = str(explicit_seo.get("title") or '')
                seo_desc = str(explicit_seo.get("description") or '')
            elif from_list_shape:
                hero = next((s for s in (page_obj.get("sections") or [])
                             if isinstance(s, dict) and str(s.get("type", "")).lower() == "hero"), None)
                if hero:
                    editable = hero.get("editable") if isinstance(hero.get("editable"), dict) else {}
                    headline = ContentEngine._editable_value(editable, "headline")
                    subheadline = ContentEngine._editable_value(editable, "subheadline")
                    if headline:
                        seo_title = headline[:80]
                    if subheadline:
                        seo_desc = subheadline[:200]
                if not seo_title:
                    site_name = (content.get("site") or {}).get("business_name") \
                        if isinstance(content.get("site"), dict) else ''
                    seo_title = str(site_name or req.domain)[:80]
                if not seo_desc:
                    seo_desc = "Welcome to " + (req.domain or "our site")
            if seo_title and not seo_desc:
                # Canonical shape with a title but no description: fill the
                # description from the title (field-level completeness), but
                # a missing title remains a validation failure.
                seo_desc = seo_title[:200]
            if not seo_title:
                continue

            canonical_sections = []
            for sec in (page_obj.get("sections") or []):
                if not isinstance(sec, dict):
                    continue
                sec_type = str(sec.get("type") or "Content")
                editable = sec.get("editable") if isinstance(sec.get("editable"), dict) else {}

                heading = (
                    ContentEngine._editable_value(editable, "heading")
                    or ContentEngine._editable_value(editable, "headline")
                    or (str(sec.get("semantic_heading")) if sec.get("semantic_heading") else '')
                    or (sec_type + " Section")
                )
                body = (
                    ContentEngine._editable_value(editable, "body")
                    or ContentEngine._editable_value(editable, "subheadline")
                    or (str(sec.get("body")) if sec.get("body") else '')
                )
                # Optional list items become additional body lines so real LLM
                # list content survives (labels + values are real copy).
                items = editable.get("list")
                if isinstance(items, list) and items:
                    lines = []
                    for item in items:
                        if isinstance(item, dict):
                            label = str(item.get("label") or '').strip()
                            value = str(item.get("value") or '').strip()
                            if label and value:
                                lines.append("%s: %s" % (label, value))
                            elif value:
                                lines.append(value)
                        elif isinstance(item, str) and item.strip():
                            lines.append(item.strip())
                    if lines:
                        body = (body + "\n\n" + "\n".join(lines)).strip() if body else "\n".join(lines)

                # Phase 47.29: the prompt's instructed prose-block fallback
                # (for models that omit items) is normalized back into
                # canonical structured items here — the ContentArtifact
                # boundary — so ADR-0079 structured composition survives
                # model variation. Only applied for the structured section
                # types and only under strict grammar.
                items = self._normalize_section_items(sec, editable)
                if not items:
                    items = self._items_from_body_blocks(sec_type, body)

                canonical_sections.append({
                    "type": sec_type,
                    "semantic_heading": heading[:80],
                    "aria_label": str(sec.get("aria_label") or (sec_type + " section")),
                    "body": body[:2000],
                    "items": items,
                })

            metadata = page_obj.get("metadata") if isinstance(page_obj.get("metadata"), dict) else {}
            metadata.setdefault("status", "draft")

            normalized["pages"][slug] = {
                "seo": {"title": seo_title, "description": seo_desc},
                "metadata": metadata,
                "sections": canonical_sections,
            }

        return normalized

    @staticmethod
    def _editable_value(editable: Dict[str, Any], key: str) -> str:
        """Extract an editable field's text: {key: {value: ...}} or plain string."""
        val = editable.get(key)
        if isinstance(val, dict):
            val = val.get("value")
        if val is None:
            return ''
        return str(val)

    @staticmethod
    def _normalize_section_items(sec: Dict[str, Any], editable: Dict[str, Any]) -> List[Dict[str, str]]:
        """Phase 47.27 (ADR-0079) / 47.29: canonical structured items for a
        section.

        Accepts the LLM's natural item shapes (items/list/faqs/plans/menu/
        products, at the section level or inside editable) and maps each
        entry onto the canonical item keys (title, body, price, badge,
        category, question, answer). Phase 47.29 additionally repairs the
        observed weaker-model shapes deterministically: list containers
        that arrive as objects ({"1": {...}}), nested natural objects
        ({"plan": {"name": ..., "price": ...}}), and "Name - price"
        string entries. Bounded (8 items, 200-char fields). Returns []
        when the section carries no structured items — sections without
        items remain fully backward compatible.
        """
        raw = None
        for source in (sec, editable):
            for key in _ITEM_LIST_KEYS:
                candidate = source.get(key)
                if isinstance(candidate, list) and candidate:
                    raw = candidate
                    break
                if isinstance(candidate, dict) and candidate:
                    # Phase 47.29: object-shaped container ({"0": {...}}) —
                    # a natural weak-model shape; values are the items.
                    values = [v for v in candidate.values()
                              if isinstance(v, (dict, str)) and v]
                    if values:
                        raw = values
                        break
            if raw:
                break
        if not raw:
            return []

        items = []
        for entry in raw[:8]:
            if isinstance(entry, str):
                text = entry.strip()
                if not text:
                    continue
                parsed = ContentEngine._parse_priced_string(text)
                if parsed:
                    items.append(parsed)
                else:
                    items.append({'title': text[:80], 'body': ''})
                continue
            if not isinstance(entry, dict):
                continue
            # Phase 47.29: pre-flatten nested natural objects into the
            # search space ({"plan": {"name": "Pro", "price": "$10"}} →
            # name/price at top level) so nested weak-model shapes keep
            # every field. Only scalar leaves merge; {'value': ...}
            # editable wrappers stay for _coerce_item_value.
            search = dict(entry)
            for _key, _val in entry.items():
                if isinstance(_val, dict) and 'value' not in _val:
                    for _sub_key, _sub_val in _val.items():
                        if (isinstance(_sub_val, (str, int, float))
                                and not isinstance(_sub_val, bool)
                                and _sub_key not in search):
                            search[_sub_key] = _sub_val
            item = {}
            for canonical_key, aliases in _ITEM_KEY_ALIASES.items():
                for alias in aliases:
                    val = ContentEngine._coerce_item_value(
                        search.get(alias), aliases)
                    if val is None:
                        continue
                    text = str(val).strip()
                    if text:
                        item[canonical_key] = text[:200]
                        break
            if item:
                items.append(item)
        return items

    @staticmethod
    def _coerce_item_value(val: Any, aliases: tuple) -> Any:
        """Resolve an item field's value: {key: {value: ...}} or a nested
        natural object carrying the SAME alias group's keys
        ({"plan": {"name": "Pro", "price": "$10"}} — Phase 47.29; the
        group-aware scan keeps 'name' from leaking into 'price')."""
        if val is None:
            return None
        if isinstance(val, dict):
            if 'value' in val:
                return val.get('value')
            # Nested natural object: resolve through this field's own
            # alias group only.
            for alias in aliases:
                nested = val.get(alias)
                if nested is not None and not isinstance(nested, (dict, list)):
                    return nested
            return None
        if isinstance(val, list):
            # A list-shaped field (e.g. features: ["a","b"]) flattens to a
            # semicolon-joined string — the canonical feature-list form.
            flat = [str(v).strip() for v in val
                    if v is not None and not isinstance(v, (dict, list))
                    and str(v).strip()]
            return '; '.join(flat) if flat else None
        return val

    @staticmethod
    def _parse_priced_string(text: str) -> Optional[Dict[str, str]]:
        """Deterministic \"Name - price\" string-item repair (Phase 47.29).

        Applies only when the right side of a separator is price-like
        (contains a digit and/or currency symbol) so ordinary prose titles
        are never misread as priced items."""
        for sep in (' — ', ' - ', ' – ', ': '):
            if sep not in text:
                continue
            name, _, price = text.partition(sep)
            name, price = name.strip(), price.strip()
            if name and price and _PRICEISH_RE.search(price):
                return {'title': name[:80], 'price': price[:40]}
        return None

    @staticmethod
    def _items_from_body_blocks(section_type: str, body: str) -> List[Dict[str, str]]:
        """Phase 47.29: deterministic prose-block repair for the structured
        sections. The prompt instructs weaker models to fall back to the
        blank-line-separated block format (\"Plan name - price\" + feature
        lines, Q&A blocks, \"Item name - price\" + description line) when
        they omit items; this normalizes that instructed format BACK into
        canonical items at the ContentArtifact boundary so the structured
        composition path (ADR-0079) survives model variation. Strict
        grammar only: priced blocks require a price-like right side, FAQ
        blocks require a question-mark first line. Bounded, deterministic,
        no LLM call.
        """
        sec = str(section_type or '').strip().lower()
        if sec not in ('pricing', 'faq', 'menuhighlights'):
            return []
        blocks = [b.strip() for b in (body or '').split('\n\n') if b.strip()]
        if not blocks:
            return []
        items: List[Dict[str, str]] = []
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue
            first = lines[0]
            if sec == 'faq':
                if '?' not in first:
                    continue
                question = first[:200]
                answer = ' '.join(lines[1:])[:400]
                items.append({'question': question, 'answer': answer})
                continue
            parsed = ContentEngine._parse_priced_string(first)
            if not parsed:
                continue
            item = {'title': parsed['title'][:80], 'price': parsed['price'][:40]}
            rest = [l for l in lines[1:]]
            if rest:
                item['body'] = ' '.join(rest)[:200]
            items.append(item)
            if len(items) >= 8:
                break
        return items

    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ContentEngine (Deterministic + Schema Validation)...")

        req = artifact.requirements
        pages_structure = {}

        component_hierarchy = artifact.architecture.component_hierarchy if hasattr(artifact.architecture, "component_hierarchy") else {}
        for comp_id, comp_data in component_hierarchy.items():
            if comp_data.get("type") != "page": continue
            path = comp_data.get("path", "/")
            pages_structure[path] = comp_data.get("sections", ["Hero", "Content"])

        payload = {
            "prompt": (
                f"Generate structured editable content for {req.domain}. "
                f"Page map: {json.dumps(pages_structure)}. {_CONTENT_SCHEMA_PROMPT}"
            ),
            # Phase 47.18 (Part C): structured generation context so the
            # content reflects the actual client brief and the REAL research
            # gathered by the source framework. Bounded digests — provenance
            # preserved, no raw dumps, irrelevant data cannot dominate.
            "business": self._business_context(artifact),
            "research": self._research_digest(artifact),
            "knowledge": self._knowledge_digest(artifact),
            "response_format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "pages": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "seo": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "description": {"type": "string"}
                                        },
                                        "required": ["title", "description"]
                                    },
                                    "metadata": {"type": "object"},
                                    "sections": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "semantic_heading": {"type": "string"},
                                                "aria_label": {"type": "string"},
                                                "body": {"type": "string"},
                                                "items": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "title": {"type": "string"},
                                                            "body": {"type": "string"},
                                                            "price": {"type": "string"},
                                                            "badge": {"type": "string"},
                                                            "category": {"type": "string"},
                                                            "question": {"type": "string"},
                                                            "answer": {"type": "string"}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                "required": ["seo", "metadata", "sections"]
                            }
                        }
                    },
                    "required": ["pages"]
                }
            }
        }

        result = runtime.ai.generate("generate_content", payload)

        # Phase 47.20C: real providers return the JSON payload as a string
        # (result['analysis'] == result['response'] — see AIProviderManager
        # engine-boundary normalization) which may be fenced; mocks/tests may
        # return a parsed dict. Extract deterministically, then normalize the
        # LLM's natural shape into the canonical schema before validation.
        parsed = self._extract_json_payload(result.get("analysis", {}))
        if not parsed:
            parsed = self._extract_json_payload(result.get("response", ""))
        parsed = self._normalize_content_schema(parsed, artifact)

        fallback_reason = None
        if not self._validate_schema(parsed):
            fallback_reason = "ai_content_schema_validation_failed"
            _logger.warning(
                "AI Content generation failed schema validation (%s). "
                "Falling back to deterministic generation.", fallback_reason)
            parsed = {"pages": {}}
            for comp_id, comp_data in component_hierarchy.items():
                if comp_data.get("type") != "page": continue
                path = comp_data.get("path", "/")
                sections = comp_data.get("sections", ["Hero", "Content"])
                parsed["pages"][path] = {
                    "seo": {"title": req.domain + " - " + path, "description": "Welcome to " + req.domain},
                    "metadata": {"status": "draft"},
                    "sections": [
                        {
                            "type": sec,
                            "semantic_heading": "h2",
                            "aria_label": sec + " section",
                            "body": "Editable content for " + sec,
                            "items": []
                        } for sec in sections
                    ]
                }

        model = Content(pages=parsed.get("pages", {}))
        metadata = {}
        # Phase 47.29: bounded structured-content evidence — how many
        # structured items (Pricing/FAQ/MenuHighlights/…) survived into
        # the ContentArtifact (integer only, no payload copies).
        structured_items = sum(
            len(page.get('items') or [])
            for page_data in (parsed.get("pages") or {}).values()
            for page in (page_data.get('sections') or [])
            if isinstance(page, dict))
        if structured_items:
            metadata["content_structured_items"] = structured_items
        if fallback_reason:
            # Phase 47.20C: fallback reason is observable in engine metadata
            # (no secrets — a stable reason code only).
            metadata["content_fallback_reason"] = fallback_reason
        return EngineExecutionResult(success=True, artifact=artifact.evolve(content=model), metadata=metadata, error=None)
