# -*- coding: utf-8 -*-
"""
nexora.connector_environment — Connector Execution Environment
Part 1 of Phase 26.2 — Universal Connector Platform Refinement.
"""
from odoo import models, fields

class NexoraConnectorEnvironment(models.Model):
    _name = 'nexora.connector_environment'
    _description = 'Connector Execution Environment'
    _order = 'name asc'

    # Identity
    name = fields.Char(string='Name', required=True, index=True)
    slug = fields.Char(string='Slug', required=True, index=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    # Environment Type
    environment_type = fields.Selection([
        ('local', 'Local Development'),
        ('workspace', 'Builder Workspace'),
        ('docker', 'Docker Runtime'),
        ('kubernetes', 'Kubernetes'),
        ('vps', 'VPS Production'),
        ('cloud', 'Cloud Deployment'),
        ('customer', 'Customer Deployment'),
        ('ci_runner', 'CI/CD Runner'),
    ], string='Environment Type', required=True, default='local')

    # Runtime Characteristics
    operating_system = fields.Char(string='Operating System', help='e.g., linux, windows, darwin')
    architecture = fields.Char(string='Architecture', help='e.g., x86_64, arm64')
    python_version = fields.Char(string='Python Version')
    runtime_version = fields.Char(string='Runtime Version')
    container_runtime = fields.Char(string='Container Runtime', help='e.g., docker, containerd')

    # Execution Constraints
    internet_access = fields.Boolean(string='Internet Access', default=True)
    filesystem_access = fields.Boolean(string='Filesystem Access', default=True)
    max_memory_mb = fields.Integer(string='Max Memory (MB)', default=1024)
    max_cpu_cores = fields.Float(string='Max CPU Cores', default=1.0)
    max_execution_time_s = fields.Integer(string='Max Execution Time (s)', default=300)

    # Configuration
    environment_variables_json = fields.Text(string='Environment Variables (JSON)', default='{}')
    default_configuration_json = fields.Text(string='Default Configuration (JSON)', default='{}')
    secret_provider_reference = fields.Char(string='Secret Provider Ref', help='Identifier for the secrets vault used in this env.')

    # Metadata
    tags = fields.Char(string='Tags')
    metadata_json = fields.Text(string='Metadata (JSON)', default='{}')

    _sql_constraints = [
        ('unique_environment_slug', 'unique(slug)', 'Environment slug must be globally unique!')
    ]
