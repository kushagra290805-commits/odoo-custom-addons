import threading
import hashlib
import time
from typing import Dict, Optional, Tuple

from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import McpConfiguration
from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import McpTransport, TransportBinding
from odoo.addons.nexora_studio.services.connector.sdk.logging import get_logger

_logger = get_logger(__name__)

class SessionTransportPool:
    """
    Manages session-bound McpTransport instances.
    Provides isolated transport creation per session identity.
    """
    def __init__(self, config: McpConfiguration):
        self.config = config
        self._pool: Dict[str, Tuple[McpTransport, float]] = {}  # hash -> (transport, last_used_at)
        self._lock = threading.Lock()
        self.ttl_seconds = 600  # 10 minutes default TTL
        # Phase 44.2 (W7 / ADR-0067): hard upper bound so a burst of distinct
        # session identities cannot grow the pool without limit. Eviction is
        # LRU when the bound is reached.
        self.max_size = 100

    def get_transport(self, session_identity: str) -> McpTransport:
        """
        Acquire a transport bound to the given session identity.
        Derives an opaque cryptographic cache key.
        """
        # 1. Derive an opaque cryptographic identifier for cache isolation
        # Never use raw tokens as dictionary keys.
        session_hash = hashlib.sha256(session_identity.encode('utf-8')).hexdigest()
        
        # 2. Attempt fast-path retrieval
        with self._lock:
            self._evict_expired_locked() # piggyback cleanup
            if session_hash in self._pool:
                transport, _ = self._pool[session_hash]
                if transport.is_connected():
                    self._pool[session_hash] = (transport, time.time())
                    return transport
                else:
                    _logger.warning("Session transport disconnected, evicting.")
                    self._evict_locked(session_hash)
            
        # 3. Create new transport outside lock (to prevent blocking all sessions on slow network)
        binding = TransportBinding(
            location=self.config.session_binding_location,
            name=self.config.session_binding_field,
            value=session_identity
        )
        transport = McpTransport(self.config, transport_binding=binding)
        transport.connect()
        
        # 4. Store in pool
        with self._lock:
            # Re-check if another thread beat us to it while we were connecting
            if session_hash in self._pool:
                existing_transport, _ = self._pool[session_hash]
                if existing_transport.is_connected():
                    # Another thread won the race. Shut down the one we just created and use theirs.
                    transport.disconnect()
                    self._pool[session_hash] = (existing_transport, time.time())
                    return existing_transport
                else:
                    self._evict_locked(session_hash)

            # Enforce the hard size bound (W7): evict least-recently-used
            # entries while at capacity. Runs under self._lock, reusing the
            # same lock/re-check pattern as the race handling above.
            while len(self._pool) >= self.max_size:
                lru_hash = min(self._pool, key=lambda h: self._pool[h][1])
                _logger.info("Session transport pool at capacity (%s); evicting LRU %s", self.max_size, lru_hash[:8])
                self._evict_locked(lru_hash)

            self._pool[session_hash] = (transport, time.time())
            return transport

    def _evict_locked(self, session_hash: str):
        """Evict a specific transport by hash without acquiring lock."""
        if session_hash in self._pool:
            transport, _ = self._pool.pop(session_hash)
            try:
                transport.disconnect()
            except Exception as e:
                _logger.error(f"Error disconnecting evicted transport: {e}")

    def _evict_expired_locked(self):
        """Evict all expired transports without acquiring lock."""
        now = time.time()
        expired = [h for h, (_, last_used) in self._pool.items() if (now - last_used) > self.ttl_seconds]
        for h in expired:
            _logger.info(f"Evicting expired session transport {h[:8]}")
            self._evict_locked(h)

    def shutdown_all(self):
        """Gracefully shut down all pooled transports."""
        with self._lock:
            for transport, _ in self._pool.values():
                try:
                    transport.disconnect()
                except Exception as e:
                    _logger.error(f"Error disconnecting transport during shutdown: {e}")
            self._pool.clear()
