# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProjectBlueprint(models.Model):
    _name = 'nexora.project_blueprint'
    _description = 'Project Blueprint (Information Architecture)'
    
    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade', index=True)
    status = fields.Selection([('draft', 'Draft'), ('generated', 'Generated'), ('validated', 'Validated')], default='draft')
    
    information_architecture = fields.Text(string='Information Architecture')
    navigation_structure = fields.Text(string='Navigation Structure')
    pages_json = fields.Text(string='Pages (JSON)')
    component_hierarchy_json = fields.Text(string='Component Hierarchy (JSON)')
    design_system_json = fields.Text(string='Design System (JSON)')
    integrations_json = fields.Text(string='Integrations (JSON)')
    seo_requirements = fields.Text(string='SEO Requirements')
    performance_goals = fields.Text(string='Performance Goals')


class ExecutionPlan(models.Model):
    _name = 'nexora.execution_plan'
    _description = 'Autonomous Execution Plan'
    
    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade', index=True)
    project_blueprint_id = fields.Many2one('nexora.project_blueprint', string='Blueprint', ondelete='cascade')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('validating', 'Validating'),
        ('validated', 'Validated'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='draft')
    
    stage_ids = fields.One2many('nexora.execution_stage', 'plan_id', string='Stages')


class ExecutionStage(models.Model):
    _name = 'nexora.execution_stage'
    _description = 'Execution Stage'
    _order = 'sequence asc, id asc'
    
    plan_id = fields.Many2one('nexora.execution_plan', string='Plan', required=True, ondelete='cascade')
    name = fields.Char(string='Stage Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending')
    
    task_ids = fields.One2many('nexora.execution_task', 'stage_id', string='Tasks')


class GenerationManifest(models.Model):
    _name = 'nexora.generation_manifest'
    _description = 'Generation Manifest'
    
    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade', index=True)
    execution_plan_id = fields.Many2one('nexora.execution_plan', string='Execution Plan', ondelete='cascade')
    
    pages_json = fields.Text(string='Pages Map (JSON)')
    routes_json = fields.Text(string='Routes (JSON)')
    components_json = fields.Text(string='Components (JSON)')
    assets_json = fields.Text(string='Assets (JSON)')
    apis_json = fields.Text(string='APIs (JSON)')
    forms_json = fields.Text(string='Forms (JSON)')
    seo_requirements = fields.Text(string='SEO Guidelines')
    shared_resources_json = fields.Text(string='Shared Resources (JSON)')
    dependencies_json = fields.Text(string='Dependencies (JSON)')
    metadata_json = fields.Text(string='Generation Metadata (JSON)')

class ExecutionTask(models.Model):
    _name = 'nexora.execution_task'
    _description = 'Execution Task'
    
    stage_id = fields.Many2one('nexora.execution_stage', string='Stage', required=True, ondelete='cascade')
    name = fields.Char(string='Task Name', required=True)
    objective = fields.Text(string='Objective')
    inputs_json = fields.Text(string='Inputs (JSON)')
    outputs_json = fields.Text(string='Outputs (JSON)')
    required_capability = fields.Char(string='Required Capability')
    validation_rules = fields.Text(string='Validation Rules')
    rollback_strategy = fields.Text(string='Rollback Strategy')
    
    retries = fields.Integer(string='Retries', default=0)
    last_error = fields.Text(string='Last Error')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('generated', 'Generated'),
        ('validated', 'Validated'),
        ('committed', 'Committed'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending')


class PlanDependency(models.Model):
    _name = 'nexora.plan_dependency'
    _description = 'Execution Task Dependency'
    
    task_id = fields.Many2one('nexora.execution_task', string='Task', required=True, ondelete='cascade', help='The task that depends on another task')
    depends_on_task_id = fields.Many2one('nexora.execution_task', string='Depends On', required=True, ondelete='cascade', help='The task that must finish first')
