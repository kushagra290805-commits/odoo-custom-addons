# -*- coding: utf-8 -*-
"""
Provider Health Service

Dedicated service to monitor structural provider availability (e.g. general provider outages
or API key misconfigurations). Ensures that structural health does not overwrite Circuit Breaker state.
"""
from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class ProviderHealthService(models.AbstractModel):
    _name = 'nexora.provider_health_service'
    _description = 'AI Provider Health Monitoring Service'

    @api.model
    def is_provider_healthy(self, provider_key: str) -> bool:
        """
        Check if the provider is structurally healthy.
        This checks if the provider is enabled and configured, and potentially 
        makes a lightweight ping to the provider's /models endpoint.
        """
        pm = self.env['nexora.ai_provider_manager']
        provider_data = next((p for p in pm.get_available_providers() if p['key'] == provider_key), None)
        if not provider_data:
            return False
            
        return provider_data.get('available', False)

    @api.model
    def validate_provider_health(self, provider_key: str):
        """
        Raise an exception if the provider is unhealthy.
        """
        if not self.is_provider_healthy(provider_key):
            raise ValueError(f"Provider {provider_key} is currently unhealthy or unconfigured.")

