# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PluginCategory(models.Model):
    _name = 'nexora.plugin.category'
    _description = 'Plugin Category'
    
    name = fields.Char(required=True)
    description = fields.Text()

class PluginRegistry(models.Model):
    _name = 'nexora.plugin.registry'
    _description = 'Plugin Marketplace / Registry'

    name = fields.Char(required=True)
    provider_name = fields.Char(required=True)
    category_id = fields.Many2one('nexora.plugin.category', string="Category")
    version = fields.Char(default="1.0.0")
    status = fields.Selection([
        ('uninstalled', 'Uninstalled'),
        ('installed', 'Installed'),
        ('active', 'Active'),
        ('error', 'Error')
    ], default='uninstalled')
    capabilities = fields.Text(help="JSON list of capabilities exposed")
    dependencies = fields.Text(help="JSON list of dependencies")
    health = fields.Selection([('ok', 'OK'), ('degraded', 'Degraded'), ('failing', 'Failing')], default='ok')
    configuration_status = fields.Boolean(default=False)
