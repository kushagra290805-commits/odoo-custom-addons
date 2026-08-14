from typing import Dict, Any, List
from odoo.addons.nexora_studio.services.connector.sdk.context import ExecutionContext
from odoo.addons.nexora_studio.services.connector.sdk.exceptions import RuntimeException
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger

_logger = get_logger(__name__)

class McpProvider:
    """
    Capability Provider for MCP Connectors.
    Maps generic capability namespaces to MCP protocol commands via the McpTransport.
    """
    def __init__(self, transport: McpTransport):
        self.transport = transport

    def execute(
        self, 
        capability_namespace: str, 
        parameters: Dict[str, Any], 
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Main capability execution dispatcher.
        """
        _logger.debug("McpProvider: Executing capability %s", capability_namespace)
        
        try:
            if capability_namespace == "tools.list":
                return self._tools_list(parameters)
            elif capability_namespace == "tools.call":
                return self._tools_call(parameters)
            elif capability_namespace == "resources.list":
                return self._resources_list(parameters)
            elif capability_namespace == "resources.read":
                return self._resources_read(parameters)
            elif capability_namespace == "prompts.list":
                return self._prompts_list(parameters)
            elif capability_namespace == "prompts.get":
                return self._prompts_get(parameters)
            else:
                raise RuntimeException(
                    error_code="CAPABILITY_NOT_FOUND",
                    user_safe_message=f"Capability {capability_namespace} is not supported by MCP provider.",
                    technical_message=f"Namespace {capability_namespace} unknown."
                )
        except RuntimeException:
            raise
        except Exception as e:
            raise RuntimeException(
                error_code="PROVIDER_EXECUTION_FAILED",
                user_safe_message=f"Failed to execute MCP capability {capability_namespace}.",
                technical_message=str(e)
            )

    def _tools_list(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self.transport.list_tools()
        # The result is a pydantic model in the MCP SDK, we must convert to dict
        return {"tools": [tool.model_dump() for tool in result.tools]}

    def _tools_call(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        name = parameters.get("name")
        arguments = parameters.get("arguments", {})
        if not name:
            raise RuntimeException("INVALID_PARAMETERS", "Missing tool name.", "Missing 'name' in parameters.")
            
        result = self.transport.call_tool(name, arguments)
        return {"content": [c.model_dump() for c in result.content], "isError": getattr(result, "isError", False)}

    def _resources_list(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self.transport.list_resources()
        return {"resources": [r.model_dump() for r in result.resources]}

    def _resources_read(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        uri = parameters.get("uri")
        if not uri:
            raise RuntimeException("INVALID_PARAMETERS", "Missing resource uri.", "Missing 'uri' in parameters.")
        result = self.transport.read_resource(uri)
        return {"contents": [c.model_dump() for c in result.contents]}

    def _prompts_list(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self.transport.list_prompts()
        return {"prompts": [p.model_dump() for p in result.prompts]}

    def _prompts_get(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        name = parameters.get("name")
        arguments = parameters.get("arguments", {})
        if not name:
            raise RuntimeException("INVALID_PARAMETERS", "Missing prompt name.", "Missing 'name' in parameters.")
        result = self.transport.get_prompt(name, arguments)
        return {
            "description": result.description,
            "messages": [m.model_dump() for m in result.messages]
        }
