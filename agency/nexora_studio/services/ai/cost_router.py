# -*- coding: utf-8 -*-
"""
Cost Router - intelligent routing based on task complexity.

# Development Configuration (Phase 9B):
#     All tiers default to openrouter -> ollama fallback.
#     This is fully configurable via ir.config_parameter:
#         nexora.cost_router_tier_simple   = openrouter,ollama
#         nexora.cost_router_tier_medium   = openrouter,ollama
#         nexora.cost_router_tier_complex  = openrouter,ollama
#
# Production override example:
#     nexora.cost_router_tier_complex = claude,openai,gemini,openrouter,ollama
"""
from odoo import models, api
from odoo.exceptions import UserError
import logging
from .ai_execution_context import ProviderResolution, AIExecutionContext

_logger = logging.getLogger(__name__)

# Default tier -> adapter mapping (DEVELOPMENT configuration)
# OpenRouter is first in every tier, Ollama is the universal fallback.
_DEFAULT_TIERS = {
    'simple':  ['openrouter', 'ollama'],
    'medium':  ['openrouter', 'ollama'],
    'complex': ['openrouter', 'ollama'],
}

# Task type -> tier mapping
_TASK_TIER = {
    'simple_task':     'simple',
    'documentation':   'simple',
    'review_task':     'medium',
    'code_generation': 'complex',
    'bug_fixing':      'medium',
    'security_review': 'complex',
    'quality_pass':    'medium',
}


class CostRouter(models.AbstractModel):
    _name = 'nexora.ai_cost_router'
    _description = 'AI Cost Router - intelligent provider selection'

    @api.model
    def classify_task(self, task_type):
        """Map a task_type string to a cost tier."""
        return _TASK_TIER.get(task_type, 'medium')

    @api.model
    def get_fallback_chain(self, tier):
        """
        Return the ordered list of provider keys to try for the given tier.
        Reads overrides from AIConfigurationService.
        """
        param_key = f'cost_router_tier_{tier}'
        override = self.env['nexora.ai_configuration_service'].get_config('core', param_key, '')
        if override:
            return [p.strip() for p in override.split(',') if p.strip()]
        return list(_DEFAULT_TIERS.get(tier, _DEFAULT_TIERS['medium']))

    @api.model
    def resolve_provider(self, ctx: AIExecutionContext, adapters_by_key, required_capabilities=None) -> ProviderResolution:
        """
        Given the context and requirements, resolve a provider and return a ProviderResolution trace.
        """
        tier = self.classify_task(ctx.capability or 'medium')
        chain = self.get_fallback_chain(tier)
        pm = self.env['nexora.ai_provider_manager']
        
        available_providers = {
            p['key']: p['available'] for p in pm.get_available_providers()
        }
        
        def _provider_has_capabilities(provider_key):
            if not required_capabilities:
                return True
            # Get the default model for this provider to check its capabilities
            active_model_id = self.env['nexora.ai_configuration_service'].get_active_model(provider_key)
            if not active_model_id:
                return False
            
            model = self.env['nexora.ai_model_catalog'].search([('provider', '=', provider_key), ('model_id', '=', active_model_id)], limit=1)
            if not model:
                return False
                
            model_caps = [c.code for c in model.capability_ids]
            # Verify all required capabilities exist in the model's capabilities
            return all(rc in model_caps for rc in required_capabilities)

        skipped = []
        fallback_depth = 0
        
        for key in chain:
            if key in available_providers and available_providers[key]:
                if _provider_has_capabilities(key):
                    adapter = adapters_by_key.get(key)
                    if adapter is not None:
                        _logger.info(
                            'CostRouter: tier=%s task=%s -> selected %s',
                            tier, ctx.capability, key
                        )
                        return ProviderResolution(
                            requested_provider=chain[0],
                            requested_capability=ctx.capability,
                            selected_provider=key,
                            selected_model=self.env['nexora.ai_configuration_service'].get_active_model(key),
                            skipped_providers=skipped,
                            fallback_depth=fallback_depth,
                            execution_policy_applied='standard_retry'
                        )
                else:
                    skipped.append(key)
            else:
                skipped.append(key)
                
            fallback_depth += 1

        available_keys = [
            k for k in adapters_by_key.keys()
            if available_providers.get(k) and _provider_has_capabilities(k)
        ]
        
        if available_keys:
            fallback_key = available_keys[0]
            _logger.warning(
                'CostRouter: no preferred provider available for tier=%s. '
                'Falling back to %s', tier, fallback_key
            )
            return ProviderResolution(
                requested_provider=chain[0],
                requested_capability=ctx.capability,
                selected_provider=fallback_key,
                selected_model=self.env['nexora.ai_configuration_service'].get_active_model(fallback_key),
                skipped_providers=skipped,
                fallback_depth=fallback_depth,
                execution_policy_applied='fallback_retry'
            )

        raise UserError(
            f'No AI provider is available that satisfies requirements ({required_capabilities}). '
            'Configure at least one capable provider in Settings > Nexora Studio.'
        )
