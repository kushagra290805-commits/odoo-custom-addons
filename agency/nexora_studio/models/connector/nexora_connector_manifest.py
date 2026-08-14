# -*- coding: utf-8 -*-
"""
nexora.connector_manifest — Connector Manifest
Part 2 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields

class NexoraConnectorManifest(models.Model):
    _name = 'nexora.connector_manifest'
    _description = 'Connector Manifest'
    _order = 'connector_id asc'

    connector_id = fields.Char(string='Connector ID', required=True, index=True)
    display_name = fields.Char(string='Display Name', required=True)
    connector_type_id = fields.Many2one('nexora.connector_type', string='Connector Type', required=True, ondelete='restrict')
    
    description = fields.Text(string='Description')
    author = fields.Char(string='Author')
    publisher = fields.Char(string='Publisher')
    license_type = fields.Char(string='License')
    
    homepage_url = fields.Char(string='Homepage URL')
    documentation_url = fields.Char(string='Documentation URL')
    
    tags = fields.Char(string='Tags')
    metadata_json = fields.Text(string='Metadata (JSON)', default='{}')

    release_ids = fields.One2many('nexora.connector_release', 'manifest_id', string='Releases')

    _sql_constraints = [
        ('unique_connector_id', 'unique(connector_id)', 'Connector ID must be globally unique!')
    ]
