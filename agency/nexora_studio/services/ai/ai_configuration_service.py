# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, exceptions
import logging

_logger = logging.getLogger(__name__)

class AIConfigVersion(models.Model):
    _name = 'nexora.ai_config_version'
    _description = 'AI Configuration Version History'
    _order = 'create_date desc'
    
    provider = fields.Char(string='Provider', index=True)
    key = fields.Char(string='Configuration Key', index=True)
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')
    user_id = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user)

class AIConfigurationService(models.AbstractModel):
    _name = 'nexora.ai_configuration_service'
    _description = 'AI Configuration Governance Service'

    # =====================================================================================
    # 1. Configuration Repository (Cached)
    # =====================================================================================
    @tools.ormcache('provider', 'key')
    def get_config(self, provider, key, default=False):
        """
        Thread-safe, process-safe read-through cache for AI configuration.
        """
        full_key = f'nexora.{provider}.{key}'
        val = self.env['ir.config_parameter'].sudo().get_param(full_key, default)
        return val

    def set_config(self, provider, key, value):
        """
        Write configuration and invalidate the specific ORM cache globally.
        """
        full_key = f'nexora.{provider}.{key}'
        old_value = self.get_config(provider, key, default=False)
        
        # Don't log or write if it's the exact same value
        if str(old_value) == str(value):
            return
            
        if value is False or value is None:
            self.env['ir.config_parameter'].sudo().set_param(full_key, False)
        else:
            self.env['ir.config_parameter'].sudo().set_param(full_key, value)
            
        # Log to version history
        # Avoid logging API keys in plaintext
        log_old = '********' if 'key' in key.lower() else str(old_value)
        log_new = '********' if 'key' in key.lower() else str(value)
        self.env['nexora.ai_config_version'].sudo().create({
            'provider': provider,
            'key': key,
            'old_value': log_old,
            'new_value': log_new,
        })
        
        self.env.registry.clear_cache()
        _logger.info(f"AIConfigurationService: Updated config {full_key}")

    def get_provider_credentials(self, provider):
        """
        Fetch all necessary credentials for a provider exclusively from the Registry.
        """
        reg = self.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider)], limit=1)
        if reg:
            return {
                'api_key': reg.api_key or '',
                'base_url': reg.base_url or ''
            }
        return {
            'api_key': '',
            'base_url': ''
        }

    # =====================================================================================
    # 2. Model Resolver
    # =====================================================================================
    def get_active_model(self, provider, workload='default'):
        """
        Resolves the configured default model for a provider using the Registry.
        """
        reg = self.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider)], limit=1)
        if reg:
            if workload == 'chat' and reg.default_chat_model_id:
                return reg.default_chat_model_id.model_id
            if workload == 'code' and reg.default_code_model_id:
                return reg.default_code_model_id.model_id
            if workload == 'reasoning' and reg.default_reasoning_model_id:
                return reg.default_reasoning_model_id.model_id
            if workload == 'vision' and reg.default_vision_model_id:
                return reg.default_vision_model_id.model_id
            if workload == 'embedding' and reg.default_embedding_model_id:
                return reg.default_embedding_model_id.model_id
            if reg.default_model_id:
                return reg.default_model_id.model_id
        return False

    def set_active_model(self, provider, model_id):
        """
        Sets the default model for a provider on the Registry.
        """
        Catalog = self.env['nexora.ai_model_catalog'].sudo()
        model_rec = Catalog.search([('provider', '=', provider), ('model_id', '=', model_id)], limit=1)
        if model_rec:
            reg = self.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider)], limit=1)
            if reg:
                reg.default_model_id = model_rec.id

    def list_available_models(self, provider):
        """
        Returns a list of active models for the given provider from the catalog.
        """
        Catalog = self.env['nexora.ai_model_catalog'].sudo()
        domain = [('provider', '=', provider), ('status', '=', 'active')]
        return Catalog.search_read(domain, ['model_id', 'name', 'context_length'])

    def resolve_model_record(self, provider, model_id=None, workload='default'):
        """
        Resolves the model ID to an actual nexora.ai_model_catalog record.
        Uses the configured active model if model_id is not explicitly provided.
        """
        Catalog = self.env['nexora.ai_model_catalog'].sudo()
        if model_id:
            return Catalog.search([('provider', '=', provider), ('model_id', '=', model_id)], limit=1)
        
        reg = self.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider)], limit=1)
        if reg:
            if workload == 'chat' and reg.default_chat_model_id:
                return reg.default_chat_model_id
            if workload == 'code' and reg.default_code_model_id:
                return reg.default_code_model_id
            if workload == 'reasoning' and reg.default_reasoning_model_id:
                return reg.default_reasoning_model_id
            if workload == 'vision' and reg.default_vision_model_id:
                return reg.default_vision_model_id
            if workload == 'embedding' and reg.default_embedding_model_id:
                return reg.default_embedding_model_id
            if reg.default_model_id:
                return reg.default_model_id
        return None

    # =====================================================================================
    # 3. Provider Health & Central Validation
    # =====================================================================================
    def validate_configuration(self, provider, model_id=None):
        """
        Centralized validation returning structured validation results.
        """
        errors = []
        
        # 1. API Key check
        api_key = self.get_config(provider, 'api_key')
        if not api_key:
            errors.append({'type': 'missing_api_key', 'message': f'API key is missing for provider {provider}'})
            
        # 2. Model check
        target_model = model_id or self.get_active_model(provider)
        if not target_model:
            errors.append({'type': 'missing_model', 'message': f'No active model configured for provider {provider}'})
        else:
            # 3. Catalog existence & status check
            record = self.resolve_model_record(provider, target_model)
            if not record:
                errors.append({'type': 'invalid_catalog', 'message': f'Model {target_model} not found in the local catalog for provider {provider}'})
            elif record.status != 'active':
                errors.append({'type': 'inactive_model', 'message': f'Model {target_model} is marked as {record.status} in the catalog'})

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def get_provider_health(self, provider):
        """
        Returns a health status for a provider (e.g., for a dashboard).
        Statuses: MISSING_CONFIG, VALIDATING, SYNCING, SYNC_FAILED, AUTH_FAILED, CATALOG_OUTDATED, HEALTHY
        """
        enabled = self.get_config(provider, 'enabled', 'True')
        if str(enabled).lower() not in ('true', '1', 'yes'):
            return {'provider': provider, 'status': 'disabled', 'issues': []}

        validation = self.validate_configuration(provider)
        errors = validation['errors']
        
        if any(e['type'] == 'missing_api_key' for e in errors):
            return {'provider': provider, 'status': 'missing_config', 'issues': errors}

        # Check latest sync log instead of doing synchronous network requests
        latest_log = self.env['nexora.ai_catalog_sync_log'].search(
            [('provider', '=', provider)], 
            order='sync_date desc, id desc', 
            limit=1
        )
        
        if latest_log:
            if latest_log.status == 'error':
                err_msg = latest_log.error_message or ''
                if 'Validation failed' in err_msg or 'unreachable' in err_msg:
                    return {'provider': provider, 'status': 'auth_failed', 'issues': [{'type': 'auth_failed', 'message': err_msg}]}
                else:
                    return {'provider': provider, 'status': 'sync_failed', 'issues': [{'type': 'sync_failed', 'message': err_msg}]}
                    
        # If we reach here, either there is no sync log, or the last sync was successful.
        if any(e['type'] in ('missing_model', 'invalid_catalog') for e in errors):
            return {'provider': provider, 'status': 'catalog_outdated', 'issues': errors}

        if any(e['type'] == 'inactive_model' for e in errors):
            return {'provider': provider, 'status': 'unavailable', 'issues': errors}

        return {
            'provider': provider,
            'status': 'healthy',
            'issues': errors
        }
