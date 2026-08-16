# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time

_logger = logging.getLogger(__name__)

class TavilyProvider(models.AbstractModel):
    _name = 'nexora.provider.tavily'
    _description = 'Canonical Tavily Web Research Provider'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Canonical execution interface.
        Uses the existing Tavily MCP connection when available.
        If the MCP is unavailable, return a structured capability failure.
        """
        try:
            from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
            from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorExecutionRequest, ConnectorRuntimeContext
            
            bootstrap = ConnectorPlatformBootstrap.get_instance()
            if not bootstrap or not bootstrap.connector_runtime:
                return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: ConnectorRuntime unavailable.", execution_ms=(time.time()-start_time)*1000)
            
            mcp_tool = request.payload.get('mcp_tool', request.namespace)
            args = {k: v for k, v in request.payload.items() if k != 'mcp_tool'}
            
            exec_req = ConnectorExecutionRequest(
                capability_namespace="tools.call",
                payload={
                    "name": mcp_tool,
                    "arguments": args
                },
                context=ConnectorRuntimeContext(
                    connector_id="tavily_mcp",
                    session_id=getattr(request, 'session_id', 'provider_execution')
                )
            )
            
            result = bootstrap.connector_runtime.dispatch(exec_req)
            
            if not result.success:
                return ProviderExecutionResult(
                    success=False, 
                    data=None, 
                    error=f"Tavily MCP error: {result.error} (Code: {result.error_code})", 
                    execution_ms=(time.time()-start_time)*1000
                )
                
            return ProviderExecutionResult(
                success=True, 
                data=result.data, 
                error=None, 
                execution_ms=(time.time()-start_time)*1000
            )

        except Exception as e:
            _logger.error(f"Tavily MCP execution error: {e}")
            return ProviderExecutionResult(success=False, data=None, error=f"Tavily MCP error: {str(e)}", execution_ms=(time.time()-start_time)*1000)
