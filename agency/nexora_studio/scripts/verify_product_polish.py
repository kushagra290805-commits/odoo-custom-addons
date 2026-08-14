import logging
import sys
import os

# Add Odoo community path to sys.path
sys.path.append(r'D:\ODOO\community\odoo')

import odoo
from odoo import tools
from odoo.exceptions import UserError

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("Product-Polish-Verification")

def run_verification():
    _logger.info("Starting Product Polish Verification...")
    odoo.tools.config.parse_config(['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])
    
    from odoo.modules.registry import Registry
    registry = Registry('nexora_studio')
    
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        
        # 1. Config Change Detection
        _logger.info("=== 1. Test Config Change Detection ===")
        groq_provider = env['nexora.provider.registry'].search([('provider_id', '=', 'groq')], limit=1)
        if not groq_provider:
            _logger.error("Groq provider not found.")
            return

        # Prepare state
        groq_provider.write({
            'lifecycle_state': 'HEALTHY',
            'catalog_sync_status': 'success',
            'health_status': 'HEALTHY',
            'api_key': 'test_key'
        })
        
        # Trigger change
        groq_provider.write({'base_url': 'https://api.groq.com/openai/v2'})
        
        assert groq_provider.catalog_sync_status == 'stale', "Catalog not marked stale!"
        assert groq_provider.lifecycle_state == 'CONFIGURED', f"Lifecycle not CONFIGURED, got {groq_provider.lifecycle_state}"
        # health_status is no longer overridden on config change, only by orchestrator
        _logger.info("Config Change Detection PASSED")

        # 2. Missing API Key Validation
        _logger.info("=== 2. Missing API Key Validation ===")
        groq_provider.write({'api_key': False})
        assert groq_provider.lifecycle_state == 'UNCONFIGURED', "Lifecycle not downgraded to UNCONFIGURED!"
        
        env['nexora.ai_provider_manager'].test_connection(groq_provider.provider_id)
        assert groq_provider.health_status == 'Missing API Key', "Health not Missing API Key"
        assert groq_provider.lifecycle_state == 'UNCONFIGURED', "Lifecycle not UNCONFIGURED"
        _logger.info("Missing API Key Validation PASSED")

        # Restore API Key
        groq_provider.write({'api_key': os.environ.get('GROQ_API_KEY', 'gsk_test')})

        # 3. Model Summary
        _logger.info("=== 3. Model Summary UI Data ===")
        models = env['nexora.ai_model_catalog'].search([('provider', '=', 'groq')], limit=1)
        if models:
            groq_provider.write({'default_model_id': models[0].id})
            assert groq_provider.summary_model_name == models[0].name, "Summary name mismatch"
            assert groq_provider.summary_model_provider == 'groq', "Summary provider mismatch"
            _logger.info("Model Summary Data PASSED")

        _logger.info("=== 4. Ollama Diagnostics Verification ===")
        ollama = env['nexora.provider.registry'].search([('provider_id', '=', 'ollama')], limit=1)
        if ollama:
            try:
                env['nexora.ai_provider_manager'].test_connection(ollama.provider_id)
                _logger.info(f"Ollama Health: {ollama.health_status}")
            except Exception as e:
                _logger.info(f"Ollama test failed gracefully: {e}")
        
        # Rollback so we don't dirty DB with tests
        cr.rollback()
        _logger.info("All Product Polish Verifications PASSED (rolled back).")

if __name__ == '__main__':
    run_verification()
