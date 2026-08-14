# -*- coding: utf-8 -*-
"""
Anthropic Claude Adapter — Claude 3 / 4 family.
"""
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class ClaudeAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.claude'
    _inherit = 'nexora.ai_adapter_base'
    _description = 'Anthropic Claude AI Provider Adapter'

    def get_provider_name(self):
        return 'claude'

    def get_display_name(self):
        return 'Anthropic Claude'

    def get_provider_metadata(self):
        return {
            'name': 'Anthropic Claude',
            'key': 'claude',
            'required_config': ['api_key', 'base_url', 'timeout'],
            'default_base_url': 'https://api.anthropic.com/v1',
            'supports_catalog_sync': False,
        }

    def _headers(self, provider_input):
        h = super()._headers(provider_input)
        if provider_input.api_key:
            h['x-api-key'] = provider_input.api_key
        h['anthropic-version'] = '2023-06-01'
        return h

    def run_diagnostics(self, provider_input):
        import time
        start = time.time()
        ep = provider_input.base_url.rstrip('/')
        try:
            r = self._http_get(ep, provider_input, timeout=5)
            # Even if it returns 404/401, it is reachable
            return {
                'connectivity_state': 'reachable',
                'latency_ms': (time.time() - start) * 1000
            }
        except Exception as e:
            if 'Timeout' in str(type(e)):
                return {'connectivity_state': 'unreachable', 'error': 'Endpoint unreachable or timed out'}
            return {'connectivity_state': 'unreachable', 'error': str(e)}

    def authenticate(self, provider_input):
        key = provider_input.api_key
        endpoint = provider_input.base_url.rstrip('/')
        if not key:
            return {'authentication_state': 'failed', 'error': 'No API key provided'}
            
        try:
            # Dummy completion to prove auth
            payload = {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 1,
                'messages': [{'role': 'user', 'content': 'test'}]
            }
            r = self._http_post(f'{endpoint}/messages', provider_input, json=payload, timeout=5)
            if r.status_code in [401, 403]:
                return {'authentication_state': 'failed', 'error': f'HTTP {r.status_code}: Unauthorized'}
                
            return {'authentication_state': 'authenticated'}
        except Exception as e:
            return {'authentication_state': 'failed', 'error': str(e)}

    def fetch_catalog(self, provider_input):
        # Anthropic does not expose a public model list endpoint
        return []

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        provider_input = self.resolve_provider_input(credentials=credentials)
        key = provider_input.api_key
        endpoint = provider_input.base_url.rstrip('/') if provider_input.base_url else 'https://api.anthropic.com/v1'
        if not key:
            return {
                'provider': 'claude', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': 'Claude API key not configured',
            }
            
        if not model:
            return {
                'provider': 'claude', 'model': '', 'prompt': '',
                'response': '', 'token_usage': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'execution_time': 0, 'error': 'No model specified for execution.',
            }
            
        prompt_text = '\n'.join(m.get('content', '') for m in messages)

        # Separate system from user messages for the Anthropic API
        system_text = '\n'.join(
            m['content'] for m in messages if m['role'] == 'system'
        )
        api_messages = [
            {'role': m['role'], 'content': m['content']}
            for m in messages if m['role'] != 'system'
        ]

        def _call(t):
            payload = {
                'model': model,
                'max_tokens': max_tokens,
                'messages': api_messages,
            }
            if system_text:
                payload['system'] = system_text
            if temperature is not None:
                payload['temperature'] = temperature
            r = self._http_post(
                f'{endpoint}/messages',
                provider_input, json=payload, timeout=t,
            )
            r.raise_for_status()
            data = r.json()
            content_blocks = data.get('content', [])
            response_text = '\n'.join(
                b.get('text', '') for b in content_blocks if b.get('type') == 'text'
            )
            usage = data.get('usage', {})
            total_tokens = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            return {
                'provider': 'claude',
                'model': model,
                'prompt': prompt_text,
                'response': response_text,
                'token_usage': total_tokens,
                'prompt_tokens': usage.get('input_tokens', 0),
                'completion_tokens': usage.get('output_tokens', 0),
                'total_tokens': total_tokens,
                'error': None,
            }

        return _call(timeout)
