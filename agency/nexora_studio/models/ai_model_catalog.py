from odoo import models, fields, api
import json

class AICapability(models.Model):
    _name = 'nexora.ai_capability'
    _description = 'AI Capability'
    
    name = fields.Char('Capability Name', required=True, index=True)
    code = fields.Char('Capability Code', required=True, index=True)
    description = fields.Text('Description')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Capability code must be unique!')
    ]

class AIModelCatalog(models.Model):
    _name = 'nexora.ai_model_catalog'
    _description = 'AI Model Catalog'
    _order = 'provider asc, name asc'

    provider = fields.Selection([
        ('openrouter', 'OpenRouter'),
        ('ollama', 'Ollama'),
        ('nvidia', 'NVIDIA Build'),
        ('openai', 'OpenAI'),
        ('claude', 'Claude'),
        ('anthropic', 'Anthropic'),
        ('gemini', 'Gemini'),
        ('generic_openai', 'Generic OpenAI'),
        ('airouter', 'AIRouter.in'),
        ('groq', 'Groq'),
        ('test', 'Test Provider')
    ], string='Provider', required=True, index=True)
    
    model_id = fields.Char('Model ID', required=True, index=True)
    name = fields.Char('Model Name')
    
    # Pricing & Limits
    context_length = fields.Integer('Context Length')
    max_output_tokens = fields.Integer('Max Output Tokens')
    price_prompt = fields.Float('Prompt Price (USD/1k)', digits=(16, 8))
    price_completion = fields.Float('Completion Price (USD/1k)', digits=(16, 8))
    is_free = fields.Boolean('Free', compute='_compute_is_free', store=True)
    
    # Model-Specific Capabilities
    supports_vision = fields.Boolean('Vision', default=False)
    supports_tool_calling = fields.Boolean('Tool Calling', default=False)
    supports_reasoning = fields.Boolean('Reasoning', default=False)
    supports_image_generation = fields.Boolean('Image Generation', default=False)
    supports_embeddings = fields.Boolean('Embeddings', default=False)
    supports_streaming = fields.Boolean('Streaming', default=False)
    supports_json = fields.Boolean('JSON Mode', default=False)
    
    # Capabilities (Relational and Raw)
    capability_ids = fields.Many2many(
        'nexora.ai_capability',
        string='Capabilities',
        help='Normalized capabilities used for routing (e.g. Code Generation, Reasoning)'
    )
    capabilities_json = fields.Text(
        'Raw Capabilities (JSON)',
        help='Raw provider-specific capability metadata'
    )
    
    # Lifecycle & Sync
    status = fields.Selection([
        ('active', 'Active'),
        ('deprecated', 'Deprecated'),
        ('unavailable', 'Unavailable')
    ], string='Status', default='active', required=True, index=True)
    deprecated_flag = fields.Boolean('Deprecated Flag', default=False, help="Set to True when upstream API flags model as deprecated")
    
    last_synced_at = fields.Datetime('Last Synced At', readonly=True)
    last_seen_at = fields.Datetime('Last Seen At', readonly=True)
    
    _sql_constraints = [
        ('provider_model_uniq', 'unique(provider, model_id)', 'Model ID must be unique per provider!')
    ]
    
    @api.depends('price_prompt', 'price_completion')
    def _compute_is_free(self):
        for rec in self:
            rec.is_free = (rec.price_prompt <= 0.0) and (rec.price_completion <= 0.0)
            
    def name_get(self):
        result = []
        for rec in self:
            price_tag = "Free" if rec.is_free else "Paid"
            result.append((rec.id, f"[{rec.provider}] {rec.name or rec.model_id} ({price_tag})"))
        return result

