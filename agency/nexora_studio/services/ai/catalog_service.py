# -*- coding: utf-8 -*-
"""
Catalog Service — dedicated service for catalog synchronization and capability discovery.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import time
import traceback
import json

_logger = logging.getLogger(__name__)

class AICatalogService(models.AbstractModel):
    _name = 'nexora.ai_catalog_service'
    _description = 'AI Catalog Service'

    @api.model
    def sync_catalog(self, provider_key=None):
        """
        Syncs model catalogs from provider APIs, updates ai_model_catalog,
        and caches capabilities on the provider registry.
        """
        provider_manager = self.env['nexora.ai_provider_manager']
        providers = [provider_key] if provider_key else provider_manager._get_adapters().keys()
        
        for p in providers:
            reg = self.env['nexora.provider.registry'].search([('provider_id', '=', p)], limit=1)
            if not reg:
                continue
                
            reg.sudo().write({'catalog_sync_status': 'syncing'})
            _logger.debug(f"Catalog Service syncing provider: {p}")
            
            adapter = provider_manager.get_adapter(p)
            
            start_date = fields.Datetime.now()
            start_ts = time.time()
            
            try:
                provider_input = adapter.resolve_provider_input(reg=reg)
                live_models = adapter.fetch_catalog(provider_input)
                if not live_models:
                    has_active = self.env['nexora.ai_model_catalog'].search_count([('provider', '=', p), ('status', '=', 'active')]) > 0
                    reg.sudo().write({
                        'catalog_sync_status': 'stale' if has_active else 'failed',
                        'last_failed_sync': fields.Datetime.now(),
                        'sync_retry_count': reg.sync_retry_count + 1,
                        'catalog_sync_error': 'No models returned from provider API'
                    })
                    continue
                    
                live_ids = {m['id']: m for m in live_models}
                
                Catalog = self.env['nexora.ai_model_catalog']
                existing_recs = Catalog.search([('provider', '=', p)])
                existing_map = {r.model_id: r for r in existing_recs}
                
                added = []
                removed = []
                changed = []
                
                Capability = self.env['nexora.ai_capability']
                all_caps = Capability.search([])
                cap_map = {c.code: c.id for c in all_caps}
                
                def _get_cap_ids(m_data):
                    ids = []
                    if m_data.get('supports_chat') and 'chat' in cap_map:
                        ids.append(cap_map['chat'])
                    if m_data.get('supports_vision') and 'vision' in cap_map:
                        ids.append(cap_map['vision'])
                    if m_data.get('supports_reasoning') and 'reasoning' in cap_map:
                        ids.append(cap_map['reasoning'])
                    return [(6, 0, ids)]
                
                # Update/Create
                for m_id, m_data in live_ids.items():
                    vals = {
                        'name': m_data.get('name') or m_id,
                        'context_length': m_data.get('context_length') or 0,
                        'max_output_tokens': m_data.get('max_output_tokens') or 0,
                        'price_prompt': m_data.get('price_prompt', 0.0),
                        'price_completion': m_data.get('price_completion', 0.0),
                        'capability_ids': _get_cap_ids(m_data),
                        'capabilities_json': str({
                            k: v for k, v in m_data.items() if k.startswith('supports_')
                        }),
                        'supports_vision': m_data.get('supports_vision', False),
                        'supports_tool_calling': m_data.get('supports_tool_calling', False),
                        'supports_reasoning': m_data.get('supports_reasoning', False),
                        'supports_image_generation': m_data.get('supports_image_generation', False),
                        'supports_embeddings': m_data.get('supports_embeddings', False),
                        'supports_streaming': m_data.get('supports_streaming', False),
                        'supports_json': m_data.get('supports_json', False),
                        'status': 'active',
                        'deprecated_flag': False,
                        'last_synced_at': fields.Datetime.now(),
                        'last_seen_at': fields.Datetime.now()
                    }
                    
                    if m_id not in existing_map:
                        vals['provider'] = p
                        vals['model_id'] = m_id
                        Catalog.create(vals)
                        added.append(m_id)
                    else:
                        rec = existing_map[m_id]
                        # simplified diffing
                        is_changed = (
                            rec.price_prompt != vals['price_prompt'] or 
                            rec.price_completion != vals['price_completion'] or 
                            rec.status != 'active' or
                            rec.deprecated_flag
                        )
                        if is_changed:
                            changed.append(m_id)
                        rec.write(vals)
                        
                # Deprecate missing
                for m_id, rec in existing_map.items():
                    if m_id not in live_ids and rec.status != 'unavailable':
                        rec.sudo().write({
                            'status': 'unavailable',
                            'deprecated_flag': True,
                            'last_synced_at': fields.Datetime.now()
                        })
                        removed.append(m_id)
                        
                # Update registry status & capabilities
                # Calculate provider-level capabilities (aggregate of its models)
                all_active = Catalog.search([('provider', '=', p), ('status', '=', 'active')])
                
                reg.sudo().write({
                    'catalog_sync_status': 'success',
                    'catalog_last_sync': fields.Datetime.now(),
                    'last_successful_sync': fields.Datetime.now(),
                    'sync_retry_count': 0,
                    'catalog_sync_error': False,
                    # capability cache
                    'cap_streaming': any(m.supports_streaming for m in all_active),
                    'cap_tool_calling': any(m.supports_tool_calling for m in all_active),
                    'cap_json_mode': any(m.supports_json for m in all_active),
                    'cap_vision': any(m.supports_vision for m in all_active),
                    'cap_reasoning': any(m.supports_reasoning for m in all_active),
                    'cap_embeddings': any(m.supports_embeddings for m in all_active),
                    'cap_function_calling': any(m.supports_tool_calling for m in all_active),
                    'cap_context_window': max([m.context_length for m in all_active]) if all_active else 0,
                    'cap_max_output_tokens': max([m.max_output_tokens for m in all_active]) if all_active else 0,
                })
                
                # Log Sync Event
                end_date = fields.Datetime.now()
                duration = time.time() - start_ts
                
                prev_log = self.env['nexora.ai_catalog_sync_log'].search([('provider', '=', p)], order='catalog_revision desc', limit=1)
                rev = (prev_log.catalog_revision + 1) if prev_log else 1
                
                summary = {
                    'added': added,
                    'removed': removed,
                    'changed': changed,
                    'total_active': len(live_models)
                }
                
                self.env['nexora.ai_catalog_sync_log'].create({
                    'provider': p,
                    'catalog_revision': rev,
                    'status': 'success',
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_seconds': duration,
                    'models_fetched': len(live_models),
                    'models_added': len(added),
                    'models_updated': len(changed),
                    'models_deprecated': len(removed),
                    'models_removed': 0, # Models are never removed
                    'summary_json': str(summary)
                })
                
                _logger.info(f"Catalog sync success for {p} in {duration:.2f}s. Added: {len(added)}, Removed: {len(removed)}, Changed: {len(changed)}")
                
            except Exception as e:
                end_date = fields.Datetime.now()
                duration = time.time() - start_ts
                err_msg = traceback.format_exc()
                _logger.error(f"Catalog sync failed for provider {p}: {e}\\n{err_msg}")
                
                has_active = self.env['nexora.ai_model_catalog'].search_count([('provider', '=', p), ('status', '=', 'active')]) > 0
                reg.sudo().write({
                    'catalog_sync_status': 'stale' if has_active else 'failed',
                    'catalog_last_sync': fields.Datetime.now(),
                    'last_failed_sync': fields.Datetime.now(),
                    'sync_retry_count': reg.sync_retry_count + 1,
                    'catalog_sync_error': str(e)
                })
                
                self.env['nexora.ai_catalog_sync_log'].create({
                    'provider': p,
                    'status': 'error',
                    'error_message': err_msg,
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_seconds': duration
                })

    @api.model
    def mark_catalog_stale(self, provider_id):
        """
        Marks a provider's catalog as STALE without performing a sync.
        This is the exclusive entry point for invalidating a catalog status.
        """
        reg = self.env['nexora.provider.registry'].search([('provider_id', '=', provider_id)], limit=1)
        if reg:
            _logger.debug(f"Catalog Service explicitly marking catalog STALE for {provider_id}")
            reg.sudo().write({'catalog_sync_status': 'stale'})
