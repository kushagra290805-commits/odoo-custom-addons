# -*- coding: utf-8 -*-
from odoo import models, fields
class NexoraConnectorLog(models.Model):
    _name = 'nexora.connector_log'
    _description = 'Nexora Connector Log'
    _order = 'logged_at desc'
    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    log_level = fields.Selection([('debug','DEBUG'),('info','INFO'),('warning','WARNING'),('error','ERROR'),('critical','CRITICAL')], string='Level', default='info', required=True, index=True)
    message = fields.Text(string='Message', required=True)
    context_json = fields.Text(string='Context (JSON)', default='{}')
    logged_at = fields.Datetime(string='Logged At', default=fields.Datetime.now, index=True)
