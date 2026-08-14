# -*- coding: utf-8 -*-
"""
Provider Execution Policy

Responsible for retries, timeout policy, circuit breaking, and HTTP failure classification.
Independent of structural provider health.
"""
from odoo import models, api
import requests
import time
import logging
from typing import Callable, Dict, Any
from .ai_execution_context import AIExecutionContext

_logger = logging.getLogger(__name__)


class RateLimitException(Exception):
    """Specific exception to indicate provider rate limits (429)."""
    pass

class CircuitBreakerOpenException(Exception):
    """Specific exception to indicate provider circuit breaker is open."""
    pass


# Global transient dictionary for circuit breakers (clears on restart).
# Maps provider_key -> {'failures': int, 'next_attempt_at': float}
_CIRCUIT_BREAKERS = {}


class ProviderExecutionPolicy(models.AbstractModel):
    _name = 'nexora.provider_execution_policy'
    _description = 'AI Provider Execution Policy & Circuit Breaker'

    def _is_circuit_open(self, provider_key: str) -> bool:
        cb = _CIRCUIT_BREAKERS.get(provider_key)
        if not cb:
            return False
        
        # If open, check cooldown (e.g. 60 seconds)
        if cb['failures'] >= 3:
            if time.time() < cb['next_attempt_at']:
                return True
            else:
                # Half-open: allow one request through to test
                pass
        return False
        
    def _record_success(self, provider_key: str):
        if provider_key in _CIRCUIT_BREAKERS:
            del _CIRCUIT_BREAKERS[provider_key]
            
    def _record_failure(self, provider_key: str):
        cb = _CIRCUIT_BREAKERS.get(provider_key, {'failures': 0, 'next_attempt_at': 0})
        cb['failures'] += 1
        # Cooldown of 60 seconds when tripped
        if cb['failures'] >= 3:
            cb['next_attempt_at'] = time.time() + 60
        _CIRCUIT_BREAKERS[provider_key] = cb


    @api.model
    def execute(self, ctx: AIExecutionContext, fn: Callable) -> Dict[str, Any]:
        """
        Execute an external HTTP call governed by retry policies and circuit breakers.
        fn should accept (timeout: int) and return the provider's text response and token usage dict.
        """
        provider_key = ctx.provider
        
        if self._is_circuit_open(provider_key):
            _logger.warning("Circuit breaker OPEN for provider: %s", provider_key)
            raise CircuitBreakerOpenException(f"Circuit breaker is open for {provider_key}")
            
        last_error = None
        retries = ctx.retries
        timeout = ctx.timeout
        
        for attempt in range(1, retries + 2):
            start = time.time()
            try:
                # Delegate to the adapter logic to make the request
                result = fn(timeout)
                self._record_success(provider_key)
                
                # result is expected to be a dict with 'response' and 'token_usage'
                return {
                    'response': result.get('response', ''),
                    'token_usage': result.get('token_usage', 0),
                    'execution_time': round(time.time() - start, 3),
                    'error': None,
                    'http_status': 200,
                    'retry_count': attempt - 1,
                    'failure_classification': None
                }
                
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 500
                latency = round(time.time() - start, 3)
                
                if status in (401, 403, 404):
                    # Fail immediately
                    self._record_failure(provider_key)
                    _logger.error("Execution Policy: %s returned %s. Aborting.", provider_key, status)
                    return self._build_error(e, latency, attempt - 1, status, 'AUTH_OR_CONFIG_ERROR')
                    
                elif status == 429:
                    # Rate limit -> Bubble up so CostRouter can fallback
                    _logger.warning("Execution Policy: %s returned 429 Rate Limit.", provider_key)
                    raise RateLimitException("Provider rate limit reached.")
                    
                elif status >= 500:
                    # Server Error -> Exponential backoff
                    last_error = e
                    _logger.warning("Execution Policy: %s returned %s. Retrying...", provider_key, status)
                    
            except requests.exceptions.ReadTimeout as e:
                # ReadTimeout -> Standard retry + circuit breaker
                latency = round(time.time() - start, 3)
                last_error = e
                self._record_failure(provider_key)
                _logger.warning("Execution Policy: %s ReadTimeout (timeout=%s). Retrying...", provider_key, timeout)
                
            except Exception as e:
                # Unknown network failure
                latency = round(time.time() - start, 3)
                last_error = e
                self._record_failure(provider_key)
                _logger.warning("Execution Policy: %s Unexpected error: %s", provider_key, str(e))
                
            if attempt <= retries:
                time.sleep(min(2 ** attempt, 10))

        # All retries exhausted
        self._record_failure(provider_key)
        return self._build_error(last_error, round(time.time() - start, 3), retries, 500, 'RETRIES_EXHAUSTED')
        
    def _build_error(self, exc: Exception, latency: float, retry_count: int, status: int, classification: str) -> Dict[str, Any]:
        return {
            'response': '',
            'token_usage': 0,
            'execution_time': latency,
            'error': str(exc),
            'http_status': status,
            'retry_count': retry_count,
            'failure_classification': classification
        }

