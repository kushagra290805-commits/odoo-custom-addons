# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time

_logger = logging.getLogger(__name__)

class GitHubProvider(models.AbstractModel):
    _name = 'nexora.provider.github'
    _description = 'Canonical GitHub Provider'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Canonical execution interface.
        Uses the existing GitHub MCP connection when available.
        If the MCP is unavailable, return a structured capability failure.
        """
        try:
            import asyncio
            
            platform = self.env['nexora_studio.platform']
            runtime = platform.get_runtime()
            adapter = runtime.get_runtime('mcp_runtime')
            
            if not adapter:
                return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: MCP Runtime unavailable.", execution_ms=(time.time()-start_time)*1000)
                
            mcp_tool = request.payload.get('mcp_tool', request.namespace)
            # Since execute is synchronous, we run the router coroutine threadsafe
            future = asyncio.run_coroutine_threadsafe(
                adapter.router.execute_capability(mcp_tool, request.payload), 
                adapter._loop
            )
            result = future.result(timeout=60.0)
            
            return ProviderExecutionResult(success=True, data=result, error=None, execution_ms=(time.time()-start_time)*1000)

        except Exception as e:
            _logger.error(f"GitHub MCP execution error: {e}")
            return ProviderExecutionResult(success=False, data=None, error=f"GitHub MCP error: {str(e)}", execution_ms=(time.time()-start_time)*1000)
