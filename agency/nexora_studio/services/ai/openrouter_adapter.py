# -*- coding: utf-8 -*-
"""
OpenRouter Adapter - access any model via the OpenRouter API.

Configuration (ir.config_parameter):
    nexora.openrouter.api_key        - Bearer token
    nexora.openrouter.base_url       - API endpoint (default: https://openrouter.ai/api/v1)
    nexora.openrouter.default_model  - Default model (default: tencent/hy3:free)
    nexora.openrouter.enabled        - Enable/disable (default: True)
    nexora.openrouter.timeout        - Request timeout in seconds (default: 120)
"""
from odoo import models
import logging

_logger = logging.getLogger(__name__)

_DEFAULTS = {
    'base_url': 'https://openrouter.ai/api/v1',
    'default_model': 'tencent/hy3:free',
    'enabled': 'True',
    'timeout': '120',
}


class OpenRouterAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.openrouter'
    _inherit = 'nexora.ai_adapter.generic_openai'
    _description = 'OpenRouter AI Provider Adapter'


    # -- Interface -----------------------------------------------------------

    def get_provider_name(self):
        return 'openrouter'

    def get_display_name(self):
        return 'OpenRouter'

    def get_provider_metadata(self):
        return {
            'name': 'OpenRouter',
            'key': 'openrouter',
            'required_config': ['api_key', 'base_url', 'timeout'],
            'default_base_url': 'https://openrouter.ai/api/v1',
            'supports_catalog_sync': True,
        }

    def run_diagnostics(self, provider_input):
        try:
            r = self._http_get(f'{ep}/models', provider_input, timeout=5)
            return {
                'connectivity_state': 'reachable',
                'latency_ms': (time.time() - start) * 1000
            }
        except Exception as e:
            if 'Timeout' in str(type(e)):
                return {'connectivity_state': 'unreachable', 'error': 'Endpoint unreachable or timed out'}
            return {'connectivity_state': 'unreachable', 'error': str(e)}

    def fetch_catalog(self, provider_input):
        ep = provider_input.base_url
        if ep:
            ep = ep.rstrip('/')
        if not ep:
            return []
        
        try:
            r = self._http_get(f'{ep}/models', provider_input, timeout=10)
            if r.status_code == 200:
                data = r.json().get('data', [])
                return [self._normalize_model_data(m) for m in data]
            return []
        except Exception as e:
            _logger.error(f"Failed to fetch catalog from OpenRouter: {e}")
            return []

    def authenticate(self, provider_input):
        key = provider_input.api_key
        base_url = provider_input.base_url.rstrip('/') if provider_input.base_url else 'https://openrouter.ai/api/v1'
        if not key:
            return {'authentication_state': 'failed', 'error': 'No API key provided'}
        try:
            r = self._http_get(
                f'{base_url}/auth/key',
                provider_input,
                timeout=10,
            )
            if r.status_code == 200:
                return {'authentication_state': 'authenticated'}
            else:
                return {'authentication_state': 'failed', 'error': f'HTTP {r.status_code}: {r.text}'}
        except Exception as e:
            return {'authentication_state': 'failed', 'error': str(e)}

    def _headers(self, provider_input):
        h = super()._headers(provider_input)
        h.update({
            'HTTP-Referer': 'https://nexora.studio',
            'X-Title': 'Nexora Studio',
        })
        return h

    def _normalize_model_data(self, m):
        arch = m.get('architecture', {})
        pricing = m.get('pricing', {})
        top_provider = m.get('top_provider', {})
        
        # OpenRouter pricing is per token in docs, but API returns floats, we multiply appropriately if needed
        # but let's just take raw floats.
        price_prompt = float(pricing.get('prompt', 0) or 0)
        price_completion = float(pricing.get('completion', 0) or 0)
        
        context_length = m.get('context_length') or top_provider.get('context_length') or 4096
        max_output_tokens = top_provider.get('max_completion_tokens') or 4096

        return {
            'id': m.get('id'),
            'name': m.get('name') or m.get('id'),
            'context_length': context_length,
            'max_output_tokens': max_output_tokens,
            'supports_streaming': True,
            'supports_tool_calling': 'tools' in (arch.get('instruct_type') or ''),
            'supports_vision': 'image' in arch.get('input_modalities', []),
            'supports_json': False, # Conservative default
            'supports_reasoning': bool(m.get('reasoning', False)),
            'supports_embeddings': False,
            'price_prompt': price_prompt,
            'price_completion': price_completion,
        }

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=None,
                        retries=2):
        provider_input = self.resolve_provider_input(credentials=credentials)
        key = provider_input.api_key
        base_url = provider_input.base_url.rstrip('/') if provider_input.base_url else 'https://openrouter.ai/api/v1'
        if not key:
            return {
                'provider': 'openrouter', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': (
                    'OpenRouter API key not configured. '
                    'Set it via Settings -> AI Configuration.'
                ),
            }

        # Model must be provided by the caller (ProviderManager)
        if not model:
            return {
                'provider': 'openrouter', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': 'No model specified for execution.',
            }
        req_timeout = timeout if timeout is not None else 120
        prompt_text = '\n'.join(m.get('content', '') for m in messages)

        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://nexora.studio',
            'X-Title': 'Nexora Studio',
        }
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        # OpenRouter throws HTTP 400 if response_format is used on models 
        # that don't explicitly support it (like many free models).
        # We rely on prompt engineering (which is already done by the stages)
        # to enforce JSON output rather than strict API schema constraints.
        # if json_mode:
        #     payload['response_format'] = {'type': 'json_object'}

        r = self._http_post(
            f'{base_url}/chat/completions',
            provider_input,
            json=payload,
            timeout=req_timeout,
        )
        r.raise_for_status()
        
        data = r.json()
        choice = data.get('choices', [{}])[0]
        usage = data.get('usage', {})
        
        return {
            'provider': 'openrouter',
            'model': model,
            'prompt': prompt_text,
            'response': choice.get('message', {}).get('content', ''),
            'token_usage': usage.get('total_tokens', 0),
            'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0),
            'cost': usage.get('cost', 0),
            'error': None,
        }
