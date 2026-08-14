"""
McpCapabilityDiscoveryService — Dynamic MCP Capability Discovery
=================================================================
Phase 28 — Connector MCP Onboarding Platform (ADR-0051).

Discovers tools, resources, and prompts from a live MCP server and persists
the full JSON schema to nexora.mcp_discovered_tool records.

Key behaviors:
- Uses the global ConnectorRuntime (connector must be registered and running)
- Each discovery run REPLACES previous results (not appended)
- Does NOT generate Python classes for discovered tools
- Does NOT hardcode tool names in source code
- Updates nexora.mcp_server_config.discovered_capabilities_count
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

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
            from odoo.addons.nexora_studio.services.connector.runtime.connector_runtime import ConnectorRuntime
            from odoo.addons.nexora_studio.services.connector.registry.persistence.odoo_adapter import OdooConnectorPersistenceAdapter
            runtime = ConnectorRuntime(persistence_port=OdooConnectorPersistenceAdapter(odoo_env))
            runtime.startup()
            
        self._runtime = runtime
        self._env = odoo_env

    def discover(self, connector_record) -> Dict[str, int]:
        """
        Discover all capabilities from the MCP server and persist to Odoo.
        Previous discovery results for this connector are REPLACED.

        Args:
            connector_record: nexora.connector Odoo record

        Returns:
            Dict with 'tool_count', 'resource_count', 'prompt_count'
        """
        connector_id = connector_record.connector_id
        _logger.info(
            "McpCapabilityDiscoveryService: starting discovery for '%s'.", connector_id,
            extra={'connector_id': connector_id}
        )

        ctx = ConnectorRuntimeContext(connector_id=connector_id, session_id='discovery')

        tools = self._discover_tools(connector_id, ctx)
        resources = self._discover_resources(connector_id, ctx)
        prompts = self._discover_prompts(connector_id, ctx)

        # Replace all previous discovery results
        self._replace_discovered_tools(connector_record, tools, resources, prompts)

        counts = {
            'tool_count': len(tools),
            'resource_count': len(resources),
            'prompt_count': len(prompts),
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

    def _discover_tools(self, connector_id: str, ctx: ConnectorRuntimeContext) -> List[Dict]:
        req = ConnectorExecutionRequest(
            capability_namespace='tools.list',
            context=ctx,
            timeout_seconds=30.0,
        )
        result = self._runtime.dispatch(req)
        
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"DISCOVERY RESULT RAW: success={result.success}, data={result.data}, error={result.error}")
        
        if not result.success:
            _logger.warning(
                "McpCapabilityDiscoveryService: tools.list failed for '%s': %s",
                connector_id, result.error
            )
            return []
        return result.data.get('tools', []) if result.data else []

    def _discover_resources(self, connector_id: str, ctx: ConnectorRuntimeContext) -> List[Dict]:
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
            return []
        return result.data.get('resources', []) if result.data else []

    def _discover_prompts(self, connector_id: str, ctx: ConnectorRuntimeContext) -> List[Dict]:
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
            return []
        return result.data.get('prompts', []) if result.data else []

    # ------------------------------------------------------------------
    # Odoo Persistence
    # ------------------------------------------------------------------

    def _replace_discovered_tools(
        self,
        connector_record,
        tools: List[Dict],
        resources: List[Dict],
        prompts: List[Dict],
    ) -> None:
        """Delete previous discovery results and insert new ones."""
        # Delete previous results for this connector
        self._env['nexora.mcp_discovered_tool'].search(
            [('connector_id', '=', connector_record.id)]
        ).unlink()

        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        to_create = []

        for tool in tools:
            to_create.append(self._tool_to_record(connector_record.id, tool, 'tools', now))

        for resource in resources:
            to_create.append(self._tool_to_record(connector_record.id, resource, 'resources', now))

        for prompt in prompts:
            to_create.append(self._tool_to_record(connector_record.id, prompt, 'prompts', now))

        if to_create:
            self._env['nexora.mcp_discovered_tool'].create(to_create)

        # Update count on the config record
        mcp_config = self._env['nexora.mcp_server_config'].search(
            [('connector_id', '=', connector_record.id)], limit=1
        )
        if mcp_config:
            # discovered_capabilities_count is computed — just invalidate the cache
            mcp_config.invalidate_recordset(['discovered_capabilities_count'])

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
