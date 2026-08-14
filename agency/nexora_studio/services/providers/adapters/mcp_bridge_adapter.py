import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
from typing import Dict, Any, List

from ..base_provider import (
    BaseProvider,
    ProviderMetadata,
    ProviderCategory,
    ProviderConfiguration,
    ProviderAuthentication,
    ProviderHealth,
    ProviderCapability,
    ProviderSearchResult,
    ProviderExecutionResult,
    ProviderExecutionContext
)

_logger = logging.getLogger(__name__)

class UnifiedMcpProviderProxy(BaseProvider):
    """
    Bridge adapter wrapping legacy MCP services (McpService + ToolRegistry)
    into the Unified Provider Platform (ADR-0031).
    """

    def __init__(self, metadata: ProviderMetadata):
        super().__init__(metadata)
        self._mcp_service = None
        self._mcp_server_name = metadata.provider_id.replace("legacy_mcp_", "")

    @classmethod
    def get_default_metadata(cls) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="legacy_mcp_bridge",
            name="Legacy MCP Bridge Adapter",
            category=ProviderCategory.MCP,
            provider_version="1.0.0",
            manifest_version="2.0",
            api_version="v1",
            vendor_url="internal",
            author="Nexora Studio"
        )

    def initialize(self, config: ProviderConfiguration) -> None:
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                self._mcp_service = http.request.env['agency.mcp_service']
        except ImportError:
            pass

    def authenticate(self, auth: ProviderAuthentication) -> bool:
        return True

    def check_health(self) -> ProviderHealth:
        if not self._mcp_service:
            return ProviderHealth(status="degraded", latency_ms=0.0, error_rate_24h=0.0, last_checked=None, details="No MCP service")
        return ProviderHealth(status="healthy", latency_ms=5.0, error_rate_24h=0.0, last_checked=None)

    def discover_capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability(
                capability_id=f"{self.metadata.provider_id}_tool_call",
                operation_type="mcp_tool_call",
                capability_version="1.0",
                supported_revisions=["1.0"],
                deprecated_revisions=[],
                parameter_schema={},
                output_schema={},
                rate_limits={"rpm": 120},
                supports_tool_calling=True
            )
        ]

    def search(self, query: str, filters: Dict[str, Any]) -> List[ProviderSearchResult]:
        return []

    def fetch(self, resource_id: str, context: ProviderExecutionContext) -> ProviderExecutionResult:
        return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=NotImplementedError("fetch not supported by MCP Bridge"))

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        operation = request.payload.get('operation') or request.namespace.split('.')[-1]
        payload = request.payload
        context = request.context
        import time
        start = time.time()
        
        if not self._mcp_service:
            return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=None)
            
        if operation == "mcp_tool_call":
            tool_name = payload.get("tool_name", "")
            args = payload.get("arguments", {})
            try:
                # Use correct legacy execution since call_tool doesn't exist on mcp_service
                class DummyRuntime:
                    builder_session_id = False
                res = self._mcp_service.execute_tool_safely(DummyRuntime(), tool_name, {}, **args)
                duration = (time.time() - start) * 1000
                return ProviderExecutionResult(success=True, data=res, metadata={"legacy": True}, execution_ms=duration)
            except Exception as e:
                duration = (time.time() - start) * 1000
                return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=duration, error=Exception(str(e)))
        
        return ProviderExecutionResult(success=False, data=None, metadata={}, execution_ms=0, error=None)
    def cleanup(self) -> None:
        self._mcp_service = None

