# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate_default_models(env):
    """
    Phase 18.2 One-time migration:
    Moves legacy `ir.config_parameter` string values for default models
    to the new `nexora.provider.registry` Many2one relationships.
    """
    _logger.info("Starting Phase 18.2 Default Model Migration...")
    ICPSudo = env['ir.config_parameter'].sudo()
    Registry = env['nexora.provider.registry'].sudo()
    Catalog = env['nexora.ai_model_catalog'].sudo()
    
    # 1. Fetch all providers in the registry
    registries = Registry.search([('category', '=', 'ai')])
    for reg in registries:
        provider_id = reg.provider_id
        config_key = f'nexora.{provider_id}.default_model'
        legacy_model_str = ICPSudo.get_param(config_key)
        
        if legacy_model_str:
            _logger.info(f"Found legacy default model '{legacy_model_str}' for provider '{provider_id}'")
            # Try to resolve it in the catalog
            model_rec = Catalog.search([('provider', '=', provider_id), ('model_id', '=', legacy_model_str)], limit=1)
            
            if model_rec:
                _logger.info(f"Resolved to Catalog ID {model_rec.id}. Assigning to Provider Registry.")
                # Assign to all workload default fields initially (as per plan)
                reg.write({
                    'default_model_id': model_rec.id,
                    'default_chat_model_id': model_rec.id,
                    'default_code_model_id': model_rec.id,
                    'default_reasoning_model_id': model_rec.id,
                    'default_vision_model_id': model_rec.id,
                    'default_embedding_model_id': model_rec.id,
                })
            else:
                _logger.warning(f"Legacy model '{legacy_model_str}' not found in catalog. Skipping assignment.")
        
        # Once processed, we remove the legacy key to prevent duplicates
        legacy_param = ICPSudo.search([('key', '=', config_key)])
        if legacy_param:
            legacy_param.unlink()
    
    _logger.info("Phase 18.2 Default Model Migration completed successfully.")
