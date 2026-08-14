# -*- coding: utf-8 -*-
"""
AIRouter Adapter - Dedicated adapter for AIRouter
Extends Generic OpenAI since AIRouter is largely OpenAI-compatible.
"""
from odoo import models
import logging

_logger = logging.getLogger(__name__)

class AIRouterAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.airouter'
    _inherit = 'nexora.ai_adapter.generic_openai'
    _description = 'AIRouter AI Provider Adapter'

    def get_provider_name(self):
        return 'airouter'

    def get_display_name(self):
        return 'AIRouter'

    def get_provider_metadata(self):
        return {
            'name': 'AIRouter',
            'key': 'airouter',
            'required_config': ['api_key', 'base_url', 'timeout'],
            'default_base_url': 'https://api.airouter.in/v1',
            'supports_catalog_sync': True,
        }
        
    def authenticate(self, provider_input):
        """For AIRouter, we hit /chat/completions with a dummy prompt to prove auth, since /models is public and there's no /auth/key endpoint."""
        ep = provider_input.base_url.rstrip('/')
        key = provider_input.api_key
        if not key:
            return {'authentication_state': 'failed', 'error': 'No API key provided'}
            
        try:
            # Let's do a dummy completion to prove auth
            payload = {
                'model': 'dummy-model-does-not-exist',
                'messages': [{'role': 'user', 'content': 'test'}],
                'max_tokens': 1
            }
            r_chat = self._http_post(f'{ep}/chat/completions', provider_input, json=payload, timeout=5)
            if r_chat.status_code in [401, 403]:
                return {'authentication_state': 'failed', 'error': 'Authentication failed on /chat/completions'}
                
            # If it returns 404 (model not found), that means auth passed!
            return {'authentication_state': 'authenticated'}
        except Exception as e:
            return {'authentication_state': 'failed', 'error': str(e)}
