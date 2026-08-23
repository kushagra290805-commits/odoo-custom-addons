"""
McpCapabilityDiscoveryService — Dynamic MCP Capability Discovery
=================================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Discovers tools, resources, and prompts from a live MCP server and persists
the full JSON schema to nexora.mcp_discovered_tool records.

Key behaviors:
- Uses the global ConnectorRuntime (connector must be registered and running)
- Phase 44.2 (W11): persistence is NON-DESTRUCTIVE. Each discovery source
  (tools/resources/prompts) is upserted independently, keyed on
  (connector_id, tool_name, discovery_source). A source whose list call
  FAILED is skipped entirely — its previously persisted rows are preserved.
  Persistence only happens for sources that returned a real result.
- Does NOT generate Python classes for discovered tools
- Does NOT hardcode tool names in source code
- Updates nexora.mcp_server_config.discovered_capabilities_count
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from odoo.addons.nexora_studio.services.connector.domain.models import (
    ConnectorExecutionRequest,
    ConnectorRuntimeContext,
)
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger

_logger = get_logger(__name__)


class McpCapabilityDiscoveryService:
    """
    Discovers MCP capabilities from a live server and persists them to Odoo.
    """

    def __init__(self, runtime, odoo_env):
        """
        Args:
            runtime: ConnectorRuntime singleton (the global one)
            odoo_env: Odoo environment
        """
        if runtime is None:
            raise ValueError("McpCapabilityDiscoveryService requires an active ConnectorRuntime instance.")
            
        self._runtime = runtime
        self._env = odoo_env

    def discover(self, connector_record) -> Dict[str, Any]:
        """
        Discover all capabilities from the MCP server and persist to Odoo.

        Phase 44.2 (W11): non-destructive semantics.
        - Each source is persisted only if its list call SUCCEEDED.
        - A failed source keeps its previously persisted rows untouched.
        - Persistence is an upsert keyed on
          (connector_id, tool_name, discovery_source); rows no longer
          returned by a successful source are removed.

        Args:
            connector_record: nexora.connector Odoo record

        Returns:
            Dict with 'tool_count', 'resource_count', 'prompt_count'
            (counts from this run; 0 for failed sources) and 'persisted'
            (True if at least one source was persisted).
        """
        connector_id = connector_record.connector_id
        _logger.info(
            "McpCapabilityDiscoveryService: starting discovery for '%s'.", connector_id,
            extra={'connector_id': connector_id}
        )

        ctx = ConnectorRuntimeContext(connector_id=connector_id, session_id='discovery')

        # None = dispatch failed → skip persistence for that source.
        tools = self._discover_tools(connector_id, ctx)
        resources = self._discover_resources(connector_id, ctx)
        prompts = self._discover_prompts(connector_id, ctx)

        persisted = self._upsert_discovered_tools(connector_record, tools, resources, prompts)

        counts = {
            'tool_count': len(tools) if tools is not None else 0,
            'resource_count': len(resources) if resources is not None else 0,
            'prompt_count': len(prompts) if prompts is not None else 0,
            'persisted': persisted,
        }
        _logger.info(
            "McpCapabilityDiscoveryService: discovery complete for '%s': %s",
            connector_id, counts,
            extra={'connector_id': connector_id}
        )
        return counts

    # ------------------------------------------------------------------
    # MCP Discovery Dispatchers
    # ------------------------------------------------------------------

    def _discover_tools(self, connector_id: str, ctx: ConnectorRuntimeContext) -> Optional[List[Dict]]:
        """Returns the tool list, or None if the dispatch failed (W11)."""
        req = ConnectorExecutionRequest(
            capability_namespace='tools.list',
            context=ctx,
            timeout_seconds=30.0,
        )
        result = self._runtime.dispatch(req)

        # Phase 44.2 (W1): never log raw MCP payloads (may transit tokens/PII).
        if not result.success:
            _logger.warning(
                "McpCapabilityDiscoveryService: tools.list failed for '%s': %s",
                connector_id, result.error
            )
            return None
        return result.data.get('tools', []) if result.data else []

    def _discover_resources(self, connector_id: str, ctx: ConnectorRuntimeContext) -> Optional[List[Dict]]:
        """Returns the resource list, or None if the dispatch failed (W11)."""
        req = ConnectorExecutionRequest(
            capability_namespace='resources.list',
            context=ctx,
            timeout_seconds=30.0,
        )
        result = self._runtime.dispatch(req)
        if not result.success:
            _logger.warning(
                "McpCapabilityDiscoveryService: resources.list failed for '%s': %s",
                connector_id, result.error,
                extra={'connector_id': connector_id}
            )
            return None
        return result.data.get('resources', []) if result.data else []

    def _discover_prompts(self, connector_id: str, ctx: ConnectorRuntimeContext) -> Optional[List[Dict]]:
        """Returns the prompt list, or None if the dispatch failed (W11)."""
        req = ConnectorExecutionRequest(
            capability_namespace='prompts.list',
            context=ctx,
            timeout_seconds=30.0,
        )
        result = self._runtime.dispatch(req)
        if not result.success:
            _logger.warning(
                "McpCapabilityDiscoveryService: prompts.list failed for '%s': %s",
                connector_id, result.error,
                extra={'connector_id': connector_id}
            )
            return None
        return result.data.get('prompts', []) if result.data else []

    # ------------------------------------------------------------------
    # Odoo Persistence
    # ------------------------------------------------------------------

    def _upsert_discovered_tools(
        self,
        connector_record,
        tools: Optional[List[Dict]],
        resources: Optional[List[Dict]],
        prompts: Optional[List[Dict]],
    ) -> bool:
        """
        Non-destructive persistence (Phase 44.2 / W11).

        Each source is handled independently:
        - None  → the list call failed; existing rows for that source are
                  preserved untouched (a failure must never wipe data).
        - list  → authoritative result; upsert rows keyed on
                  (connector_id, tool_name, discovery_source) and remove
                  rows the server no longer reports for that source.

        Returns True if at least one source was persisted.
        """
        model = self._env['nexora.mcp_discovered_tool']
        persisted_any = False

        for items, source in (
            (tools, 'tools'),
            (resources, 'resources'),
            (prompts, 'prompts'),
        ):
            if items is None:
                # Failed dispatch: skip persistence, keep previous snapshot.
                _logger.warning(
                    "McpCapabilityDiscoveryService: skipping persistence for "
                    "source '%s' (connector %s) — list call failed; previous "
                    "rows preserved.", source, connector_record.connector_id,
                    extra={'connector_id': connector_record.connector_id}
                )
                continue
            self._upsert_source(connector_record, model, items, source)
            persisted_any = True

        if persisted_any:
            # Update count on the config record
            mcp_config = self._env['nexora.mcp_server_config'].search(
                [('connector_id', '=', connector_record.id)], limit=1
            )
            if mcp_config:
                # discovered_capabilities_count is computed — just invalidate the cache
                mcp_config.invalidate_recordset(['discovered_capabilities_count'])

        return persisted_any

    def _upsert_source(
        self,
        connector_record,
        model,
        items: List[Dict],
        source: str,
    ) -> None:
        """Upsert one discovery source keyed on (connector_id, tool_name, discovery_source)."""
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        existing = model.search([
            ('connector_id', '=', connector_record.id),
            ('discovery_source', '=', source),
        ])
        existing_by_name = {rec.tool_name: rec for rec in existing}

        seen_names = set()
        to_create = []
        for item in items:
            vals = self._tool_to_record(connector_record.id, item, source, now)
            name = vals['tool_name']
            seen_names.add(name)
            rec = existing_by_name.get(name)
            if rec is not None:
                update_vals = dict(vals)
                update_vals.pop('connector_id', None)
                update_vals.pop('tool_name', None)
                update_vals.pop('discovery_source', None)
                rec.write(update_vals)
            else:
                to_create.append(vals)

        if to_create:
            model.create(to_create)

        # Remove rows the server no longer reports for this source only.
        stale = existing.filtered(lambda r: r.tool_name not in seen_names)
        if stale:
            stale.unlink()

    def _tool_to_record(
        self,
        connector_odoo_id: int,
        item: Dict[str, Any],
        source: str,
        now: str,
    ) -> Dict[str, Any]:
        """Convert an MCP SDK model_dump() dict to a nexora.mcp_discovered_tool create vals."""
        name = item.get('name', '')
        description = item.get('description', '')

        # Extract input schema for tools; uri for resources; args for prompts
        input_schema = item.get('inputSchema', item.get('arguments', {}))
        if isinstance(input_schema, list):
            # prompts return list of argument dicts
            input_schema = {'arguments': input_schema}

        return {
            'connector_id': connector_odoo_id,
            'tool_name': name,
            'description': description,
            'input_schema_json': json.dumps(input_schema, ensure_ascii=False),
            'raw_schema_json': json.dumps(item, ensure_ascii=False, default=str),
            'discovery_source': source,
            'discovered_at': now,
        }
