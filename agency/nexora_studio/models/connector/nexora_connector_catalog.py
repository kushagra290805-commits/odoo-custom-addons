# -*- coding: utf-8 -*-
"""
nexora.connector_catalog — Connector Catalog Entry
Part 1 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields

class NexoraConnectorCatalog(models.Model):
    _name = 'nexora.connector_catalog'
    _description = 'Connector Catalog Entry'
    _order = 'name asc'

    name = fields.Char(string='Name', required=True)
    connector_id = fields.Char(string='Connector ID', required=True, index=True)
    connector_type_id = fields.Many2one('nexora.connector_type', string='Connector Type', required=True, ondelete='restrict')
    
    source_id = fields.Many2one('nexora.connector_source', string='Source', required=True, ondelete='cascade', index=True)
    
    publisher = fields.Char(string='Publisher')
    description = fields.Text(string='Description')
    latest_version = fields.Char(string='Latest Version')
    
    download_url = fields.Char(string='Download URL')
    homepage_url = fields.Char(string='Homepage URL')
    
    verified = fields.Boolean(string='Verified', default=False)
    tags = fields.Char(string='Tags')
    
    available = fields.Boolean(string='Available', default=True, index=True)
    
    _sql_constraints = [
        ('unique_source_connector', 'unique(source_id, connector_id)', 'A connector ID can only appear once per source!')
    ]
