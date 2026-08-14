# -*- coding: utf-8 -*-
"""
NVIDIA Build AI Provider Adapter
"""
from odoo import models
import logging

_logger = logging.getLogger(__name__)

class NvidiaAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.nvidia'
    _inherit = 'nexora.ai_adapter.generic_openai'
    _description = 'NVIDIA Build AI Provider Adapter'

    def get_provider_name(self):
        return 'nvidia'

    def get_display_name(self):
        return 'NVIDIA Build'

    def get_provider_metadata(self):
        return {
            'name': 'NVIDIA Build',
            'key': 'nvidia',
            'required_config': ['api_key', 'base_url', 'default_model'],
            'default_base_url': 'https://integrate.api.nvidia.com/v1',
            'supports_catalog_sync': True,
        }

    def fetch_catalog(self, provider_input):
        ep = provider_input.base_url
        if ep:
            ep = ep.rstrip('/')
        if not ep:
            return []
        try:
            r = self._http_get(f'{ep}/models', provider_input, timeout=10)
            r.raise_for_status()
            models_data = []
            for m in r.json().get('data', []):
                models_data.append({
                    'id': m['id'],
                    'name': m.get('name', m['id']),
                    'context_length': 8192,
                    'price_prompt': 0.0,
                    'price_completion': 0.0,
                    'supports_streaming': True,
                    'supports_tool_calling': False,
                    'supports_vision': False,
                    'supports_reasoning': False,
                    'supports_json': True,
                    'supports_embeddings': False,
                })
            return models_data
        except Exception as e:
            from odoo.exceptions import UserError
            raise UserError(f"Error fetching NVIDIA catalog: {e}")
