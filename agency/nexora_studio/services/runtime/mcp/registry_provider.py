import json
import os
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional, List
import threading

class RegistryProvider(ABC):
    """
    Abstract interface for providing MCP server configurations.
    """
    @abstractmethod
    def get_raw_config(self) -> Dict[str, Any]:
        """Returns the raw dictionary of mcpServers."""
        pass
        
    @abstractmethod
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe to config changes for hot reloading."""
        pass
        
    @abstractmethod
    def get_manifests(self) -> List['CapabilityManifest']:
        """Returns parsed CapabilityManifest objects."""
        pass

class JsonRegistryProvider(RegistryProvider):
    """
    Provides MCP configurations from a JSON file, with hot-reload support.
    """
    def __init__(self, file_path: str, poll_interval: float = 2.0):
        self.file_path = file_path
        self._callbacks = []
        self._last_mtime = 0
        self._last_content = {}
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def get_raw_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            return {}
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("mcpServers", {})
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to load MCP registry from {self.file_path}: {e}")
            return {}

    def get_manifests(self) -> List['CapabilityManifest']:
        from odoo.addons.nexora_studio.services.capabilities.models import CapabilityManifest, ExecutionTargetType
        raw_config = self.get_raw_config()
        manifests = []
        for provider_id, conf in raw_config.items():
            namespace = conf.get("namespace")
            if not namespace:
                continue
                
            manifest = CapabilityManifest(
                namespace=namespace,
                display_name=conf.get("display_name", provider_id),
                target_type=ExecutionTargetType.LOCAL if conf.get("transport") == "stdio" else ExecutionTargetType.REMOTE,
                version="1.0.0",
                aliases=[],
                input_schema={},
                output_schema={},
                metadata={
                    "provider": conf.get("provider_id", provider_id),
                    "category": conf.get("business_capability", "unknown"),
                    "implementation_model": f"nexora.provider.{provider_id}",
                    "transport": conf.get("transport"),
                    "enabled": conf.get("enabled", False),
                    "lifecycle": conf.get("lifecycle", "planned"),
                    "supported_capabilities": conf.get("supported_capabilities", []),
                    "priority": conf.get("priority", 50),
                    "provider_type": conf.get("provider_type", "unknown"),
                    "limits": conf.get("limits", {}),
                    "estimated_latency_ms": conf.get("estimated_latency_ms", 500),
                    "requires_authentication": conf.get("requires_authentication", False)
                }
            )
            manifests.append(manifest)
        return manifests

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)
        if not self._running:
            self.start_watching()

    def start_watching(self):
        if self._running:
            return
        self._running = True
        if os.path.exists(self.file_path):
            self._last_mtime = os.path.getmtime(self.file_path)
            self._last_content = self.get_raw_config()
            
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop_watching(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._poll_interval + 1.0)

    def _watch_loop(self):
        import time
        while self._running:
            try:
                if os.path.exists(self.file_path):
                    current_mtime = os.path.getmtime(self.file_path)
                    if current_mtime > self._last_mtime:
                        self._last_mtime = current_mtime
                        new_content = self.get_raw_config()
                        # Notify if content actually changed
                        if new_content != self._last_content:
                            self._last_content = new_content
                            for cb in self._callbacks:
                                cb(new_content)
            except Exception:
                pass
            time.sleep(self._poll_interval)
