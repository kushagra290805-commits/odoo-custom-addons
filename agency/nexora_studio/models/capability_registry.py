# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .runtime_event_constants import RuntimeEvents
import logging

_logger = logging.getLogger(__name__)

class CapabilityRegistry(models.Model):
    _name = 'nexora.capability_registry'
    _description = 'Enterprise Capability Platform Registry'
    _order = 'priority desc, version desc'

    capability_id = fields.Char(string='Capability ID', required=True, index=True)
    capability_code = fields.Char(string='Capability Code', required=True, index=True)
    display_name = fields.Char(string='Display Name', required=True)
    category = fields.Char(string='Category', required=True)
    version = fields.Char(string='Version', required=True)
    author = fields.Char(string='Author')
    provider = fields.Char(string='Provider')
    implementation_model = fields.Char(string='Implementation Model', required=True)
    checksum = fields.Char(string='Checksum (SHA-256)', required=True)
    
    supported_platforms = fields.Char(string='Supported Platforms')
    supports_local = fields.Boolean(string='Supports Local', default=True)
    supports_remote = fields.Boolean(string='Supports Remote', default=False)
    supports_async = fields.Boolean(string='Supports Async', default=False)
    
    permissions = fields.Char(string='Permissions')
    dependencies = fields.Char(string='Dependencies')
    optional_dependencies = fields.Char(string='Optional Dependencies')
    conflicts = fields.Char(string='Conflicts')
    
    minimum_runtime_version = fields.Char(string='Min Runtime Version')
    maximum_runtime_version = fields.Char(string='Max Runtime Version')
    metadata_version = fields.Char(string='Metadata Version')
    
    state = fields.Selection([
        (RuntimeEvents.CAPABILITY_DISCOVERED, 'Discovered'),
        (RuntimeEvents.CAPABILITY_VALIDATED, 'Validated'),
        (RuntimeEvents.CAPABILITY_INSTALLED, 'Installed'),
        (RuntimeEvents.CAPABILITY_ENABLED, 'Enabled'),
        (RuntimeEvents.CAPABILITY_DEGRADED, 'Degraded'),
        (RuntimeEvents.CAPABILITY_DISABLED, 'Disabled'),
        (RuntimeEvents.CAPABILITY_REMOVED, 'Removed')
    ], string='State', default=RuntimeEvents.CAPABILITY_DISCOVERED, required=True, index=True)
    
    enabled = fields.Boolean(string='Enabled', compute='_compute_enabled', store=True, index=True)
    priority = fields.Integer(string='Priority', default=10)
    
    metadata_json = fields.Text(string='Metadata (JSON)', default='{}')
    
    health_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('failed', 'Failed')
    ], string='Health Status', default='unknown')
    
    last_validation = fields.Datetime(string='Last Validation')
    
    startup_priority = fields.Integer(string='Startup Priority', default=100)
    shutdown_priority = fields.Integer(string='Shutdown Priority', default=100)

    _sql_constraints = [
        ('unique_capability_id', 'unique(capability_id)', 'Capability ID must be unique!'),
    ]

    @api.depends('state')
    def _compute_enabled(self):
        for record in self:
            record.enabled = (record.state == RuntimeEvents.CAPABILITY_ENABLED)

    @api.constrains('state', 'capability_code')
    def _check_single_active_version(self):
        for record in self:
            if record.state == RuntimeEvents.CAPABILITY_ENABLED:
                active_siblings = self.search([
                    ('capability_code', '=', record.capability_code),
                    ('state', '=', RuntimeEvents.CAPABILITY_ENABLED),
                    ('id', '!=', record.id)
                ])
                if active_siblings:
                    raise ValidationError(_("Only one version of capability code '%s' can be enabled at a time.") % record.capability_code)

    def validate_capability(self):
        return True
        
    def check_health(self):
        for record in self:
            record.health_status = 'healthy'
            
    @property
    def capability_name(self):
        return self.display_name
        
    @property
    def capability_type(self):
        return self.category
