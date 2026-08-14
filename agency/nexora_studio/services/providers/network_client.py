import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, Optional
import logging
from odoo import tools

import warnings

_logger = logging.getLogger(__name__)

warnings.warn(
    "ProviderNetworkClient and CircuitBreaker are deprecated in Phase 18.3.1. "
    "Use BaseAIAdapter's shared requests.Session layer instead.",
    DeprecationWarning, stacklevel=2
)

class CircuitBreaker:
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        # Dynamic configuration from Odoo tools.config
        self.failure_threshold = int(tools.config.get(f"{provider_id}_cb_threshold", 5))
        self.recovery_timeout = int(tools.config.get(f"{provider_id}_cb_recovery", 60))
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            if self.state != "OPEN":
                _logger.warning(f"Circuit Breaker OPENED for {self.provider_id} after {self.failures} failures.")
            self.state = "OPEN"
            self._emit_telemetry("circuit_breaker_open")

    def record_success(self):
        if self.state != "CLOSED":
            _logger.info(f"Circuit Breaker CLOSED for {self.provider_id}. Recovery successful.")
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "CLOSED": return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN": return True
        return False

    def _emit_telemetry(self, event: str):
        _logger.info(f"TELEMETRY: Provider={self.provider_id} Event={event} State={self.state}")

class ProviderNetworkClient:
    """Enterprise-grade network client for providers with Auth, Telemetry, and Caching."""
    
    _sessions: Dict[str, requests.Session] = {}
    _breakers: Dict[str, CircuitBreaker] = {}
    _cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_session(cls, provider_id: str) -> requests.Session:
        if provider_id not in cls._sessions:
            retries = int(tools.config.get(f"{provider_id}_retries", 3))
            backoff_factor = float(tools.config.get(f"{provider_id}_backoff", 0.5))
            pool_size = int(tools.config.get(f"{provider_id}_pool_size", 100))
            
            session = requests.Session()
            retry = Retry(
                total=retries,
                read=retries,
                connect=retries,
                backoff_factor=backoff_factor,
                status_forcelist=(500, 502, 503, 504, 429),
                allowed_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
            )
            adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=pool_size)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            cls._sessions[provider_id] = session
        return cls._sessions[provider_id]

    @classmethod
    def get_breaker(cls, provider_id: str) -> CircuitBreaker:
        if provider_id not in cls._breakers:
            cls._breakers[provider_id] = CircuitBreaker(provider_id)
        return cls._breakers[provider_id]

    @classmethod
    def request(cls, provider_id: str, method: str, url: str, **kwargs) -> requests.Response:
        breaker = cls.get_breaker(provider_id)
        if not breaker.can_execute():
            raise Exception(f"Circuit Breaker OPEN for provider: {provider_id}")
            
        session = cls.get_session(provider_id)
        timeout = int(tools.config.get(f"{provider_id}_timeout", 10))
        ttl = int(tools.config.get(f"{provider_id}_cache_ttl", 300))
        
        # Simple memory cache for GET requests
        cache_key = f"{provider_id}:{method}:{url}"
        if method.upper() == "GET" and cache_key in cls._cache:
            entry = cls._cache[cache_key]
            if time.time() - entry["time"] < ttl:
                _logger.debug(f"TELEMETRY: Cache HIT for {cache_key}")
                return entry["response"]
        
        _logger.debug(f"TELEMETRY: Cache MISS for {cache_key}")
        
        try:
            start_time = time.time()
            response = session.request(method, url, timeout=timeout, **kwargs)
            latency = (time.time() - start_time) * 1000
            
            _logger.info(f"TELEMETRY: Provider={provider_id} Method={method} URL={url} Status={response.status_code} Latency={latency:.2f}ms")
            
            if response.status_code >= 500:
                breaker.record_failure()
            else:
                breaker.record_success()
                if method.upper() == "GET" and response.status_code == 200:
                    cls._cache[cache_key] = {"time": time.time(), "response": response}
                
            return response
            
        except requests.exceptions.RequestException as e:
            breaker.record_failure()
            _logger.error(f"TELEMETRY: Provider={provider_id} Failure={str(e)}")
            raise Exception(f"Provider {provider_id} network request failed: {str(e)}")
