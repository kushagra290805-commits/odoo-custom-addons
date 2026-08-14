# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from .adapters.base_adapter import BaseProviderAdapter
from .provider_health_monitor import ProviderHealthMonitor

class ProviderManager:
    def __init__(self, env):
        self.env = env
        self.health_monitor = ProviderHealthMonitor()
        self.adapters: Dict[str, BaseProviderAdapter] = {}
        self._load_providers()
        
    def _load_providers(self):
        # Dynamic loading logic using self.env['nexora.source_registry']
        # Load legacy ones...
        pass
        
    def load_from_registry(self):
        if not self.env:
            return
            
        sources = self.env['nexora.source_registry'].search([])
        for source in sources:
            if source.is_mcp and source.connector_id:
                from .adapters.mcp_source_adapter import McpSourceAdapter
                adapter = McpSourceAdapter(connector_id=source.connector_id.id, env=self.env)
                self.register_adapter(source.technical_name, adapter)
            else:
                # Load existing non-MCP adapters
                pass
                
    def register_adapter(self, provider_id: str, adapter: BaseProviderAdapter):
        self.adapters[provider_id] = adapter
        
    def get_capable_providers(self, required_capability: str) -> List[str]:
        capable = []
        for pid, adapter in self.adapters.items():
            if self.health_monitor.check_health(pid) and required_capability in adapter.capabilities:
                capable.append(pid)
        return capable
        
    def route_request(self, provider_id: str, method: str, *args, **kwargs) -> Any:
        if not self.health_monitor.check_health(provider_id):
            raise Exception(f"Provider {provider_id} is currently unhealthy.")
        adapter = self.adapters.get(provider_id)
        if not adapter:
            raise Exception(f"Provider {provider_id} not found.")
        try:
            func = getattr(adapter, method)
            result = func(*args, **kwargs)
            self.health_monitor.track_latency(provider_id, 100) # Mock latency
            return result
        except Exception as e:
            self.health_monitor.record_failure(provider_id)
            raise e
