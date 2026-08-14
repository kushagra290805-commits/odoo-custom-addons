# -*- coding: utf-8 -*-
"""
nexora.connector_release — Connector Release
Part 2 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields, api

class NexoraConnectorRelease(models.Model):
    _name = 'nexora.connector_release'
    _description = 'Connector Release'
    _order = 'released_at desc'

    manifest_id = fields.Many2one('nexora.connector_manifest', string='Manifest', required=True, ondelete='cascade', index=True)
    version_string = fields.Char(string='Version', required=True)
    
    source_id = fields.Many2one('nexora.connector_source', string='Source', ondelete='restrict', index=True)
    
    changelog = fields.Text(string='Changelog')
    released_at = fields.Datetime(string='Released At', default=fields.Datetime.now)
    is_current = fields.Boolean(string='Is Current', default=False, index=True)
    
    checksum = fields.Char(string='SHA-256 Checksum')
    download_url = fields.Char(string='Download URL')
    
    installation_ids = fields.One2many('nexora.connector_installation', 'release_id', string='Installations')

    _sql_constraints = [
        ('unique_manifest_version', 'unique(manifest_id, version_string)', 'Release version must be unique per manifest!')
    ]

    @api.constrains('is_current', 'manifest_id')
    def _check_single_current(self):
        for record in self:
            if record.is_current:
                others = self.search([
                    ('manifest_id', '=', record.manifest_id.id),
                    ('is_current', '=', True),
                    ('id', '!=', record.id)
                ])
                if others:
                    others.write({'is_current': False})
