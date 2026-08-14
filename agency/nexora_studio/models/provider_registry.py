from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class NexoraProviderAuditLog(models.Model):
    _name = 'nexora.provider.audit.log'
    _description = 'Provider Configuration Audit Log'
    _order = 'create_date desc'
    
    provider_id = fields.Many2one('nexora.provider.registry', string="Provider", required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    action = fields.Char(string="Action", required=True)
    details = fields.Text(string="Details")

class NexoraProviderRegistry(models.Model):
    _name = 'nexora.provider.registry'
    _description = 'Unified Provider Registry'
    _rec_name = 'name'

    provider_id = fields.Char(string='Provider ID', required=True, index=True)
    name = fields.Char(string='Name', required=True)
    
    _sql_constraints = [
        ('provider_id_uniq', 'unique(provider_id)', 'The Provider ID must be unique!')
    ]
    
    category = fields.Selection([
        ('ai', 'AI'),
        ('asset', 'Asset'),
        ('component', 'Component'),
        ('design', 'Design'),
        ('mcp', 'MCP'),
        ('preview', 'Preview'),
        ('storage', 'Storage'),
        ('custom', 'Custom'),
    ], string='Category', required=True, index=True)

    provider_type = fields.Selection([
        ('cloud', 'Cloud API'),
        ('local', 'Local API'),
        ('hybrid', 'Hybrid')
    ], string='Provider Type', default='cloud')
    
    compatibility_profile = fields.Selection([
        ('openai_compatible', 'OpenAI Compatible'),
        ('anthropic_native', 'Anthropic Native'),
        ('gemini_native', 'Gemini Native'),
        ('ollama_native', 'Ollama Native'),
        ('nvidia_nim', 'NVIDIA NIM'),
        ('custom', 'Custom')
    ], string='Compatibility Profile', default='openai_compatible')
    
    config_state = fields.Selection([
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('missing_key', 'Missing Required Fields')
    ], string='Configuration State', default='missing_key')
    
    connectivity_state = fields.Selection([
        ('reachable', 'Reachable'),
        ('unreachable', 'Unreachable'),
        ('timeout', 'Timeout')
    ], string='Connectivity State', default='unreachable')
    
    auth_state = fields.Selection([
        ('authenticated', 'Authenticated'),
        ('unauthenticated', 'Unauthenticated'),
        ('failed', 'Failed'),
        ('no_key', 'No API Key')
    ], string='Authentication State', default='no_key')
    
    lifecycle_state = fields.Selection([
        ('UNCONFIGURED', 'Unconfigured'),
        ('CONFIGURED', 'Configured'),
        ('HEALTHY', 'Healthy'),
        ('DEGRADED', 'Degraded'),
        ('UNAVAILABLE', 'Unavailable'),
        ('DISABLED', 'Disabled')
    ], string='Lifecycle State', compute='_compute_lifecycle_state', store=True, index=True)
    
    is_active = fields.Boolean(string='Active', default=True, index=True)
    priority_weight = fields.Integer(string='Priority Weight', default=10, help="Higher weight = prioritized in fallback.")
    
    # Connection Metadata
    base_url = fields.Char(string='Base URL')
    api_key = fields.Char(string='API Key')
    timeout = fields.Integer(string='Default Timeout (s)', default=60)
    retry_policy = fields.Selection([
        ('none', 'No Retry'),
        ('simple', 'Simple Retry'),
        ('exponential', 'Exponential Backoff')
    ], string='Retry Policy', default='exponential')
    
    # Health & Discovery Metadata
    health_status = fields.Char(string='Health Indicator')
    last_checked = fields.Datetime(string='Last Checked')
    latency_ms = fields.Float(string='Latency (ms)')
    authentication_status = fields.Char(string='Authentication Status')
    
    # Cached Metadata (Post-Test Connection)
    provider_version = fields.Char(string='Provider Version', default='1.0')
    manifest_version = fields.Char(string='Manifest Version', default='1.0')
    api_version = fields.Char(string='API Version', default='v1')
    supported_endpoints_json = fields.Text(string='Supported Endpoints')
    max_context_length = fields.Integer(string='Max Context Length')
    default_tokenizer = fields.Char(string='Default Tokenizer')
    last_sync_timestamp = fields.Datetime(string='Last Sync')
    
    # Pricing Metadata
    prompt_price = fields.Float('Prompt Price (USD/1k)', digits=(16, 8))
    completion_price = fields.Float('Completion Price (USD/1k)', digits=(16, 8))
    currency = fields.Char('Currency', default='USD')
    
    concurrency_json = fields.Text(string='Concurrency Policy (JSON)')
    
    # Workload Default Models
    default_model_id = fields.Many2one("nexora.ai_model_catalog", string="Default Model", domain="[('provider', '=', provider_id), ('status', '=', 'active')]", ondelete="set null")
    default_chat_model_id = fields.Many2one("nexora.ai_model_catalog", string="Default Chat Model", domain="[('provider', '=', provider_id), ('status', '=', 'active')]", ondelete="set null")
    default_code_model_id = fields.Many2one("nexora.ai_model_catalog", string="Default Code Model", domain="[('provider', '=', provider_id), ('status', '=', 'active')]", ondelete="set null")
    default_reasoning_model_id = fields.Many2one("nexora.ai_model_catalog", string="Default Reasoning Model", domain="[('provider', '=', provider_id), ('status', '=', 'active')]", ondelete="set null")
    default_vision_model_id = fields.Many2one("nexora.ai_model_catalog", string="Default Vision Model", domain="[('provider', '=', provider_id), ('status', '=', 'active')]", ondelete="set null")
    default_embedding_model_id = fields.Many2one("nexora.ai_model_catalog", string="Default Embedding Model", domain="[('provider', '=', provider_id), ('status', '=', 'active')]", ondelete="set null")

    # Selected Model Summary
    summary_model_name = fields.Char(related="default_model_id.name", string="Model Name", readonly=True)
    summary_model_provider = fields.Selection(related="default_model_id.provider", string="Model Provider", readonly=True)
    summary_model_context = fields.Integer(related="default_model_id.context_length", string="Context Window", readonly=True)
    summary_model_streaming = fields.Boolean(related="default_model_id.supports_streaming", string="Streaming", readonly=True)
    summary_model_tool_calling = fields.Boolean(related="default_model_id.supports_tool_calling", string="Tool Calling", readonly=True)
    summary_model_vision = fields.Boolean(related="default_model_id.supports_vision", string="Vision", readonly=True)
    summary_model_reasoning = fields.Boolean(related="default_model_id.supports_reasoning", string="Reasoning", readonly=True)
    summary_model_json = fields.Boolean(related="default_model_id.supports_json", string="JSON Mode", readonly=True)
    summary_model_embedding = fields.Boolean(related="default_model_id.supports_embeddings", string="Embedding Support", readonly=True)

    # Catalog Management
    catalog_last_sync = fields.Datetime("Last Catalog Sync", readonly=True)
    catalog_model_count = fields.Integer("Available Model Count", compute="_compute_catalog_stats", store=False)
    catalog_sync_status = fields.Selection([
        ("never", "Never Synced"),
        ("syncing", "Syncing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("stale", "Stale")
    ], string="Catalog Status", default="never", readonly=True)
    catalog_sync_error = fields.Text("Catalog Sync Error", readonly=True)
    last_successful_sync = fields.Datetime("Last Successful Sync", readonly=True)
    last_failed_sync = fields.Datetime("Last Failed Sync", readonly=True)
    sync_retry_count = fields.Integer("Sync Retry Count", default=0, readonly=True)

    # Capability Cache
    cap_streaming = fields.Boolean("Streaming Support", readonly=True)
    cap_tool_calling = fields.Boolean("Tool Calling Support", readonly=True)
    cap_json_mode = fields.Boolean("JSON Mode Support", readonly=True)
    cap_vision = fields.Boolean("Vision Support", readonly=True)
    cap_reasoning = fields.Boolean("Reasoning Support", readonly=True)
    cap_embeddings = fields.Boolean("Embeddings Support", readonly=True)
    cap_function_calling = fields.Boolean("Function Calling Support", readonly=True)
    cap_context_window = fields.Integer("Max Context Window", readonly=True)
    cap_max_output_tokens = fields.Integer("Max Output Tokens", readonly=True)

    # Relations
    runtime_state_ids = fields.One2many('nexora.provider.runtime_state', 'provider_id', string='Runtime State')
    migration_log_ids = fields.One2many('nexora.provider.migration_log', 'provider_id', string='Migration Logs')
    audit_log_ids = fields.One2many('nexora.provider.audit.log', 'provider_id', string='Audit Logs')

    @api.depends('provider_id', 'catalog_last_sync')
    def _compute_catalog_stats(self):
        for rec in self:
            if rec.provider_id:
                rec.catalog_model_count = self.env['nexora.ai_model_catalog'].search_count([('provider', '=', rec.provider_id), ('status', '=', 'active')])
            else:
                rec.catalog_model_count = 0

    @api.depends('config_state', 'connectivity_state', 'auth_state', 'catalog_sync_status', 'is_active')
    def _compute_lifecycle_state(self):
        for rec in self:
            if not rec.is_active:
                rec.lifecycle_state = 'DISABLED'
                continue
                
            # strict truth table logic
            if rec.config_state in ['missing_key', 'invalid'] or not rec.config_state:
                rec.lifecycle_state = 'UNCONFIGURED'
                continue

            # config is valid, but untested
            if rec.auth_state in ['unauthenticated', 'no_key']:
                rec.lifecycle_state = 'CONFIGURED'
                continue

            # config is valid and tested
            if rec.connectivity_state == 'unreachable' or rec.connectivity_state == 'timeout':
                rec.lifecycle_state = 'UNAVAILABLE'
                continue
                
            if rec.auth_state == 'failed':
                rec.lifecycle_state = 'DEGRADED'
                continue
                
            # config valid + reachable + authenticated
            if rec.catalog_sync_status == 'success':
                rec.lifecycle_state = 'HEALTHY'
            elif rec.catalog_sync_status in ['stale', 'failed']:
                rec.lifecycle_state = 'DEGRADED'
            elif rec.catalog_sync_status == 'never':
                rec.lifecycle_state = 'CONFIGURED'
            elif rec.catalog_sync_status == 'syncing':
                rec.lifecycle_state = 'HEALTHY' # assume healthy while syncing
            else:
                _logger.warning(f"Impossible state combination for {rec.provider_id}: {rec.config_state}, {rec.connectivity_state}, {rec.auth_state}, {rec.catalog_sync_status}")
                rec.lifecycle_state = 'DEGRADED'

    def _has_configuration_changed(self, vals):
        config_fields = ['api_key', 'base_url', 'compatibility_profile', 'provider_type']
        for rec in self:
            for f in config_fields:
                if f in vals and vals[f] != getattr(rec, f):
                    return True
        return False

    def write(self, vals):
        config_changed = self._has_configuration_changed(vals)
        
        if config_changed:
            _logger.debug(f"Configuration change detected for {self.ids}. Invalidating auth and connectivity.")
            vals['auth_state'] = 'unauthenticated'
            vals['connectivity_state'] = 'unreachable'
            
        # Audit Trail Tracking
        tracked_fields = ['is_active', 'base_url', 'priority_weight', 'api_key', 'compatibility_profile']
        for rec in self:
            changes = []
            for f in tracked_fields:
                if f in vals:
                    old_val = getattr(rec, f)
                    new_val = vals[f]
                    if old_val != new_val:
                        if f == 'api_key':
                            changes.append(f"Updated API Key (Value Masked)")
                        else:
                            changes.append(f"Changed {f} from '{old_val}' to '{new_val}'")
            if changes:
                self.env['nexora.provider.audit.log'].create({
                    'provider_id': rec.id,
                    'action': 'Configuration Update',
                    'details': "\\n".join(changes)
                })
                
        res = super().write(vals)

        if config_changed:
            for rec in self:
                # Recompute config_state
                needs_key = rec.compatibility_profile not in ['ollama_native', 'local']
                new_config_state = 'missing_key' if needs_key and not rec.api_key else 'valid'
                if rec.config_state != new_config_state:
                    rec.config_state = new_config_state
                # Delegate catalog invalidation to Catalog Service
                try:
                    self.env['nexora.ai_catalog_service'].mark_catalog_stale(rec.provider_id)
                except Exception as e:
                    _logger.warning(f"Failed to invalidate catalog for {rec.provider_id}: {e}")

        return res

