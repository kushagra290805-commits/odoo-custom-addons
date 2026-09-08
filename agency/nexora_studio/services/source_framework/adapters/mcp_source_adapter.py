# -*- coding: utf-8 -*-
"""
McpSourceAdapter — Phase 29 Pure Translation Layer
===================================================
Maps Phase 29 CSF (Component Source Framework) intents to Phase 28 ConnectorRuntime
dispatch calls. This adapter NEVER:
  - starts subprocesses
  - creates MCP clients
  - manages transport
  - decrypts credentials
  - accesses nexora.mcp_credential directly
  - manages MCP lifecycle
  - creates a second capability registry

The only execution boundary is:
    McpSourceAdapter
        ↓
    ConnectorRuntime.dispatch()
        ↓
    Phase 28 transport

Semantic Tool Routing (Resolution Design — ADR-0052 §8)
-------------------------------------------------------
MCP tools have provider-specific names (e.g. 'search', 'search_web', 'find_libraries').
This adapter resolves semantic intents against the actual discovered tools persisted in
nexora.mcp_discovered_tool records, using a declarative capability_map stored as JSON
in the source_registry record's config_json (non-credential section only).

Format of capability_map in config_json (example):
    {
        "capability_map": {
            "search": "search_web",
            "get":    "get_repository"
        }
    }

If no capability_map is configured, the semantic intent name is passed directly as the
MCP tool name. This matches simple servers (e.g. @modelcontextprotocol/server-memory)
without requiring any mapping.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union

from .base_adapter import BaseProviderAdapter
from ..domain_models import (
    BusinessData, ComponentPackage, DesignAsset,
    KnowledgeDocument, Provenance, RepositoryArtifact,
)

_logger = logging.getLogger(__name__)


class McpSourceAdapter(BaseProviderAdapter):
    """
    Phase 29 translation layer for MCP-backed sources.
    Delegates exclusively to Phase 28 ConnectorRuntime.dispatch().
    """

    def __init__(self, connector_id: int, env: Any, config: Optional[Dict[str, Any]] = None,
                 source_row: Optional[Any] = None):
        super().__init__(None, config)
        self.connector_id = connector_id
        self.env = env
        # Phase 45 (ADR-0072): several sources may share ONE connector. When the
        # loader knows the exact registry row it passes it here so per-source
        # configuration resolves unambiguously instead of first-match.
        self._source_row = source_row
        # Phase 44.2 closure (C-26 / P11): execution goes through the
        # canonical router (build_canonical_router in _execute), which wires
        # ConnectorExecutionTarget itself. Availability of the platform is
        # checked via the same accessor the router uses.
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
        if not get_connector_runtime():
            raise RuntimeError("ConnectorRuntime is not available.")
        self._capability_map: Optional[Dict[str, str]] = None
        self._default_payload: Optional[Dict[str, Any]] = None
        self._payload_mapping: Optional[Dict[str, Dict[str, str]]] = None
        self._normalization_map: Optional[Dict[str, str]] = None
        self._declared_capabilities: Optional[List[str]] = None
        self._source_technical_name: Optional[str] = None
        self._discovery_config: Optional[Dict[str, Any]] = None
        self._qualification: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Capability routing
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> List[str]:
        """Declared semantic CSF capability tokens for this source.

        Phase 45 (ADR-0072, F-01): returns the tokens declared on the linked
        ``nexora.source_registry.capabilities`` CSV field (normative vocabulary:
        SEARCH / FETCH / COMPONENT_SOURCE / REPOSITORY_INTELLIGENCE).

        Concrete MCP tool names are execution details and are deliberately NOT
        exposed here — federated search filters adapters by semantic capability.
        Use :meth:`_discovered_tools` for the concrete execution surface.
        """
        self._ensure_config_loaded()
        return list(self._declared_capabilities or [])

    def _discovered_tools(self) -> List[str]:
        """Concrete MCP tools available on the connector (execution-level view)."""
        if not self.connector_id:
            return []
        connector = self.env['nexora.connector'].browse(self.connector_id)
        # Primary source: discovered tools from Phase 28 capability discovery
        discovered = self.env['nexora.mcp_discovered_tool'].search([
            ('connector_id', '=', self.connector_id)
        ])
        if discovered:
            return [t.tool_name for t in discovered]
        # Fallback: connector capability_ids if discovery not yet run
        return [cap.technical_name for cap in connector.capability_ids]

    def _ensure_config_loaded(self) -> None:
        if self._capability_map is not None:
            return

        self._capability_map = {}
        self._default_payload = {}
        self._declared_capabilities = []
        self._discovery_config = {}
        self._qualification = {}
        self._text_result_format = {}
        connector = self.env['nexora.connector'].browse(self.connector_id)
        # Resolve THIS source's registry row: prefer the explicit row handed
        # over by the loader; fall back to first-match on the connector
        # (legacy single-source-per-connector behavior).
        registry_rec = getattr(self, '_source_row', None)
        if registry_rec is None:
            registry_rec = self.env['nexora.source_registry'].search(
                [('connector_id.id', '=', self.connector_id)], limit=1
            )
        if registry_rec:
            self._source_technical_name = registry_rec.technical_name
            raw_caps = registry_rec.capabilities or ''
            self._declared_capabilities = [
                c.strip() for c in raw_caps.split(',') if c.strip()
            ]
            if registry_rec.config_json:
                try:
                    parsed = json.loads(registry_rec.config_json)
                    self._capability_map = parsed.get('capability_map', {})
                    default_payload = parsed.get('default_payload', {})
                    if isinstance(default_payload, dict):
                        self._default_payload = default_payload
                    else:
                        _logger.warning("McpSourceAdapter: default_payload must be a dict")

                    self._payload_mapping = parsed.get('payload_mapping', {})
                    self._normalization_map = parsed.get('normalization', {})
                    self._discovery_config = parsed.get('discovery', {})
                    self._qualification = parsed.get('qualification', {})
                    text_fmt = parsed.get('text_result_format', {})
                    if isinstance(text_fmt, dict):
                        self._text_result_format = text_fmt
                except (json.JSONDecodeError, AttributeError):
                    _logger.warning(
                        "McpSourceAdapter: invalid config_json for connector %s",
                        self.connector_id
                    )

    def _resolve_tool_name(self, semantic_intent: str) -> str:
        """
        Resolves a semantic intent ('search', 'get', etc.) to the actual MCP
        tool name using a declarative capability_map from config_json.

        Falls back to the intent name itself if no mapping is configured.
        Never hardcodes provider-specific tool names.
        """
        self._ensure_config_loaded()
        return self._capability_map.get(semantic_intent, semantic_intent)

    def _execute(self, semantic_intent: str, params: Dict[str, Any]) -> Any:
        """
        Resolve intent → MCP tool name → validate against discovered tools
        → execute through the canonical router chain.

        Phase 44.2 closure (C-26 / P11): this adapter previously built its own
        ConnectorExecutionRequest and called ConnectorRuntime.dispatch()
        directly — a parallel entry point bypassing policy/security. Execution
        now traverses the same chain as every other caller:

            UniversalCapabilityRouter → ConnectorExecutionTarget
            → ConnectorRuntime → ConnectorDispatcher → McpConnector …

        using the "{connector_id}.{tool_name}" shorthand of ADR-0069.
        """
        connector = self.env['nexora.connector'].browse(self.connector_id)

        tool_name = self._resolve_tool_name(semantic_intent)

        # Guard: concrete tool must be present in the discovered execution set
        available = self._discovered_tools()
        if available and tool_name not in available:
            raise ValueError(
                f"Tool '{tool_name}' (resolved from intent '{semantic_intent}') "
                f"is not in discovered capabilities for connector {self.connector_id}. "
                f"Available: {available}"
            )

        # Merge source-bound configuration payload with runtime params.
        # Precedence: Source defaults override runtime parameters to preserve source isolation.
        final_payload = dict(params)

        # Apply generic payload mapping if configured for this intent
        if self._payload_mapping and semantic_intent in self._payload_mapping:
            mapping = self._payload_mapping[semantic_intent]
            for target_key, source_key in mapping.items():
                if source_key in params:
                    final_payload[target_key] = params[source_key]

        if self._default_payload:
            final_payload.update(self._default_payload)

        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import (
            build_canonical_router,
        )

        router = build_canonical_router(self.env)
        result = router.execute(
            f"{connector.connector_id}.{tool_name}",
            {"inputs": final_payload},
            context={
                'connector_id': connector.connector_id,
                'session_id': 'csf',
            },
        )
        if not result.success:
            raise RuntimeError(
                f"Connector execution failed for tool '{tool_name}': "
                f"{' | '.join(result.logs) if result.logs else 'unknown error'}"
            )
        return result.result

    # ------------------------------------------------------------------
    # Normalization (§6 Decision)
    # ------------------------------------------------------------------

    def _normalize(self, raw: Any) -> Any:
        """
        Normalise raw MCP tool output to a typed domain model where confidence
        is sufficient. Preserves raw output otherwise.
        """
        # 1. MCP Standard Content Envelope Unwrapping
        if isinstance(raw, dict) and 'content' in raw and isinstance(raw['content'], list) and len(raw['content']) > 0:
            first = raw['content'][0]
            if isinstance(first, dict) and first.get('type') == 'text' and 'text' in first:
                try:
                    import json
                    unwrapped = json.loads(first['text'])
                    # If the JSON payload wraps items in an 'items' array (e.g. GitHub search pagination), unwrap it generically.
                    if isinstance(unwrapped, dict) and 'items' in unwrapped and isinstance(unwrapped['items'], list):
                        unwrapped = unwrapped['items']
                    return self._normalize(unwrapped)
                except (json.JSONDecodeError, TypeError):
                    # Phase 47.16: some MCP servers return human-readable text
                    # instead of JSON. When the source declares a
                    # text_result_format, parse the "Field: value" blocks into
                    # dicts and normalize each through the standard chain
                    # (field mapping -> structural heuristics -> domain
                    # model). Fully config-driven; no provider names.
                    text_blocks = self._parse_text_blocks(first['text'])
                    if text_blocks is not None:
                        return [self._normalize(item) for item in text_blocks]
                    return first['text']

        if isinstance(raw, list):
            return [self._normalize(item) for item in raw]

        if not isinstance(raw, dict):
            return raw  # preserve scalars/None as-is

        # 2. Generic Field Normalization mapping
        if getattr(self, '_normalization_map', None):
            mapped_raw = dict(raw)
            for target_field, source_field in self._normalization_map.items():
                if source_field in raw:
                    mapped_raw[target_field] = raw[source_field]
            raw = mapped_raw

        try:
            # Explicit type discriminant takes precedence
            discriminant = raw.get('_type')
            if discriminant == 'component':
                return ComponentPackage(**{k: v for k, v in raw.items() if k in ComponentPackage.__dataclass_fields__})
            if discriminant == 'document':
                return KnowledgeDocument(**{k: v for k, v in raw.items() if k in KnowledgeDocument.__dataclass_fields__})
            if discriminant == 'design_asset':
                return DesignAsset(**{k: v for k, v in raw.items() if k in DesignAsset.__dataclass_fields__})
            if discriminant == 'repository_artifact':
                return RepositoryArtifact(**{k: v for k, v in raw.items() if k in RepositoryArtifact.__dataclass_fields__})
            if discriminant == 'business_data':
                return BusinessData(**{k: v for k, v in raw.items() if k in BusinessData.__dataclass_fields__})

            # Structural heuristics (sufficient-confidence only)
            if 'component_id' in raw and 'name' in raw:
                return ComponentPackage(**{k: v for k, v in raw.items() if k in ComponentPackage.__dataclass_fields__})
            if 'document_id' in raw and 'title' in raw and 'content' in raw:
                return KnowledgeDocument(**{k: v for k, v in raw.items() if k in KnowledgeDocument.__dataclass_fields__})
            if 'asset_id' in raw and 'name' in raw and 'type' in raw:
                return DesignAsset(**{k: v for k, v in raw.items() if k in DesignAsset.__dataclass_fields__})
            if 'artifact_id' in raw and 'path' in raw:
                return RepositoryArtifact(**{k: v for k, v in raw.items() if k in RepositoryArtifact.__dataclass_fields__})
            if 'data_id' in raw and 'category' in raw:
                return BusinessData(**{k: v for k, v in raw.items() if k in BusinessData.__dataclass_fields__})

        except (TypeError, KeyError) as exc:
            _logger.warning(
                "McpSourceAdapter: normalization failed (%s), preserving raw payload: %s",
                exc, list(raw.keys())
            )

        # Insufficient confidence — return raw to preserve fidelity
        return raw

    def _parse_text_blocks(self, text: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """Phase 47.16: parse a human-readable "Field: value" text response
        into structured dicts when the source declares a
        ``text_result_format`` config::

            "text_result_format": {
                "block_start_field": "Title",
                "fields": ["Title", "ID", "URL", "Content"]
            }

        Blocks start at each ``<block_start_field>:`` line; continuation
        lines append to the previously matched field. The resulting dicts
        flow through the standard normalization chain (field mapping ->
        structural heuristics -> domain model), so no provider-specific
        logic exists here. Returns None when the format is not configured
        or nothing could be parsed (caller preserves the raw text).
        """
        fmt = getattr(self, '_text_result_format', None) or {}
        start_field = fmt.get('block_start_field')
        fields = fmt.get('fields') or []
        if not start_field or not fields:
            return None

        blocks: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        last_key: Optional[str] = None
        for line in (text or '').splitlines():
            matched_field = None
            value = None
            for field in fields:
                prefix = str(field) + ':'
                if line.startswith(prefix):
                    matched_field = field
                    value = line[len(prefix):].strip()
                    break
            if matched_field == start_field:
                if current:
                    blocks.append(current)
                current = {matched_field: value}
                last_key = matched_field
            elif matched_field is not None:
                if current is None:
                    current = {}
                current[matched_field] = value
                last_key = matched_field
            else:
                # Continuation line: append to the last matched field.
                if current is not None and last_key and line.strip():
                    current[last_key] = (current.get(last_key) or '') + '\n' + line.rstrip()
        if current:
            blocks.append(current)
        return blocks or None

    # ------------------------------------------------------------------
    # BaseProviderAdapter interface — delegates to _execute + _normalize
    # ------------------------------------------------------------------

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Any:
        params = {'query': query}
        if filters:
            params.update(filters)
        return self._normalize(self._execute('search', params))

    # ------------------------------------------------------------------
    # Repository intelligence (ADR-0072 decision 3a)
    # ------------------------------------------------------------------

    def _build_provenance(self, raw: Dict[str, Any]) -> Provenance:
        """Build canonical provenance from a normalized tool result.

        Only fields factually present on the result are populated; nothing is
        invented. Provider identity is the source's technical_name.
        """
        self._ensure_config_loaded()
        return Provenance(
            provider=self._source_technical_name or 'unknown',
            repository=raw.get('repository') or raw.get('full_name'),
            commit_sha=raw.get('sha') or raw.get('commit_sha'),
            release_version=raw.get('version') or raw.get('release'),
            license=raw.get('license'),
            import_source='csf:%s' % (self._source_technical_name or 'unknown'),
        )

    def fetch_repository_artifacts(
        self, intent: str = 'repo_search', params: Optional[Dict[str, Any]] = None
    ) -> List[RepositoryArtifact]:
        """REPOSITORY_INTELLIGENCE retrieval returning canonical artifacts.

        Executes the configured capability_map intent through the same router
        chain as every other adapter call and normalizes results into
        ``RepositoryArtifact`` domain models.

        Ordering note: result order is the MCP/tool **retrieval ordering** —
        it carries NO component-ranking semantics (repo artifacts deliberately
        bypass ComponentRankingPipeline, whose contract is ComponentPackage).
        """
        merged: Dict[str, Any] = dict(params or {})
        normalized = self._normalize(self._execute(intent, merged))
        items = normalized if isinstance(normalized, list) else [normalized]

        artifacts: List[RepositoryArtifact] = []
        for item in items:
            if isinstance(item, RepositoryArtifact):
                item.artifact_id = str(item.artifact_id)
                if not getattr(item, 'provenance', None):
                    item.provenance = self._build_provenance(
                        {'full_name': item.path})
                artifacts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            artifact_id = item.get('artifact_id') or item.get('id') or item.get('full_name')
            path = item.get('path') or item.get('full_name')
            if not artifact_id or not path:
                # Cannot form a canonical artifact — skip rather than fabricate.
                continue
            metadata = {k: v for k, v in item.items()
                        if k not in ('artifact_id', 'path', 'content', 'type')}
            artifacts.append(RepositoryArtifact(
                artifact_id=str(artifact_id),
                path=str(path),
                content=item.get('content'),
                type=item.get('type', 'file'),
                metadata=metadata,
                provenance=self._build_provenance(item),
            ))
        return artifacts

    # ------------------------------------------------------------------
    # Component-source ingestion chain (ADR-0072 decision 3)
    # ------------------------------------------------------------------

    def discover_components(self, params: Optional[Dict[str, Any]] = None) -> List[ComponentPackage]:
        """COMPONENT_SOURCE ingestion: discovery → FETCH → qualification → package.

        Entirely config-driven via ``config_json`` blocks:

        ``discovery``     — ``intent`` (capability_map key) plus fixed payload
                            (e.g. query/owner/repo/limit).
        ``qualification`` — declarative gates; a candidate becomes a
                            ``ComponentPackage`` ONLY if it passes all of them:
              ``candidate_path_pattern``  regex against the candidate path
              ``content_required_any``    substrings required in fetched content
              ``required_dependencies``   validated ONLY against dependency info
                                          actually present on the candidate /
                                          its package metadata (never invented;
                                          when no dependency info exists the
                                          gate is skipped)
              ``fetch_intent``            capability_map key used to retrieve
                                          artifact content (default ``fetch``)
              ``metadata``                attached verbatim to qualifying
                                          packages (ADR-0064 vocabulary keys)

        Bare repository/search results can never become packages: a candidate
        must survive the path filter, the content gate and (when dependency
        information exists) the dependency gate.
        """
        self._ensure_config_loaded()
        import re

        disc = dict(self._discovery_config or {})
        qual = dict(self._qualification or {})
        intent = disc.get('intent', 'discover')
        payload = {k: v for k, v in disc.items() if k != 'intent'}
        if params:
            payload.update(params)

        raw = self._normalize(self._execute(intent, payload))
        items = raw if isinstance(raw, list) else [raw]

        pattern = qual.get('candidate_path_pattern')
        regex = re.compile(pattern) if pattern else None
        required_any = qual.get('content_required_any') or []
        required_deps = qual.get('required_dependencies') or []
        meta_overlay = dict(qual.get('metadata') or {})
        fetch_intent = qual.get('fetch_intent', 'fetch')

        packages: List[ComponentPackage] = []
        for cand in items:
            if not isinstance(cand, dict):
                continue
            path = str(cand.get('path') or cand.get('full_name') or '')
            if regex and not regex.search(path):
                _logger.info("discover_components: candidate rejected by path filter: %s", path)
                continue

            fetch_payload = {'path': path}
            for target_key, source_key in (self._payload_mapping or {}).get(fetch_intent, {}).items():
                if source_key in cand:
                    fetch_payload[target_key] = cand[source_key]
            fetched = self._normalize(self._execute(fetch_intent, fetch_payload))
            content = None
            if isinstance(fetched, str):
                content = fetched
            elif isinstance(fetched, dict):
                content = fetched.get('content') or fetched.get('text')

            if required_any and not any(tok in (content or '') for tok in required_any):
                _logger.info("discover_components: candidate rejected by content gate: %s", path)
                continue

            deps_raw = cand.get('dependencies') if isinstance(cand.get('dependencies'), dict) else None
            dependencies = [{'name': k, 'version': v} for k, v in (deps_raw or {}).items()]
            if required_deps and deps_raw is not None:
                missing = [d for d in required_deps if d not in deps_raw]
                if missing:
                    _logger.info(
                        "discover_components: candidate rejected, missing deps %s: %s",
                        missing, path)
                    continue

            pkg_metadata: Dict[str, Any] = {}
            if content:
                pkg_metadata['source_code'] = content
            pkg_metadata.update(meta_overlay)

            provenance = self._build_provenance(dict(cand, path=path))
            packages.append(ComponentPackage(
                component_id=path,
                name=cand.get('name') or path.rsplit('/', 1)[-1],
                description=cand.get('description'),
                metadata=pkg_metadata,
                dependencies=dependencies,
                provenance=provenance,
            ))
        return packages

    # ------------------------------------------------------------------
    # Business-location intelligence (ADR-0073 / Phase 46)
    # ------------------------------------------------------------------

    def search_businesses(
        self, queries: List[str], limit_per_query: int = 16,
        lang: str = "", include_reviews: bool = False
    ) -> List[BusinessData]:
        """BUSINESS_SEARCH retrieval returning canonical BusinessData models.

        Executes the gosom business_search tool through the router chain,
        normalizes the JSON result list into ``BusinessData`` domain objects
        with provenance attached.
        """
        payload: Dict[str, Any] = {
            'queries': queries,
            'limit_per_query': limit_per_query,
            'lang': lang,
            'include_reviews': include_reviews,
        }
        raw = self._execute('business_search', payload)

        # MCP tools.call envelope: {"content": [...], "isError": bool}.
        # Shim-side failures (bounds violations, job timeouts, terminal job
        # states) surface as isError=True — raise instead of silently
        # returning an empty list.
        if isinstance(raw, dict) and raw.get('isError'):
            text = ''
            content = raw.get('content') or []
            if content and isinstance(content[0], dict):
                text = content[0].get('text', '')
            raise RuntimeError(
                "business_search tool error: %s" % (text or 'unknown error'))

        # Tolerate bare JSON-string results alongside the canonical envelope.
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                raise RuntimeError(
                    "business_search returned unparsable output")

        # Envelope unwrapping + _type discriminant normalization (the
        # normalizer parses the JSON text payload and constructs
        # BusinessData instances directly).
        normalized = self._normalize(raw)
        items = normalized if isinstance(normalized, list) else [normalized]

        results: List[BusinessData] = []
        for item in items:
            if isinstance(item, BusinessData):
                if not getattr(item, 'provenance', None):
                    item.provenance = self._build_provenance(
                        {'full_name': item.data_id})
                results.append(item)
                continue
            if not isinstance(item, dict):
                continue
            data_id = item.get('data_id') or item.get('place_id') or item.get('id')
            category = item.get('category', 'business_place')
            if not data_id:
                continue
            payload_data = item.get('payload') if isinstance(item.get('payload'), dict) else item
            results.append(BusinessData(
                data_id=str(data_id),
                category=category,
                payload=payload_data,
                provenance=self._build_provenance(item),
            ))
        return results

    def get_component(self, component_id: str) -> Any:
        from ..domain_models import ComponentPackage
        normalized = self._normalize(self._execute('get', {'id': component_id}))
        if isinstance(normalized, str):
            return ComponentPackage(
                component_id=component_id,
                name=component_id,
                description=normalized
            )
        if isinstance(normalized, dict):
            description = normalized.get('content', normalized.get('text', str(normalized)))
            return ComponentPackage(
                component_id=component_id,
                name=normalized.get('name', component_id),
                description=description
            )
        return normalized

    def get_metadata(self, component_id: str) -> Dict[str, Any]:
        return self._execute('get_metadata', {'id': component_id})

    def get_preview(self, component_id: str) -> Dict[str, Any]:
        return self._execute('get_preview', {'id': component_id})

    def get_dependencies(self, component_id: str) -> List[Dict[str, Any]]:
        return self._execute('get_dependencies', {'id': component_id})

    def get_license(self, component_id: str) -> str:
        return self._execute('get_license', {'id': component_id})

    def get_installation_guide(self, component_id: str) -> str:
        return self._execute('get_installation_guide', {'id': component_id})
