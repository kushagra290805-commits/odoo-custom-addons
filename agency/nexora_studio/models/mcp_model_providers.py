# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import time

from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionResult

_logger = logging.getLogger(__name__)


class _McpModelProviderMixin:
    """Phase 44.2 closure (C-26 / P11): shared canonical routing for the
    connector-backed model providers.

    Previously tavily/github/context7 each built a ConnectorExecutionRequest
    and called ConnectorRuntime.dispatch directly — a parallel entry point
    that bypassed policy, security and observability. All three now route
    through the canonical chain via build_canonical_router():

        UniversalCapabilityRouter → ConnectorExecutionTarget → ConnectorRuntime
        → ConnectorDispatcher → McpConnector → McpProvider → McpTransport

    Subclasses declare exactly one thing: their connector id. No
    connector-specific branch exists in the shared path.
    """

    _mcp_connector_id = None

    @api.model
    def execute(self, request):
        start_time = time.time()
        try:
            from odoo.addons.nexora_studio.services.connector.integration.bootstrap import (
                build_canonical_router,
            )

            router = build_canonical_router(self.env)

            mcp_tool = request.payload.get('mcp_tool', request.namespace)
            args = {k: v for k, v in request.payload.items() if k != 'mcp_tool'}

            # The dotted "{connector_id}.{tool_name}" namespace is the
            # canonical shorthand (ADR-0069): ConnectorExecutionTarget splits
            # it on the first dot into tools.call + {name, arguments}.
            result = router.execute(
                f"{self._mcp_connector_id}.{mcp_tool}",
                {"inputs": args},
                context={
                    'connector_id': self._mcp_connector_id,
                    'session_id': getattr(request, 'session_id', 'provider_execution'),
                },
            )

            execution_ms = (time.time() - start_time) * 1000
            if not result.success:
                error = ' | '.join(result.logs) if result.logs else 'MCP execution failed.'
                return ProviderExecutionResult(
                    success=False,
                    data=None,
                    error=error,
                    execution_ms=execution_ms,
                )

            return ProviderExecutionResult(
                success=True,
                data=result.result,
                error=None,
                execution_ms=execution_ms,
            )
        except Exception as e:
            _logger.error("%s execution error: %s", self._name, e)
            return ProviderExecutionResult(
                success=False,
                data=None,
                error=f"{self._mcp_connector_id} MCP error: {e}",
                execution_ms=(time.time() - start_time) * 1000,
            )


class TavilyProvider(models.AbstractModel, _McpModelProviderMixin):
    _name = 'nexora.provider.tavily'
    _description = 'Canonical Tavily Web Research Provider'
    _mcp_connector_id = 'tavily_mcp'


class GithubProvider(models.AbstractModel, _McpModelProviderMixin):
    _name = 'nexora.provider.github'
    _description = 'Canonical GitHub Provider'
    _mcp_connector_id = 'github_mcp'


class Context7Provider(models.AbstractModel, _McpModelProviderMixin):
    _name = 'nexora.provider.context7'
    _description = 'Canonical Context7 Documentation Provider'
    _mcp_connector_id = 'context7_mcp'
