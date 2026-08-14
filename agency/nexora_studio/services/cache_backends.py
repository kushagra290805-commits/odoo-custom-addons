# -*- coding: utf-8 -*-
"""
Cache backends for Nexora Studio capability caching.

The MemoryCacheBackend is the default production backend.
The RedisCacheBackend is available when redis-py is installed
and a Redis server is configured.
"""
from odoo.tools import config
import logging
import json

_logger = logging.getLogger(__name__)


class AbstractCacheBackend:
    """Interface for cache backends."""

    def set(self, key, value):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError


class MemoryCacheBackend(AbstractCacheBackend):
    """In-process dictionary cache. Default backend."""

    def __init__(self):
        self._data = {}

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)

    def clear(self):
        self._data.clear()

    def delete(self, key):
        self._data.pop(key, None)


class RedisCacheBackend(AbstractCacheBackend):
    """
    Redis-backed cache.  Falls back to MemoryCacheBackend if
    redis-py is not installed or the server is unreachable.
    """

    def __init__(self):
        self._client = None
        self._fallback = MemoryCacheBackend()
        self._prefix = config.get('nexora_redis_prefix', 'nexora:')
        try:
            import redis
            host = config.get('nexora_redis_host', 'localhost')
            port = int(config.get('nexora_redis_port', 6379))
            db = int(config.get('nexora_redis_db', 0))
            password = config.get('nexora_redis_password', None)
            self._client = redis.Redis(
                host=host, port=port, db=db, password=password,
                socket_connect_timeout=2, decode_responses=True,
            )
            self._client.ping()
            _logger.info(
                'RedisCacheBackend connected to %s:%s db=%s', host, port, db
            )
        except ImportError:
            _logger.warning(
                'redis-py is not installed. '
                'RedisCacheBackend falling back to MemoryCacheBackend.'
            )
            self._client = None
        except Exception as e:
            _logger.warning(
                'Could not connect to Redis (%s). '
                'Falling back to MemoryCacheBackend.', e
            )
            self._client = None

    def _key(self, key):
        return f'{self._prefix}{key}'

    def set(self, key, value):
        if self._client:
            try:
                self._client.set(self._key(key), json.dumps(value, default=str))
                return
            except Exception:
                pass
        self._fallback.set(key, value)

    def get(self, key):
        if self._client:
            try:
                raw = self._client.get(self._key(key))
                if raw is not None:
                    return json.loads(raw)
                return None
            except Exception:
                pass
        return self._fallback.get(key)

    def clear(self):
        if self._client:
            try:
                keys = self._client.keys(f'{self._prefix}*')
                if keys:
                    self._client.delete(*keys)
                return
            except Exception:
                pass
        self._fallback.clear()

    def delete(self, key):
        if self._client:
            try:
                self._client.delete(self._key(key))
                return
            except Exception:
                pass
        self._fallback.delete(key)


class CacheBackendFactory:
    _instance = None

    @classmethod
    def get_backend(cls) -> AbstractCacheBackend:
        if cls._instance is None:
            backend_type = config.get('nexora_cache_backend', 'memory')
            if backend_type == 'redis':
                cls._instance = RedisCacheBackend()
            else:
                cls._instance = MemoryCacheBackend()
        return cls._instance
