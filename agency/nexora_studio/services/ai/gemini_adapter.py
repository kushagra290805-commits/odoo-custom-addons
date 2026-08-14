# -*- coding: utf-8 -*-
"""
Google Gemini Adapter.
"""
from odoo import models
import requests
import logging

_logger = logging.getLogger(__name__)


class GeminiAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.gemini'
    _inherit = 'nexora.ai_adapter_base'
    _description = 'Google Gemini AI Provider Adapter'

    def get_provider_name(self):
        return 'gemini'

    def get_display_name(self):
        return 'Google Gemini'

    def get_provider_metadata(self):
        return {
            'name': 'Google Gemini',
            'key': 'gemini',
            'required_config': ['api_key', 'base_url', 'timeout'],
            'default_base_url': 'https://generativelanguage.googleapis.com/v1beta',
            'supports_catalog_sync': False,
        }

    def run_diagnostics(self, provider_input):
        import time
        import requests
        start = time.time()
        # Ping the models endpoint without a key to check reachability
        ep = provider_input.base_url.rstrip('/')
        try:
            r = requests.get(f'{ep}/models', timeout=5)
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
            r = requests.get(f'{endpoint}/models?key={key}', timeout=10)
            if r.status_code == 200:
                return {'authentication_state': 'authenticated'}
            else:
                return {'authentication_state': 'failed', 'error': f'HTTP {r.status_code}: {r.text}'}
        except Exception as e:
            return {'authentication_state': 'failed', 'error': str(e)}

    def fetch_catalog(self, provider_input):
        # We fetch the models, though usually Gemini models are hardcoded. We can just return empty or parse the /models endpoint
        import requests
        key = provider_input.api_key
        endpoint = provider_input.base_url.rstrip('/')
        if not key:
            return []
        try:
            r = requests.get(f'{endpoint}/models?key={key}', timeout=10)
            r.raise_for_status()
            models_data = []
            for m in r.json().get('models', []):
                # Google prefixes models with 'models/' in the ID
                name = m.get('name', '').replace('models/', '')
                models_data.append({
                    'id': name,
                    'name': m.get('displayName', name),
                    'context_length': m.get('inputTokenLimit', 32768),
                    'max_output_tokens': m.get('outputTokenLimit', 8192),
                    'supports_streaming': True,
                    'supports_tool_calling': True,
                    'supports_vision': 'vision' in name.lower(),
                    'supports_json': True,
                    'supports_reasoning': False,
                    'supports_embeddings': False,
                    'price_prompt': 0.0,
                    'price_completion': 0.0,
                })
            return models_data
        except Exception as e:
            from odoo.exceptions import UserError
            raise UserError(f'Gemini Catalog Sync Failed: {e}')

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        if not credentials:
            credentials = {}
        key = credentials.get('api_key')
        endpoint = credentials.get('base_url', 'https://generativelanguage.googleapis.com/v1beta')
        if not key:
            return {
                'provider': 'gemini', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'execution_time': 0,
                'error': 'Gemini API key not configured',
            }
        
        if not model:
            return {
                'provider': 'gemini', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'execution_time': 0,
                'error': 'No model specified for execution.',
            }
            
        prompt_text = '\n'.join(m.get('content', '') for m in messages)

        system_text = '\n'.join(
            m['content'] for m in messages if m['role'] == 'system'
        )
        parts = [{'text': m['content']} for m in messages if m['role'] != 'system']

        def _call(t):
            url = f'{endpoint}/models/{model}:generateContent?key={key}'
            payload = {
                'contents': [{'parts': parts}],
                'generationConfig': {
                    'temperature': temperature,
                    'maxOutputTokens': max_tokens,
                },
            }
            if system_text:
                payload['systemInstruction'] = {'parts': [{'text': system_text}]}
            if json_mode:
                payload['generationConfig']['responseMimeType'] = 'application/json'
            r = requests.post(url, json=payload, timeout=t)
            r.raise_for_status()
            data = r.json()
            candidates = data.get('candidates', [{}])
            text = ''
            if candidates:
                content = candidates[0].get('content', {})
                text = '\n'.join(
                    p.get('text', '') for p in content.get('parts', [])
                )
            usage = data.get('usageMetadata', {})
            total = usage.get('totalTokenCount', 0)
            return {
                'provider': 'gemini',
                'model': model,
                'prompt': prompt_text,
                'response': text,
                'token_usage': total,
                'error': None,
            }

        return _call(timeout)
