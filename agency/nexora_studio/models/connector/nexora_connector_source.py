# -*- coding: utf-8 -*-
"""
nexora.connector_source — Generic Connector Source
Part 1 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields, api

class NexoraConnectorSource(models.Model):
    _name = 'nexora.connector_source'
    _description = 'Connector Source'
    _order = 'priority asc, name asc'

    name = fields.Char(string='Name', required=True)
    source_type = fields.Selection([
        ('marketplace', 'Marketplace'),
        ('git', 'Git Repository'),
        ('local', 'Local Directory'),
        ('enterprise', 'Enterprise Registry'),
        ('upload', 'Direct Upload'),
    ], string='Source Type', required=True, default='marketplace', index=True)
    
    url = fields.Char(string='URL or Path')
    auth_type = fields.Selection([
        ('none', 'None'),
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth2'),
        ('basic', 'Basic Auth'),
        ('ssh', 'SSH Key'),
    ], string='Auth Type', default='none')
    
    is_official = fields.Boolean(string='Official Source', default=False)
    priority = fields.Integer(string='Priority', default=10)
    enabled = fields.Boolean(string='Enabled', default=True, index=True)
    description = fields.Text(string='Description')
    
    last_synced_at = fields.Datetime(string='Last Synced At', readonly=True)
    catalog_entry_ids = fields.One2many('nexora.connector_catalog', 'source_id', string='Catalog Entries')
    catalog_count = fields.Integer(string='Catalog Entries Count', compute='_compute_catalog_count')

    @api.depends('catalog_entry_ids')
    def _compute_catalog_count(self):
        for record in self:
            record.catalog_count = len(record.catalog_entry_ids)
