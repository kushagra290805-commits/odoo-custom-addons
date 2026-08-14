import logging
import threading
import json
import time
from typing import Any, Optional, Dict
from datetime import datetime, timedelta

from .base_provider import ProviderCache

_logger = logging.getLogger(__name__)

class CacheEntry:
    def __init__(self, value: Any, expires_at: datetime):
        self.value = value
        self.expires_at = expires_at
        
class OdooProviderCache(ProviderCache):
    """
    Multi-level caching for execution results (L1 Memory, L2 Redis, L3 VFS).
    Currently implements L1 fully, and stubs L2/L3 for Odoo DB/File System fallback.
    """

    def __init__(self):
        # L1 Cache (Memory)
        self._l1_cache: Dict[str, CacheEntry] = {}
        self._l1_lock = threading.Lock()
        self._default_ttl = 3600 # 1 hour

    def _get_redis_client(self):
        try:
            import redis
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                redis_url = http.request.env['ir.config_parameter'].sudo().get_param('agency.redis_url', 'redis://localhost:6379/0')
                return redis.from_url(redis_url)
        except Exception as e:
            _logger.error(f"Failed to initialize Redis client: {e}")
        return None

    def get(self, key: str) -> Optional[Any]:
        """
        Waterfall retrieval: L1 -> L2 -> L3
        """
        # Try L1
        with self._l1_lock:
            if key in self._l1_cache:
                entry = self._l1_cache[key]
                if datetime.utcnow() <= entry.expires_at:
                    return entry.value
                else:
                    del self._l1_cache[key]
        
        # Try L2 (Redis)
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                cached_json = redis_client.get(f"provider_cache:{key}")
                if cached_json:
                    value = json.loads(cached_json)
                    ttl = redis_client.ttl(f"provider_cache:{key}")
                    if ttl > 0:
                        with self._l1_lock:
                            self._l1_cache[key] = CacheEntry(value, datetime.utcnow() + timedelta(seconds=ttl))
                    return value
            except Exception as e:
                _logger.error(f"Cache L2 retrieval failed: {e}")
        
        # Try L3 (Odoo DB nexora.provider.cache_blob)
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                blob = env['nexora.provider.cache_blob'].sudo().search(
                    [('cache_key', '=', key), ('is_stale', '=', False)], limit=1
                )
                if blob:
                    if blob.expires_at and blob.expires_at < datetime.utcnow():
                        blob.is_stale = True
                    else:
                        value = json.loads(blob.cache_value_json)
                        # Backfill L1 and L2
                        with self._l1_lock:
                            self._l1_cache[key] = CacheEntry(value, blob.expires_at or (datetime.utcnow() + timedelta(seconds=self._default_ttl)))
                        if redis_client:
                            ttl = int((blob.expires_at - datetime.utcnow()).total_seconds()) if blob.expires_at else self._default_ttl
                            if ttl > 0:
                                redis_client.set(f"provider_cache:{key}", blob.cache_value_json, ex=ttl)
                        return value
        except Exception as e:
            _logger.error(f"Cache L3 retrieval failed: {e}")

        return None

    def set(self, key: str, value: Any, ttl_override: Optional[int] = None) -> None:
        """
        Write to all cache levels.
        """
        ttl = ttl_override if ttl_override is not None else self._default_ttl
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        value_json = json.dumps(value)
        
        # Write L1
        with self._l1_lock:
            self._l1_cache[key] = CacheEntry(value, expires_at)
            
        # Write L2
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                redis_client.set(f"provider_cache:{key}", value_json, ex=ttl)
            except Exception as e:
                _logger.error(f"Cache L2 write failed: {e}")
            
        # Write L3
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                blob_model = env['nexora.provider.cache_blob'].sudo()
                existing = blob_model.search([('cache_key', '=', key)], limit=1)
                
                vals = {
                    'cache_value_json': value_json,
                    'expires_at': expires_at,
                    'is_stale': False
                }
                
                if existing:
                    existing.write(vals)
                else:
                    vals['cache_key'] = key
                    blob_model.create(vals)
        except Exception as e:
            _logger.error(f"Cache L3 write failed: {e}")

    def invalidate(self, key: str) -> None:
        """
        Invalidate across all levels.
        """
        # Invalidate L1
        with self._l1_lock:
            if key in self._l1_cache:
                del self._l1_cache[key]
                
        # Invalidate L2
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                redis_client.delete(f"provider_cache:{key}")
            except Exception as e:
                _logger.error(f"Cache L2 invalidation failed: {e}")
                
        # Invalidate L3
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                blobs = env['nexora.provider.cache_blob'].sudo().search([('cache_key', '=', key)])
                for blob in blobs:
                    blob.is_stale = True
        except Exception as e:
            _logger.error(f"Cache L3 invalidation failed: {e}")
