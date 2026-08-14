# -*- coding: utf-8 -*-
from odoo import models, fields, api

class NexoraProject(models.Model):
    _name = 'nexora.project'
    _description = 'Nexora Client Project'

    name = fields.Char(string='Project Name', required=True)
    partner_id = fields.Many2one('res.partner', string='Client')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('closed', 'Closed')
    ], string='Status', default='draft', required=True)
    request_ids = fields.One2many('nexora.project_request', 'project_id', string='Requests')
    assigned_model_id = fields.Many2one('nexora.ai_model_catalog', string='Assigned Model', help='Deterministic canonical model assignment overriding provider defaults for this project.')


class NexoraProjectRequest(models.Model):
    _name = 'nexora.project_request'
    _description = 'Nexora Project Request'

    project_id = fields.Many2one('nexora.project', string='Project', required=True, ondelete='cascade')
    name = fields.Char(string='Request Title', required=True)
    request_type = fields.Selection([
        ('new_website', 'New Website'),
        ('redesign', 'Website Redesign'),
        ('maintenance', 'Maintenance'),
        ('bug_fix', 'Bug Fix'),
        ('feature_request', 'Feature Request'),
        ('ai_automation', 'AI Automation'),
        ('seo_work', 'SEO Work'),
        ('hosting_migration', 'Hosting Migration'),
        ('performance_optimization', 'Performance Optimization')
    ], string='Request Type', required=True)
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', required=True)

    requirements_id = fields.Many2one('nexora.project_requirements', string='Project Requirements', required=True, ondelete='restrict')
    assignment_ids = fields.One2many('nexora.developer_assignment', 'request_id', string='Developer Assignments')


class NexoraProjectRequirements(models.Model):
    _name = 'nexora.project_requirements'
    _description = 'Project Requirements (Business Source of Truth)'

    name = fields.Char(string='Reference Name', required=True)
    request_id = fields.Many2one('nexora.project_request', string='Project Request', required=True, ondelete='cascade')
    
    business_name = fields.Char(string='Business Name')
    industry = fields.Char(string='Industry')
    company_description = fields.Text(string='Company Description')
    branding_details = fields.Text(string='Branding & Colors')
    required_pages = fields.Text(string='Required Pages')
    required_features = fields.Text(string='Required Features')
    integrations = fields.Text(string='Integrations')
    seo_preferences = fields.Text(string='SEO Preferences')
    client_notes = fields.Text(string='Client Notes')


class NexoraDeveloperAssignment(models.Model):
    _name = 'nexora.developer_assignment'
    _description = 'Developer Assignment'

    request_id = fields.Many2one('nexora.project_request', string='Project Request', required=True, ondelete='cascade')
    developer_id = fields.Many2one('res.users', string='Assigned Developer', required=True)
    
    status = fields.Selection([
        ('assigned', 'Assigned'),
        ('active', 'Active'),
        ('blocked', 'Blocked'),
        ('completed', 'Completed'),
        ('reassigned', 'Reassigned')
    ], string='Status', default='assigned', required=True)

    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session')

