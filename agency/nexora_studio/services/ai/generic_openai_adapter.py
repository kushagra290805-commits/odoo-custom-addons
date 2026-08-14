# -*- coding: utf-8 -*-
"""
Generic OpenAI-Compatible Adapter — works with any provider that exposes
the standard /v1/chat/completions endpoint (LM Studio, vLLM, etc.).
"""
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class GenericOpenAIAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.generic_openai'
    _inherit = 'nexora.ai_adapter_base'
    _description = 'Generic OpenAI-Compatible AI Provider Adapter'

    def get_provider_name(self):
        return 'generic_openai'

    def get_display_name(self):
        return 'Generic OpenAI-Compatible'

    def get_provider_metadata(self):
        return {
            'name': 'Generic OpenAI-Compatible',
            'key': 'generic_openai',
            'required_config': ['base_url', 'timeout'],
            'default_base_url': 'http://localhost:8000/v1',
            'supports_catalog_sync': True,
        }

    def is_available(self, credentials=None):
        return False

    def run_diagnostics(self, provider_input):
        """Ping the base_url or /models just for reachability."""
        try:
            r = self._http_get(f'{ep}/models', provider_input, timeout=5)
            # Even if it returns 401, the server is reachable
            return {
                'connectivity_state': 'reachable',
                'latency_ms': (time.time() - start) * 1000
            }
        except Exception as e:
            if 'Timeout' in str(type(e)):
                return {'connectivity_state': 'unreachable', 'error': 'Endpoint unreachable or timed out'}
        except Exception as e:
            return {'connectivity_state': 'unreachable', 'error': str(e)}

    def authenticate(self, provider_input):
        """For generic OpenAI, we hit /models and explicitly check for 401/403. If 200, we must do a dummy completion to prove auth since /models might be public."""
        ep = provider_input.base_url.rstrip('/')
        try:
            r = self._http_get(f'{ep}/models', provider_input, timeout=5)
            if r.status_code in [401, 403]:
                return {'authentication_state': 'failed', 'error': f'HTTP {r.status_code}: Unauthorized'}
                
            # If 200, it might be public. Let's do a dummy completion
            payload = {
                'model': 'dummy',
                'messages': [{'role': 'user', 'content': 'test'}],
                'max_tokens': 1
            }
            r_chat = self._http_post(f'{ep}/chat/completions', provider_input, json=payload, timeout=5)
            if r_chat.status_code in [401, 403]:
                return {'authentication_state': 'failed', 'error': 'Authentication failed on /chat/completions'}
                
            # If it returns 404 (model not found), that means auth passed but model doesn't exist, which is fine!
            return {'authentication_state': 'authenticated'}
        except Exception as e:
            return {'authentication_state': 'failed', 'error': str(e)}

    def fetch_catalog(self, provider_input):
        ep = provider_input.base_url
        if ep:
            ep = ep.rstrip('/')
        if not ep:
            return []
        try:
            r = self._http_get(f'{ep}/models', provider_input, timeout=10)
            r.raise_for_status()
            
            data = r.json().get('data', [])
            return [self._normalize_model_data(m) for m in data]
        except Exception as e:
            if 'RequestException' in str(type(e)) or 'HTTPError' in str(type(e)):
                _logger.error("Error fetching catalog from %s: %s", ep, e)
                raise
            _logger.error("Unexpected error parsing catalog from %s: %s", ep, e)
            raise
            
    def _normalize_model_data(self, m_data):
        """
        Normalize standard OpenAI /models response.
        Uses conservative defaults since standard API doesn't provide rich metadata.
        """
        return {
            'id': m_data.get('id'),
            'name': m_data.get('name') or m_data.get('id'),
            'context_length': m_data.get('context_length') or 4096,  # Conservative default
            'max_output_tokens': m_data.get('max_tokens') or 4096,
            'supports_streaming': True,  # OpenAI compatible usually supports streaming
            'supports_tool_calling': False, # Conservative default
            'supports_vision': False,
            'supports_json': False,
            'supports_reasoning': False,
            'supports_embeddings': False,
            'price_prompt': 0.0,
            'price_completion': 0.0,
        }

    def list_models(self, credentials=None):
        catalog = self.fetch_catalog(credentials)
        return [m['id'] for m in catalog]

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        provider_input = self.resolve_provider_input(credentials=credentials)
        ep = provider_input.base_url.rstrip('/') if provider_input.base_url else None
        if not ep:
            return {
                'provider': 'generic_openai', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': 'Generic OpenAI endpoint not configured',
            }
            
        if not model:
            return {
                'provider': 'generic_openai', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': 'No model specified for execution.',
            }
            
        prompt_text = '\n'.join(m.get('content', '') for m in messages)

        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
            
        r = self._http_post(
            f'{ep}/chat/completions',
            provider_input, json=payload, timeout=timeout
        )
        r.raise_for_status()
        
        data = r.json()
        choice = data.get('choices', [{}])[0]
        usage = data.get('usage', {})
        
        return {
            'provider': 'generic_openai',
            'model': model,
            'prompt': prompt_text,
            'response': choice.get('message', {}).get('content', ''),
            'token_usage': usage.get('total_tokens', 0),
            'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0),
            'error': None,
        }
