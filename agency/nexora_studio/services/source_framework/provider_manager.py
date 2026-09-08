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

        # Phase 47.25 (ADR-0077): the native component library is a
        # code-level built-in resource source — always available through the
        # same adapter contract as the registry sources (no DB row, no
        # connector, no lifecycle). Discovery/the source-code gate treat it
        # exactly like any other source.
        from .adapters.native_library_adapter import NativeLibraryAdapter
        self.register_adapter('native_library', NativeLibraryAdapter())

        sources = self.env['nexora.source_registry'].search([])
        for source in sources:
            # Phase 47.24 (ADR-0076): the shadcn / react_bits sources
            # resolve through the DIRECT public registries (bridged to the
            # existing provider-platform adapters) instead of the dead MCP
            # execution path — component selection must not depend on an
            # MCP connector being enabled. No registry/connector rows
            # change; only the adapter binding for these existing rows.
            if source.technical_name == 'shadcn':
                from .adapters.shadcn_registry_adapter import ShadcnRegistryAdapter
                self.register_adapter(source.technical_name, ShadcnRegistryAdapter())
                continue
            if source.technical_name == 'react_bits':
                from .adapters.react_bits_registry_adapter import ReactBitsRegistryAdapter
                self.register_adapter(source.technical_name, ReactBitsRegistryAdapter())
                continue
            if source.is_mcp and source.connector_id:
                from .adapters.mcp_source_adapter import McpSourceAdapter
                # Phase 45 (ADR-0072): pass the exact registry row — several
                # sources may share one connector, each with its own
                # capability_map/qualification configuration.
                adapter = McpSourceAdapter(
                    connector_id=source.connector_id.id, env=self.env,
                    source_row=source)
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
