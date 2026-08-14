import os
from typing import Dict, List, Optional, Any
from .mcp_models import McpServerConfig, StartupPolicy
from .registry_provider import RegistryProvider

class McpServerRegistry:
    """
    Configuration-driven registry for MCP servers.
    Uses a RegistryProvider abstraction to decouple from storage.
    """
    def __init__(self, provider: RegistryProvider):
        self.provider = provider
        self._servers: Dict[str, McpServerConfig] = {}
        self.provider.subscribe(self._handle_config_update)
        
    def _handle_config_update(self, config_data: Dict[str, Any]) -> None:
        """Called by the RegistryProvider when the underlying config changes."""
        self._parse_and_load(config_data)

    def load(self) -> None:
        """Initial load from the provider."""
        data = self.provider.get_raw_config()
        self._parse_and_load(data)

    def _parse_and_load(self, data: Dict[str, Any]) -> None:
        new_servers = {}
        for s_id, s_data in data.items():
            raw_env = s_data.get("environment_variables", {})
            expanded_env = {
                k: os.path.expandvars(v) if isinstance(v, str) else v
                for k, v in raw_env.items()
            }
            
            # Map string to enum, default to OPTIONAL
            raw_policy = s_data.get("startup_policy", "optional").lower()
            try:
                policy = StartupPolicy(raw_policy)
            except ValueError:
                policy = StartupPolicy.OPTIONAL
            
            config = McpServerConfig(
                id=s_id,
                display_name=s_data.get("display_name", s_id),
                transport=s_data.get("transport", "stdio"),
                enabled=s_data.get("enabled", True),
                startup_policy=policy,
                startup_command=s_data.get("startup_command", ""),
                startup_args=s_data.get("startup_args", []),
                cwd=s_data.get("cwd", None),
                environment_variables=expanded_env,
                authentication=s_data.get("authentication", {}),
                health_check=s_data.get("health_check", {}),
                timeout=s_data.get("timeout", 30),
                retry_policy=s_data.get("retry_policy", {}),
                capability_filters=s_data.get("capability_filters", []),
                security_profile=s_data.get("security_profile", "default")
            )
            new_servers[s_id] = config
            
        self._servers = new_servers
                
    def get_server(self, server_id: str) -> Optional[McpServerConfig]:
        return self._servers.get(server_id)
        
    def get_enabled_servers(self) -> List[McpServerConfig]:
        return [s for s in self._servers.values() if s.enabled]
