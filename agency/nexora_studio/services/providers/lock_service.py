import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

from .base_provider import LockService, LockAcquisitionResult, LockBackend

_logger = logging.getLogger(__name__)

class MemoryLock:
    def __init__(self):
        self.lock = threading.Lock()
        self.holder_id: Optional[str] = None
        self.acquired_at: Optional[datetime] = None
        self.expires_at: Optional[datetime] = None

class OdooLockService(LockService):
    """
    Distributed Lock Service for the Unified Provider Platform.
    Implements Memory locking, with stubs for PostgreSQL and Redis.
    The backend is configurable via Odoo system parameters.
    """

    def __init__(self, default_backend: LockBackend = LockBackend.MEMORY):
        self._default_backend = default_backend
        self._memory_locks: Dict[str, MemoryLock] = {}
        self._dict_lock = threading.Lock()

    def get_backend(self) -> LockBackend:
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                param = http.request.env['ir.config_parameter'].sudo().get_param('agency.provider_lock_backend', 'memory')
                if param == 'postgresql': return LockBackend.POSTGRESQL
                if param == 'redis': return LockBackend.REDIS
        except Exception:
            pass
        return self._default_backend

    def acquire(self, lock_key: str, holder_id: str, timeout_ms: int = 5000, ttl_ms: int = 30000) -> LockAcquisitionResult:
        backend = self.get_backend()
        if backend == LockBackend.POSTGRESQL:
            res = self._acquire_postgres(lock_key, holder_id, timeout_ms, ttl_ms)
            if res: return res
        elif backend == LockBackend.REDIS:
            res = self._acquire_redis(lock_key, holder_id, timeout_ms, ttl_ms)
            if res: return res
            
        return self._acquire_memory(lock_key, holder_id, timeout_ms, ttl_ms)

    def release(self, lock_key: str, holder_id: str) -> bool:
        backend = self.get_backend()
        if backend == LockBackend.POSTGRESQL:
            if self._release_postgres(lock_key, holder_id): return True
        elif backend == LockBackend.REDIS:
            if self._release_redis(lock_key, holder_id): return True
            
        return self._release_memory(lock_key, holder_id)

    def extend(self, lock_key: str, holder_id: str, ttl_ms: int) -> bool:
        backend = self.get_backend()
        if backend == LockBackend.REDIS:
            if self._extend_redis(lock_key, holder_id, ttl_ms): return True
        # PG advisory locks do not support TTL extending directly in the same way, rely on connection lifetime or fallback
        return self._extend_memory(lock_key, holder_id, ttl_ms)

    def is_held(self, lock_key: str) -> bool:
        backend = self.get_backend()
        if backend == LockBackend.REDIS:
            return self._is_held_redis(lock_key)
        # For PG, querying pg_locks is complex without holder id context, fallback to memory logic for in-process
        with self._dict_lock:
            if lock_key not in self._memory_locks:
                return False
            mem_lock = self._memory_locks[lock_key]
            if mem_lock.expires_at and datetime.utcnow() > mem_lock.expires_at:
                return False
            return mem_lock.holder_id is not None

    # ── Redis Backend Implementation ─────────────────────────────────────────
    def _get_redis_client(self):
        try:
            import redis
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                redis_url = http.request.env['ir.config_parameter'].sudo().get_param('agency.redis_url', 'redis://localhost:6379/0')
                return redis.from_url(redis_url)
        except Exception:
            pass
        return None

    def _acquire_redis(self, lock_key: str, holder_id: str, timeout_ms: int, ttl_ms: int) -> Optional[LockAcquisitionResult]:
        client = self._get_redis_client()
        if not client: return None
        import time
        start = time.time()
        timeout_seconds = timeout_ms / 1000.0
        while True:
            if client.set(f"provider_lock:{lock_key}", holder_id, px=ttl_ms, nx=True):
                return LockAcquisitionResult(True, lock_key, holder_id, datetime.utcnow(), datetime.utcnow() + timedelta(milliseconds=ttl_ms))
            if time.time() - start > timeout_seconds:
                return LockAcquisitionResult(False, lock_key, "", None, None)
            time.sleep(0.05)

    def _release_redis(self, lock_key: str, holder_id: str) -> bool:
        client = self._get_redis_client()
        if not client: return False
        script = """
        if redis.call("get",KEYS[1]) == ARGV[1] then
            return redis.call("del",KEYS[1])
        else
            return 0
        end
        """
        return bool(client.eval(script, 1, f"provider_lock:{lock_key}", holder_id))
        
    def _extend_redis(self, lock_key: str, holder_id: str, ttl_ms: int) -> bool:
        client = self._get_redis_client()
        if not client: return False
        script = """
        if redis.call("get",KEYS[1]) == ARGV[1] then
            return redis.call("pexpire",KEYS[1],ARGV[2])
        else
            return 0
        end
        """
        return bool(client.eval(script, 1, f"provider_lock:{lock_key}", holder_id, ttl_ms))

    def _is_held_redis(self, lock_key: str) -> bool:
        client = self._get_redis_client()
        if not client: return False
        return client.exists(f"provider_lock:{lock_key}") > 0

    # ── PostgreSQL Backend Implementation ────────────────────────────────────
    def _acquire_postgres(self, lock_key: str, holder_id: str, timeout_ms: int, ttl_ms: int) -> Optional[LockAcquisitionResult]:
        try:
            from odoo import http
            import zlib, time
            if not http.request or not hasattr(http.request, 'env'): return None
            env = http.request.env
            lock_id = zlib.crc32(lock_key.encode('utf-8')) - 2147483648
            start = time.time()
            timeout_seconds = timeout_ms / 1000.0
            while True:
                env.cr.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
                if env.cr.fetchone()[0]:
                    return LockAcquisitionResult(True, lock_key, holder_id, datetime.utcnow(), datetime.utcnow() + timedelta(milliseconds=ttl_ms))
                if time.time() - start > timeout_seconds:
                    return LockAcquisitionResult(False, lock_key, "", None, None)
                time.sleep(0.05)
        except Exception:
            return None

    def _release_postgres(self, lock_key: str, holder_id: str) -> bool:
        try:
            from odoo import http
            import zlib
            if not http.request or not hasattr(http.request, 'env'): return False
            env = http.request.env
            lock_id = zlib.crc32(lock_key.encode('utf-8')) - 2147483648
            env.cr.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
            return env.cr.fetchone()[0]
        except Exception:
            return False

    # ── Memory Backend Implementation ────────────────────────────────────────

    def _acquire_memory(self, lock_key: str, holder_id: str, timeout_ms: int, ttl_ms: int) -> LockAcquisitionResult:
        with self._dict_lock:
            if lock_key not in self._memory_locks:
                self._memory_locks[lock_key] = MemoryLock()
            mem_lock = self._memory_locks[lock_key]

        start_time = time.time()
        timeout_seconds = timeout_ms / 1000.0

        while True:
            # Check for expiration of existing lock
            if mem_lock.holder_id is not None and mem_lock.expires_at:
                if datetime.utcnow() > mem_lock.expires_at:
                    # Lock expired, forcefully release it
                    mem_lock.holder_id = None
                    if mem_lock.lock.locked():
                        try:
                            mem_lock.lock.release()
                        except RuntimeError:
                            pass

            if mem_lock.lock.acquire(blocking=False):
                mem_lock.holder_id = holder_id
                mem_lock.acquired_at = datetime.utcnow()
                mem_lock.expires_at = mem_lock.acquired_at + timedelta(milliseconds=ttl_ms)
                
                return LockAcquisitionResult(
                    acquired=True,
                    lock_key=lock_key,
                    holder_id=holder_id,
                    acquired_at=mem_lock.acquired_at,
                    expires_at=mem_lock.expires_at
                )

            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                return LockAcquisitionResult(
                    acquired=False,
                    lock_key=lock_key,
                    holder_id=mem_lock.holder_id,
                    acquired_at=mem_lock.acquired_at,
                    expires_at=mem_lock.expires_at
                )

            time.sleep(0.01)

    def _release_memory(self, lock_key: str, holder_id: str) -> bool:
        with self._dict_lock:
            if lock_key not in self._memory_locks:
                return False
            mem_lock = self._memory_locks[lock_key]

        if mem_lock.holder_id == holder_id:
            mem_lock.holder_id = None
            mem_lock.acquired_at = None
            mem_lock.expires_at = None
            try:
                mem_lock.lock.release()
                return True
            except RuntimeError:
                return False
        return False

    def _extend_memory(self, lock_key: str, holder_id: str, ttl_ms: int) -> bool:
        with self._dict_lock:
            if lock_key not in self._memory_locks:
                return False
            mem_lock = self._memory_locks[lock_key]

        if mem_lock.holder_id == holder_id:
            mem_lock.expires_at = datetime.utcnow() + timedelta(milliseconds=ttl_ms)
            return True
        return False
