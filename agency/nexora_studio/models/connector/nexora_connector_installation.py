# -*- coding: utf-8 -*-
from odoo import models, fields
class NexoraConnectorInstallation(models.Model):
    _name = 'nexora.connector_installation'
    _description = 'Nexora Connector Installation'
    _order = 'installed_at desc'
    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    release_id = fields.Many2one('nexora.connector_release', string='Release', required=True, ondelete='restrict', index=True)
    environment_id = fields.Many2one('nexora.connector_environment', string='Environment', required=True, ondelete='restrict', index=True)
    installed_by = fields.Many2one('res.users', string='Installed By', default=lambda self: self.env.user)
    installed_at = fields.Datetime(string='Installed At', default=fields.Datetime.now)
    installation_path = fields.Char(string='Installation Path')
    install_log = fields.Text(string='Install Log')
    state = fields.Selection([('pending','Pending'),('installed','Installed'),('failed','Failed'),('uninstalled','Uninstalled')], string='State', default='pending', required=True, index=True)
    installation_metadata = fields.Text(string='Metadata (JSON)', default='{}')
