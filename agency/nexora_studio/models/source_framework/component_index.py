# -*- coding: utf-8 -*-
from odoo import models, fields

class ComponentIndex(models.Model):
    _name = 'nexora.component_index'
    _description = 'Component Index & Cache'
    _order = 'indexing_timestamp desc'

    component_id = fields.Char(required=True, index=True, help="Unique ID from the provider")
    provider_id = fields.Many2one('nexora.source_registry', required=True, ondelete='cascade')
    
    name = fields.Char(required=True)
    description = fields.Text()
    
    # Provenance
    repository = fields.Char()
    commit_sha = fields.Char()
    release_version = fields.Char()
    license_type = fields.Char()
    import_source = fields.Char()
    import_timestamp = fields.Datetime(default=fields.Datetime.now)
    
    # Cache metadata
    provider_version = fields.Char()
    cache_version = fields.Char(default="1.0")
    indexing_timestamp = fields.Datetime(default=fields.Datetime.now)
    
    # Interaction Type (meaningful interactions only)
    interaction_type = fields.Selection([
        ('previewed', 'Previewed'),
        ('installed', 'Installed'),
        ('ai_selected', 'AI Selected')
    ], required=True)
    
    # Data
    package_data = fields.Text(help="Serialized ComponentPackage domain model")
    
    # Semantic Search Readiness (Extension points)
    semantic_tags = fields.Text(help="Comma-separated tags for semantic search")
    ai_summary = fields.Text(help="AI-generated summary for vector search")
