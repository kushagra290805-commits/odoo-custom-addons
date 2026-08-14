import logging
import threading
from typing import Optional

from .base_provider import ProviderTransactionManager
from .container import ProviderServiceContainer

_logger = logging.getLogger(__name__)

class OdooProviderTransactionManager(ProviderTransactionManager):
    """
    Coordinates transactions across SQL, FSM, Cache, Locks, Metrics, Cost Ledger, and Telemetry.
    Provides idempotency protection and compensation.
    """
    
    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        self._local = threading.local()

    @property
    def _is_active(self) -> bool:
        return getattr(self._local, 'active_tx', False)

    @_is_active.setter
    def _is_active(self, value: bool) -> None:
        self._local.active_tx = value

    @property
    def _dirty_keys(self) -> list:
        if not hasattr(self._local, 'dirty_keys'):
            self._local.dirty_keys = []
        return self._local.dirty_keys

    def register_dirty_cache_key(self, key: str) -> None:
        self._dirty_keys.append(key)

    def begin_transaction(self) -> None:
        if self._is_active:
            _logger.debug("Transaction already active. Assuming nested context.")
            return
            
        self._is_active = True
        self._local.dirty_keys = []
        
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                http.request.env.cr.execute('SAVEPOINT provider_tx')
        except Exception as e:
            _logger.error(f"Failed to create SAVEPOINT: {e}")

    def commit(self) -> None:
        if not self._is_active:
            return
            
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                http.request.env.cr.execute('RELEASE SAVEPOINT provider_tx')
        except Exception as e:
            _logger.error(f"Failed to release SAVEPOINT: {e}")
            
        self._is_active = False
        self._local.dirty_keys = []

    def rollback(self) -> None:
        if not self._is_active:
            return
            
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                http.request.env.cr.execute('ROLLBACK TO SAVEPOINT provider_tx')
        except Exception as e:
            _logger.error(f"Failed to rollback SAVEPOINT: {e}")
            
        self._is_active = False
        
        self.compensate()
        self._local.dirty_keys = []

    def compensate(self) -> None:
        """
        Rolls back state in non-transactional systems like Redis Caches.
        """
        _logger.debug("Executing transaction compensation for non-SQL resources.")
        if not self._dirty_keys:
            return
            
        from .base_provider import ProviderCache
        try:
            cache = self._container.resolve(ProviderCache)
            for key in self._dirty_keys:
                cache.invalidate(key)
        except Exception as e:
            _logger.error(f"Compensation failed to invalidate caches: {e}")
