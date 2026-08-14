# -*- coding: utf-8 -*-
from odoo import models, fields, api

class GitRuntime(models.Model):
    _name = 'nexora.git_runtime'
    _description = 'Git Runtime State'
    
    runtime_id = fields.Many2one('nexora.runtime', string='Runtime', required=True, ondelete='cascade')
    repository_url = fields.Char(string='Repository URL', help="Remote origin URL")
    current_branch = fields.Char(string='Current Branch')
    current_commit = fields.Char(string='Current Commit')
    
    is_dirty = fields.Boolean(string='Dirty State', default=False, help="Are there uncommitted changes?")
    ahead = fields.Integer(string='Commits Ahead', default=0)
    behind = fields.Integer(string='Commits Behind', default=0)
    
    last_fetch = fields.Datetime(string='Last Fetch')
    last_pull = fields.Datetime(string='Last Pull')
    last_push = fields.Datetime(string='Last Push')
    
    branch_ids = fields.One2many('nexora.git_branch', 'git_runtime_id', string='Branches')
    commit_ids = fields.One2many('nexora.git_commit', 'git_runtime_id', string='Recent Commits')

    def action_git_fetch(self):
        service = self.env['nexora.git_service']
        for record in self:
            service.git_fetch(record.runtime_id)
            
    def action_git_pull(self):
        service = self.env['nexora.git_service']
        for record in self:
            service.git_pull(record.runtime_id)
            
    def action_git_push(self):
        service = self.env['nexora.git_service']
        for record in self:
            service.git_push(record.runtime_id)

class GitBranch(models.Model):
    _name = 'nexora.git_branch'
    _description = 'Git Branch'
    
    git_runtime_id = fields.Many2one('nexora.git_runtime', required=True, ondelete='cascade')
    name = fields.Char(string='Branch Name', required=True)
    is_remote = fields.Boolean(string='Is Remote', default=False)
    upstream = fields.Char(string='Upstream Branch')
    latest_commit = fields.Char(string='Latest Commit')

class GitCommit(models.Model):
    _name = 'nexora.git_commit'
    _description = 'Git Commit'
    _order = 'date desc'
    
    git_runtime_id = fields.Many2one('nexora.git_runtime', required=True, ondelete='cascade')
    sha = fields.Char(string='Commit SHA', required=True)
    author = fields.Char(string='Author')
    message = fields.Text(string='Message')
    date = fields.Datetime(string='Date')
