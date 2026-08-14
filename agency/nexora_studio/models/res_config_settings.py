import logging
_logger = logging.getLogger(__name__)
# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Default workspace root used when no setting has been configured.
_DEFAULT_WORKSPACE_ROOT = r'D:\NexoraStudio\workspaces'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # -- Workspace -----------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        _logger.warning("===== DUMPING VALS_LIST IN CREATE =====")
        _logger.warning(vals_list)
        return super().create(vals_list)

    nexora_workspace_root = fields.Char(
        string='Workspace Root Directory',
        config_parameter='nexora.workspace_root',
        default=_DEFAULT_WORKSPACE_ROOT,
        help=(
            'The local filesystem directory where all Builder Session workspaces will be created. '
            f'Defaults to: {_DEFAULT_WORKSPACE_ROOT}. '
            'The directory is created automatically if it does not exist.'
        )
    )

    # -- Routing Configuration -----------------------------------------------

    nexora_cost_router_tier_simple = fields.Char(
        string='Simple Task Fallback Chain',
        help='Comma-separated list of providers (e.g. openrouter,ollama) for simple tasks.',
        default='openrouter,ollama',
    )
    
    nexora_cost_router_tier_medium = fields.Char(
        string='Medium Task Fallback Chain',
        help='Comma-separated list of providers for medium tasks.',
        default='openrouter,ollama',
    )
    
    nexora_cost_router_tier_complex = fields.Char(
        string='Complex Task Fallback Chain',
        help='Comma-separated list of providers for complex tasks.',
        default='openrouter,ollama',
    )

    def set_values(self):
        super().set_values()
        ai_service = self.env['nexora.ai_configuration_service']
        
        # Save routing config
        ai_service.set_config('core', 'cost_router_tier_simple', self.nexora_cost_router_tier_simple or 'openrouter,ollama')
        ai_service.set_config('core', 'cost_router_tier_medium', self.nexora_cost_router_tier_medium or 'openrouter,ollama')
        ai_service.set_config('core', 'cost_router_tier_complex', self.nexora_cost_router_tier_complex or 'openrouter,ollama')

    @api.model
    def get_values(self):
        res = super().get_values()
        ai_service = self.env['nexora.ai_configuration_service']
        
        # Load routing config
        res.update({
            'nexora_cost_router_tier_simple': ai_service.get_config('core', 'cost_router_tier_simple', 'openrouter,ollama'),
            'nexora_cost_router_tier_medium': ai_service.get_config('core', 'cost_router_tier_medium', 'openrouter,ollama'),
            'nexora_cost_router_tier_complex': ai_service.get_config('core', 'cost_router_tier_complex', 'openrouter,ollama'),
        })
                    
        return res
