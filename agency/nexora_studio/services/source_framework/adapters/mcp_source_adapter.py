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
    KnowledgeDocument, RepositoryArtifact,
)

_logger = logging.getLogger(__name__)


class McpSourceAdapter(BaseProviderAdapter):
    """
    Phase 29 translation layer for MCP-backed sources.
    Delegates exclusively to Phase 28 ConnectorRuntime.dispatch().
    """

    def __init__(self, connector_id: int, env: Any, config: Optional[Dict[str, Any]] = None):
        super().__init__(None, config)
        self.connector_id = connector_id
        self.env = env
        # Import lazily to avoid circular imports at module-load time
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
        self._runtime = get_connector_runtime()
        if not self._runtime:
            raise RuntimeError("ConnectorRuntime is not available.")
        self._capability_map: Optional[Dict[str, str]] = None
        self._default_payload: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Capability routing
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> List[str]:
        """Returns list of discovered tool namespaces from nexora.mcp_discovered_tool."""
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
        connector = self.env['nexora.connector'].search([('connector_id', '=', self.connector_id)], limit=1)
        # Look up source_registry record linked to this connector
        registry_rec = self.env['nexora.source_registry'].search(
            [('connector_id.connector_id', '=', self.connector_id)], limit=1
        )
        if registry_rec and registry_rec.config_json:
            try:
                parsed = json.loads(registry_rec.config_json)
                self._capability_map = parsed.get('capability_map', {})
                default_payload = parsed.get('default_payload', {})
                if isinstance(default_payload, dict):
                    self._default_payload = default_payload
                else:
                    _logger.warning("McpSourceAdapter: default_payload must be a dict")
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
        Resolve intent → MCP tool name → validate against discovered tools → dispatch.
        """
        from odoo.addons.nexora_studio.services.connector.domain.models import (
            ConnectorExecutionRequest, ConnectorRuntimeContext
        )

        tool_name = self._resolve_tool_name(semantic_intent)

        # Guard: tool must be present in discovered capability set
        available = self.capabilities
        if available and tool_name not in available:
            raise ValueError(
                f"Tool '{tool_name}' (resolved from intent '{semantic_intent}') "
                f"is not in discovered capabilities for connector {self.connector_id}. "
                f"Available: {available}"
            )

        ctx = ConnectorRuntimeContext(
            connector_id=str(self.connector_id),
            session_id='csf'
        )

        # Merge source-bound configuration payload with runtime params.
        # Precedence: Source defaults override runtime parameters to preserve source isolation.
        final_payload = dict(params)
        if self._default_payload:
            final_payload.update(self._default_payload)

        request = ConnectorExecutionRequest(
            capability_namespace="tools.call",
            context=ctx,
            payload={
                "name": tool_name,
                "arguments": final_payload
            },
        )

        result = self._runtime.dispatch(request)
        if not result.success:
            raise RuntimeError(
                f"ConnectorRuntime dispatch failed for tool '{tool_name}': {result.error}"
            )
        return result.data

    # ------------------------------------------------------------------
    # Normalization (§6 Decision)
    # ------------------------------------------------------------------

    def _normalize(self, raw: Any) -> Any:
        """
        Normalise raw MCP tool output to a typed domain model where confidence
        is sufficient. Preserves raw output otherwise.

        Rules:
        - Never invents fields.
        - Never forces normalization on ambiguous data.
        - Exposes normalization failures via logging, returns raw on error.
        - Provider-specific normalization config can be added later via
          'normalization' key in config_json without changing this class.
        """
        if isinstance(raw, list):
            return [self._normalize(item) for item in raw]

        if not isinstance(raw, dict):
            return raw  # preserve scalars/None as-is

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

    # ------------------------------------------------------------------
    # BaseProviderAdapter interface — delegates to _execute + _normalize
    # ------------------------------------------------------------------

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Any:
        params = {'query': query}
        if filters:
            params.update(filters)
        return self._normalize(self._execute('search', params))

    def get_component(self, component_id: str) -> Any:
        return self._normalize(self._execute('get', {'id': component_id}))

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
