import logging
import threading
import json
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from .base_provider import (
    CapabilityCache,
    ProviderCapability,
    BaseProvider
)

_logger = logging.getLogger(__name__)

class CapabilityCacheEntry:
    def __init__(self, capabilities: List[ProviderCapability], expires_at: datetime):
        self.capabilities = capabilities
        self.expires_at = expires_at

class OdooCapabilityCache(CapabilityCache):
    """
    Dedicated caching for Provider Capabilities manifests.
    Reduces the overhead of discover_capabilities() calls.
    """

    def __init__(self):
        self._l1_cache: Dict[str, CapabilityCacheEntry] = {}
        self._lock = threading.Lock()
        self._default_ttl = 86400  # 24 hours

    def get(self, provider_id: str, capability_version: str = "latest") -> Optional[List[ProviderCapability]]:
        with self._lock:
            if provider_id in self._l1_cache:
                entry = self._l1_cache[provider_id]
                if datetime.utcnow() <= entry.expires_at:
                    if capability_version == "latest":
                        return entry.capabilities
                    else:
                        filtered = [c for c in entry.capabilities if c.capability_version == capability_version]
                        return filtered if filtered else None
                else:
                    del self._l1_cache[provider_id]

        # Try Odoo database (L2)
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                record = env['nexora.provider.capability_cache'].sudo().search(
                    [('provider_id', '=', provider_id), ('is_stale', '=', False)], limit=1
                )
                if record:
                    if record.expires_at and record.expires_at < datetime.utcnow():
                        record.is_stale = True
                    else:
                        caps_data = json.loads(record.capabilities_json)
                        # Reconstruct ProviderCapability objects
                        caps = []
                        for c_data in caps_data:
                            caps.append(ProviderCapability(**c_data))
                            
                        # Backfill L1
                        with self._lock:
                            self._l1_cache[provider_id] = CapabilityCacheEntry(caps, record.expires_at or (datetime.utcnow() + timedelta(seconds=self._default_ttl)))
                            
                        if capability_version == "latest":
                            return caps
                        else:
                            filtered = [c for c in caps if c.capability_version == capability_version]
                            return filtered if filtered else None
        except Exception as e:
            _logger.debug(f"CapabilityCache L2 retrieval failed: {e}")
            
        return None

    def set(self, provider_id: str, capabilities: List[ProviderCapability], ttl_seconds: int = 86400) -> None:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        # Write L1
        with self._lock:
            self._l1_cache[provider_id] = CapabilityCacheEntry(capabilities, expires_at)
            
        # Write L2
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                model = env['nexora.provider.capability_cache'].sudo()
                existing = model.search([('provider_id', '=', provider_id)], limit=1)
                
                # Convert to dicts for JSON serialization
                caps_data = [c.__dict__ for c in capabilities]
                
                vals = {
                    'capabilities_json': json.dumps(caps_data),
                    'cached_at': datetime.utcnow(),
                    'expires_at': expires_at,
                    'is_stale': False
                }
                
                if existing:
                    existing.write(vals)
                else:
                    vals['provider_id'] = provider_id
                    model.create(vals)
        except Exception as e:
            _logger.debug(f"CapabilityCache L2 write failed: {e}")

    def invalidate(self, provider_id: str) -> None:
        with self._lock:
            if provider_id in self._l1_cache:
                del self._l1_cache[provider_id]
                
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                records = env['nexora.provider.capability_cache'].sudo().search([('provider_id', '=', provider_id)])
                for record in records:
                    record.is_stale = True
        except Exception:
            pass

    def invalidate_all(self) -> None:
        with self._lock:
            self._l1_cache.clear()
            
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                records = env['nexora.provider.capability_cache'].sudo().search([('is_stale', '=', False)])
                for record in records:
                    record.is_stale = True
        except Exception:
            pass

    def refresh(self, provider_id: str, provider: BaseProvider) -> List[ProviderCapability]:
        capabilities = provider.discover_capabilities()
        self.set(provider_id, capabilities, self._default_ttl)
        return capabilities

    def get_or_refresh(self, provider_id: str, provider: BaseProvider) -> List[ProviderCapability]:
        cached = self.get(provider_id)
        if cached is not None:
            return cached
        return self.refresh(provider_id, provider)
