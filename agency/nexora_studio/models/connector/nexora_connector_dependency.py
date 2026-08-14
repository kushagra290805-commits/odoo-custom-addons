# -*- coding: utf-8 -*-
from odoo import models, fields
class NexoraConnectorDependency(models.Model):
    _name = 'nexora.connector_dependency'
    _description = 'Nexora Connector Dependency'
    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    depends_on_connector_id = fields.Many2one('nexora.connector', string='Depends On', required=True, ondelete='restrict')
    dependency_type = fields.Selection([('required','Required'),('optional','Optional'),('conflicts_with','Conflicts With')], string='Type', default='required', required=True)
    version_constraint = fields.Char(string='Version Constraint', default='*', help='Semver range e.g. >=1.0.0 or ^2.0.0')
    description = fields.Char(string='Description')
