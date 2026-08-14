# -*- coding: utf-8 -*-
"""
nexora.connector_configuration — Connector Configuration
Part 5 of Phase 26.1 — Universal Connector Platform Refinement.
"""
from odoo import models, fields

class NexoraConnectorConfiguration(models.Model):
    _name = 'nexora.connector_configuration'
    _description = 'Nexora Connector Configuration'
    _order = 'connector_id'

    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True, ondelete='cascade', index=True)
    
    schema_json = fields.Text(string='Schema (JSON)', default='{}', help='JSON schema defining valid configuration keys and types.')
    default_values_json = fields.Text(string='Default Values (JSON)', default='{}', help='Default configuration values provided by the manifest.')
    user_overrides_json = fields.Text(string='User Overrides (JSON)', default='{}', help='Configuration values overridden by the user.')
    environment_variables_json = fields.Text(string='Environment Variables (JSON)', default='{}', help='Configuration values sourced from the environment.')
    secret_references_json = fields.Text(string='Secret References (JSON)', default='{}', help='Mapping of config keys to secret vault references.')
    
    is_valid = fields.Boolean(string='Is Valid', default=False)
    validation_errors = fields.Text(string='Validation Errors (JSON)', default='[]')
    validation_metadata_json = fields.Text(string='Validation Metadata (JSON)', default='{}')
    
    _sql_constraints = [
        ('unique_connector_configuration', 'unique(connector_id)', 'A connector can have only one configuration aggregate!')
    ]
