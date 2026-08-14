# -*- coding: utf-8 -*-
"""
OpenAI Adapter — GPT-4o, GPT-4o-mini, etc.
"""
from odoo import models
import requests
import logging

_logger = logging.getLogger(__name__)


class OpenAIAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.openai'
    _inherit = 'nexora.ai_adapter_base'
    _description = 'OpenAI AI Provider Adapter'

    def get_provider_name(self):
        return 'openai'

    def get_display_name(self):
        return 'OpenAI'

    def get_provider_metadata(self):
        return {
            'name': 'OpenAI',
            'key': 'openai',
            'required_config': ['api_key', 'base_url', 'timeout'],
            'default_base_url': 'https://api.openai.com/v1',
            'supports_catalog_sync': True,
        }

    def run_diagnostics(self, provider_input):
        import time
        import requests
        start = time.time()
        ep = provider_input.base_url.rstrip('/')
        try:
            r = requests.get(f'{ep}/models', timeout=5, headers=self._headers(provider_input))
            return {
                'connectivity_state': 'reachable',
                'latency_ms': (time.time() - start) * 1000
            }
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return {'connectivity_state': 'unreachable', 'error': 'Endpoint unreachable or timed out'}
        except Exception as e:
            return {'connectivity_state': 'unreachable', 'error': str(e)}

    def authenticate(self, provider_input):
        import requests
        key = provider_input.api_key
        endpoint = provider_input.base_url.rstrip('/')
        if not key:
            return {'authentication_state': 'failed', 'error': 'No API key provided'}
            
        try:
            r = requests.get(f'{endpoint}/models', headers=self._headers(provider_input), timeout=10)
            if r.status_code == 200:
                return {'authentication_state': 'authenticated'}
            else:
                return {'authentication_state': 'failed', 'error': f'HTTP {r.status_code}: {r.text}'}
        except Exception as e:
            return {'authentication_state': 'failed', 'error': str(e)}

    def fetch_catalog(self, provider_input):
        import requests
        key = provider_input.api_key
        endpoint = provider_input.base_url.rstrip('/')
        if not key:
            return []
        try:
            r = requests.get(
                f'{endpoint}/models',
                headers=self._headers(provider_input),
                timeout=10,
            )
            r.raise_for_status()
            models_data = []
            for m in r.json().get('data', []):
                name = m['id']
                models_data.append({
                    'id': name,
                    'name': name,
                    'context_length': 128000 if 'gpt-4o' in name or 'gpt-4-turbo' in name else 8192,
                    'max_output_tokens': 4096,
                    'supports_streaming': True,
                    'supports_tool_calling': True,
                    'supports_vision': 'gpt-4o' in name or 'vision' in name,
                    'supports_json': True,
                    'supports_reasoning': 'o1' in name or 'o3' in name,
                    'supports_embeddings': 'embed' in name,
                    'price_prompt': 0.0,
                    'price_completion': 0.0,
                })
            return models_data
        except Exception as e:
            from odoo.exceptions import UserError
            raise UserError(f'OpenAI Catalog Sync Failed: {e}')

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        if not credentials:
            credentials = {}
        key = credentials.get('api_key')
        endpoint = credentials.get('base_url', 'https://api.openai.com/v1').rstrip('/')
        if not key:
            return {
                'provider': 'openai', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'execution_time': 0,
                'error': 'OpenAI API key not configured',
            }
        if not model:
            return {
                'provider': 'openai', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'execution_time': 0,
                'error': 'No model specified for execution.',
            }
        prompt_text = '\n'.join(m.get('content', '') for m in messages)

        def _call(t):
            headers = {
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
            }
            payload = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
            if json_mode:
                payload['response_format'] = {'type': 'json_object'}
            r = requests.post(
                f'{endpoint}/chat/completions',
                headers=headers, json=payload, timeout=t,
            )
            r.raise_for_status()
            data = r.json()
            choice = data.get('choices', [{}])[0]
            usage = data.get('usage', {})
            return {
                'provider': 'openai',
                'model': model,
                'prompt': prompt_text,
                'response': choice.get('message', {}).get('content', ''),
                'token_usage': usage.get('total_tokens', 0),
                'error': None,
            }

        return _call(timeout)
