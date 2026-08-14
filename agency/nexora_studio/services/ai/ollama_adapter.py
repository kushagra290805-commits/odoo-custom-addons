# -*- coding: utf-8 -*-
"""
Ollama Adapter — local LLM provider via HTTP API.
"""
from odoo import models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class OllamaAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.ollama'
    _inherit = 'nexora.ai_adapter_base'
    _description = 'Ollama AI Provider Adapter'

    def get_provider_name(self):
        return 'ollama'

    def get_display_name(self):
        return 'Ollama (Local)'

    def get_provider_metadata(self):
        return {
            'name': 'Ollama (Local)',
            'key': 'ollama',
            'required_config': ['base_url', 'timeout'],
            'default_base_url': 'http://localhost:11434',
            'supports_catalog_sync': True,
        }

    def _get_active_endpoint(self, provider_input):
        from urllib.parse import urlparse
        endpoint = provider_input.base_url.rstrip('/')
        try:
            r = self._http_get(f'{endpoint}/api/version', provider_input, timeout=2)
            r.raise_for_status()
            return endpoint
        except Exception as e:
            parsed = urlparse(endpoint)
            if parsed.hostname == 'localhost':
                fallback_ep = endpoint.replace('localhost', '127.0.0.1', 1)
                try:
                    _logger.debug(f"Ollama fallback testing {fallback_ep}")
                    r2 = self._http_get(f'{fallback_ep}/api/version', provider_input, timeout=2)
                    r2.raise_for_status()
                    return fallback_ep
                except Exception:
                    pass
            raise e

    def run_diagnostics(self, provider_input):
        import time
        start_ts = time.time()
        
        try:
            active_ep = self._get_active_endpoint(provider_input)
            return {
                'connectivity_state': 'reachable',
                'latency_ms': (time.time() - start_ts) * 1000
            }
        except Exception as e:
            if 'Timeout' in str(type(e)) or 'ConnectionError' in str(type(e)):
                return {'connectivity_state': 'unreachable', 'error': 'Local Ollama server is offline (socket connection failed).'}
            return {'connectivity_state': 'unreachable', 'error': str(e)}

    def authenticate(self, provider_input):
        # Ollama has no authentication
        return {'authentication_state': 'authenticated'}

    def fetch_catalog(self, provider_input):
        if not provider_input.base_url:
            provider_input.base_url = 'http://localhost:11434'
        
        try:
            active_ep = self._get_active_endpoint(provider_input)
            r = self._http_get(f'{active_ep}/api/tags', provider_input, timeout=5)
            r.raise_for_status()
            
            models_data = []
            for m in r.json().get('models', []):
                models_data.append({
                    'id': m['name'],
                    'name': m['name'],
                    'context_length': 8192,
                    'max_output_tokens': 4096,
                    'supports_streaming': True,
                    'supports_tool_calling': False,
                    'supports_vision': 'llava' in m['name'].lower() or 'vision' in m['name'].lower(),
                    'supports_json': True,
                    'supports_reasoning': 'reasoning' in m['name'].lower() or 'think' in m['name'].lower(),
                    'supports_embeddings': 'embed' in m['name'].lower(),
                    'price_prompt': 0.0,
                    'price_completion': 0.0,
                })
            return models_data
        except Exception as e:
            from odoo.exceptions import UserError
            raise UserError(f'Ollama Catalog Sync Failed: {e}')

    def list_models(self, credentials=None):
        catalog = self.fetch_catalog(credentials)
        return [m['id'] for m in catalog]

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        provider_input = self.resolve_provider_input(credentials=credentials)
        if not provider_input.base_url:
            provider_input.base_url = 'http://localhost:11434'
        
        try:
            endpoint = self._get_active_endpoint(provider_input)
        except Exception as e:
            return {
                'provider': 'ollama', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': f'Failed to connect to Ollama: {e}',
            }

        if not model:
            return {
                'provider': 'ollama', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': 'No model specified for execution.',
            }
        prompt = '\n'.join(
            f"[{m['role']}]: {m['content']}" for m in messages
        )

        def _call(t):
            payload = {
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': temperature,
                    'num_predict': max_tokens,
                },
            }
            if json_mode:
                payload['format'] = 'json'
            r = self._http_post(
                f'{endpoint}/api/generate',
                provider_input,
                json=payload, timeout=t
            )
            r.raise_for_status()
            data = r.json()
            return {
                'provider': 'ollama',
                'model': model,
                'prompt': prompt,
                'response': data.get('response', ''),
                'token_usage': data.get('eval_count', 0),
                'prompt_tokens': data.get('prompt_eval_count', 0),
                'completion_tokens': data.get('eval_count', 0),
                'total_tokens': data.get('prompt_eval_count', 0) + data.get('eval_count', 0),
                'error': None,
            }

        return _call(timeout)
