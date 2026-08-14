# -*- coding: utf-8 -*-
"""
Base AI Provider Adapter — Abstract interface all providers must implement.
"""
from odoo import models, api
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

_logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ProviderInput:
    api_key: str = ''
    base_url: str = ''
    timeout: int = 10
    provider_id: str = ''
    compatibility_profile: str = ''

@dataclass
class ProviderDiagnosticResult:
    config_valid: bool = False
    connectivity_state: str = 'unreachable'  # reachable, unreachable, timeout
    authentication_state: str = 'failed'      # authenticated, unauthenticated, failed, no_key
    catalog_state: str = 'never'              # success, failed, stale, never
    catalog_models: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    failure_reason: str = ''
    warnings: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)



class BaseAIAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter_base'
    _description = 'Abstract AI Provider Adapter'

    @api.model
    def _register_hook(self):
        super()._register_hook()
        if self._name == 'nexora.ai_adapter_base':
            return
            
        base_cls = type(self.env['nexora.ai_adapter_base'])
        for method in ['run_diagnostics', 'authenticate', 'fetch_catalog']:
            if getattr(type(self), method) is getattr(base_cls, method):
                raise TypeError(f"Adapter {self._name} must implement {method}()")

    def resolve_provider_input(self, reg=None, credentials=None) -> ProviderInput:
        if reg:
            return ProviderInput(
                api_key=getattr(reg, 'api_key', '') or '',
                base_url=getattr(reg, 'base_url', '') or '',
                timeout=getattr(reg, 'timeout', 10) or 10,
                provider_id=getattr(reg, 'provider_id', '') or '',
                compatibility_profile=getattr(reg, 'compatibility_profile', '') or ''
            )
        if credentials:
            return ProviderInput(
                api_key=credentials.get('api_key', '') or '',
                base_url=credentials.get('base_url', '') or '',
                timeout=credentials.get('timeout', 10) or 10,
                provider_id=credentials.get('provider_id', '') or '',
                compatibility_profile=credentials.get('compatibility_profile', '') or ''
            )
        return ProviderInput()

    def _headers(self, provider_input: ProviderInput) -> Dict[str, str]:
        h = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if provider_input.api_key:
            h['Authorization'] = f'Bearer {provider_input.api_key}'
        return h

    # ── Shared HTTP Layer ──────────────────────────────────────────

    def _request(self, method, url, provider_input, **kwargs):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        from odoo.exceptions import UserError
        
        # Use a class-level shared session if not exists
        if not hasattr(self.__class__, '_shared_session'):
            session = requests.Session()
            # We configure basic retry for connection issues, but ProviderExecutionPolicy handles business logic retries
            retries = Retry(total=1, backoff_factor=0.1, status_forcelist=[502, 503, 504])
            session.mount('http://', HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10))
            session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10))
            self.__class__._shared_session = session

        session = self.__class__._shared_session

        timeout = kwargs.pop('timeout', None)
        if timeout is None:
            timeout = provider_input.timeout if provider_input else 10

        headers = kwargs.pop('headers', None)
        if headers is None:
            headers = self._headers(provider_input) if provider_input else {}
        elif provider_input:
            # Merge with default headers
            h = self._headers(provider_input)
            h.update(headers)
            headers = h

        start_time = time.time()
        try:
            response = session.request(method, url, headers=headers, timeout=timeout, **kwargs)
            return response
        except requests.exceptions.Timeout as e:
            _logger.error(f"HTTP {method} Timeout to {url}: {e}")
            raise  # Let the Execution Policy handle timeout exceptions
        except requests.exceptions.ConnectionError as e:
            _logger.error(f"HTTP {method} ConnectionError to {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            _logger.error(f"HTTP {method} RequestException to {url}: {e}")
            raise
        finally:
            latency = (time.time() - start_time) * 1000
            _logger.debug(f"HTTP {method} {url} completed in {latency:.2f}ms")

    def _http_get(self, url, provider_input, **kwargs):
        return self._request('GET', url, provider_input, **kwargs)

    def _http_post(self, url, provider_input, **kwargs):
        return self._request('POST', url, provider_input, **kwargs)

    # ── Interface Methods ──────────────────────────────────────────

    def get_provider_name(self):
        """Return the canonical provider key (e.g. 'ollama', 'openrouter')."""
        raise NotImplementedError

    def get_display_name(self):
        """Human-readable provider name."""
        raise NotImplementedError

    def get_provider_metadata(self):
        """
        Return provider metadata used for dynamic configuration and capabilities.
        """
        raise NotImplementedError

    def run_diagnostics(self, provider_input: ProviderInput):
        """
        Checks base endpoint reachability and latency without requiring auth.
        Returns: Dict containing latency_ms, connectivity_state, error.
        """
        raise NotImplementedError("run_diagnostics() must be implemented by the adapter.")

    def authenticate(self, provider_input: ProviderInput):
        """
        Validates credentials against an endpoint that strictly requires authorization.
        Returns: Dict containing authentication_state, failure_reason.
        """
        raise NotImplementedError("authenticate() must be implemented by the adapter.")

    def fetch_catalog(self, provider_input: ProviderInput):
        """
        Retrieves and maps the provider's models.
        Returns: List of models, or raises an Exception on failure.
        """
        raise NotImplementedError("fetch_catalog() must be implemented by the adapter.")

    def health_check(self, provider_input: ProviderInput) -> ProviderDiagnosticResult:
        """
        The primary orchestration method that executes diagnostics, auth, and catalog fetch.
        Returns: A ProviderDiagnosticResult instance.
        """
        import time
        res = ProviderDiagnosticResult()
        
        if not provider_input.base_url:
            res.failure_reason = 'Missing Base URL'
            res.config_valid = False
            return res
            
        needs_key = provider_input.compatibility_profile not in ['ollama_native', 'local']
        if needs_key and not provider_input.api_key:
            res.failure_reason = 'Missing API Key'
            res.config_valid = False
            res.authentication_state = 'no_key'
            return res
            
        res.config_valid = True
        
        # 1. Connectivity
        start_ts = time.time()
        try:
            diag = self.run_diagnostics(provider_input)
            res.connectivity_state = diag.get('connectivity_state', 'unreachable')
            res.latency_ms = diag.get('latency_ms', (time.time() - start_ts) * 1000)
            if 'error' in diag:
                res.failure_reason = diag['error']
        except Exception as e:
            res.connectivity_state = 'unreachable'
            res.failure_reason = str(e)
            
        if res.connectivity_state != 'reachable':
            return res
            
        # 2. Authentication
        try:
            auth = self.authenticate(provider_input)
            res.authentication_state = auth.get('authentication_state', 'failed')
            if 'error' in auth:
                res.failure_reason = auth['error']
        except Exception as e:
            res.authentication_state = 'failed'
            res.failure_reason = str(e)
            
        if res.authentication_state != 'authenticated':
            return res
            
        # 3. Catalog Fetch
        try:
            models = self.fetch_catalog(provider_input)
            res.catalog_models = models
            res.catalog_state = 'success'
        except Exception as e:
            res.catalog_state = 'failed'
            res.warnings.append(f"Catalog sync failed: {str(e)}")
            
        return res

    def is_available(self, provider_input: ProviderInput = None):
        """Check whether the provider is reachable and configured."""
        raise NotImplementedError

    def list_models(self, credentials=None):
        """Return a list of model name strings available on this provider."""
        return []

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        """
        Send a chat-style completion request.

        Parameters
        ----------
        messages : list[dict]
            OpenAI-style messages: [{'role': 'system'|'user'|'assistant', 'content': str}]
        model : str | None
            Override the default model.
        temperature : float
        max_tokens : int
        json_mode : bool
            If True, request a JSON response where the provider supports it.
        timeout : int
            Per-request timeout in seconds.
        retries : int
            Number of retries on transient failures.

        Returns
        -------
        dict  with keys:
            provider, model, prompt, response, token_usage,
            execution_time, error
        """
        raise NotImplementedError

    def generate_code(self, prompt, context_text='', credentials=None, model=None,
                      temperature=0.3, max_tokens=4096, timeout=120,
                      retries=2):
        """
        Convenience wrapper for code-generation tasks.
        Delegates to chat_completion with a system prompt tuned for code.
        """
        messages = [
            {'role': 'system', 'content': (
                'You are a senior full-stack web developer. '
                'Return ONLY valid code. No markdown fences. No explanations unless requested.'
            )},
        ]
        if context_text:
            messages.append({'role': 'user', 'content': f'Context:\n{context_text}'})
        messages.append({'role': 'user', 'content': prompt})
        return self.chat_completion(
            messages, credentials=credentials, model=model, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout, retries=retries
        )

    # ── Helpers ────────────────────────────────────────────────────

