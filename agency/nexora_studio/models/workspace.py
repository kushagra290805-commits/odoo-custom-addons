# -*- coding: utf-8 -*-
import os
import re
import logging
from pathlib import Path
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import uuid

_logger = logging.getLogger(__name__)


class Workspace(models.Model):
    _name = 'nexora.workspace'
    _description = 'Workspace Runtime'

    # ORCHESTRATION RULE:
    # Workspace ONLY represents the local filesystem state.
    # It does NOT orchestrate other runtimes.
    # Runtimes (Git, Preview, MCP, etc.) attach to Builder Session, NOT Workspace.

    name = fields.Char(string='Name', required=True)
    
    workspace_uuid = fields.Char(
        string='Workspace UUID',
        required=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        readonly=True
    )

    workspace_slug = fields.Char(
        string='Workspace Slug',
        required=True,
        copy=False,
        readonly=True,
        help="Filesystem-safe identifier used for the physical folder name."
    )

    initialized_at = fields.Datetime(
        string='Initialized At',
        readonly=True,
        help="When the workspace was physically created on the filesystem."
    )

    # Stored path written after successful initialization.
    workspace_path = fields.Char(
        string='Workspace Path',
        copy=False,
        readonly=True,
        help='The physical path where this workspace resides on disk. Populated after initialization.'
    )

    # Computed display field — always shows the resolved path even before initialization.
    resolved_path = fields.Char(
        string='Resolved Path',
        compute='_compute_resolved_path',
        store=False,
        readonly=True,
        help='The expected filesystem path for this workspace (resolved from the configured workspace root).'
    )

    status = fields.Selection([
        ('missing', 'Missing'),
        ('initializing', 'Initializing'),
        ('ready', 'Ready'),
        ('busy', 'Busy'),
        ('error', 'Error')
    ], string='Status', default='missing', required=True, copy=False)

    size_bytes = fields.Char(string='Size', default='0 MB', readonly=True)
    last_scan = fields.Datetime(string='Last Scan', readonly=True)
    last_activity = fields.Datetime(string='Last Activity')

    health = fields.Selection([
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('partial', 'Partial/Corrupted'),
        ('missing', 'Missing')
    ], string='Health', default='unknown', readonly=True)

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('workspace_uuid_uniq', 'unique(workspace_uuid)', 'Workspace UUID must be unique!'),
        ('workspace_path_uniq', 'unique(workspace_path)', 'Workspace Path must be unique!'),
        ('workspace_slug_uniq', 'unique(workspace_slug)', 'Workspace slug must be unique!'),
    ]

    def _generate_slug(self, name):
        """Generates a filesystem-safe slug from the name."""
        if not name:
            return "unnamed-workspace"
        
        # Lowercase
        slug = name.lower()
        # Spaces to hyphens
        slug = slug.replace(' ', '-')
        # Remove invalid windows characters
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        # Trim duplicate hyphens
        slug = re.sub(r'-+', '-', slug)
        # Trim leading/trailing hyphens
        slug = slug.strip('-')
        
        if not slug:
            slug = "workspace"
            
        return slug

    def _get_unique_slug(self, base_slug, current_id=None):
        """Ensures the slug is globally unique across all workspaces."""
        slug = base_slug
        counter = 2
        
        domain = [('workspace_slug', '=', slug)]
        if current_id:
            domain.append(('id', '!=', current_id))
            
        while self.search_count(domain) > 0:
            slug = f"{base_slug}-{counter}"
            counter += 1
            domain = [('workspace_slug', '=', slug)]
            if current_id:
                domain.append(('id', '!=', current_id))
                
        return slug

    @api.onchange('name')
    def _onchange_name_generate_slug(self):
        """Automatically preview the slug in the UI when the name changes, if not initialized."""
        for record in self:
            if record.name and not record.initialized_at:
                base_slug = self._generate_slug(record.name)
                # Note: onchange uniqueness isn't perfect for concurrent usage,
                # but create/write guarantees it.
                record.workspace_slug = self._get_unique_slug(base_slug, getattr(record, 'id', None))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals and not vals.get('workspace_slug'):
                base_slug = self._generate_slug(vals['name'])
                vals['workspace_slug'] = self._get_unique_slug(base_slug)
        return super(Workspace, self).create(vals_list)

    def write(self, vals):
        # Prevent manual slug changes if already initialized
        if 'workspace_slug' in vals:
            for record in self:
                if record.initialized_at and vals['workspace_slug'] != record.workspace_slug:
                    raise UserError(_("Workspace slug cannot be changed after the workspace is initialized. Use the 'Rename Workspace Folder' action."))
                    
        # Auto-update slug if name changes and not initialized
        if 'name' in vals and 'workspace_slug' not in vals:
            for record in self:
                if not record.initialized_at:
                    base_slug = self._generate_slug(vals['name'])
                    unique_slug = self._get_unique_slug(base_slug, record.id)
                    # We can't update individual records cleanly inside a batched write if we need different values per record,
                    # but for single record writes it's fine. For multi, we handle it sequentially:
                    super(Workspace, record).write({'workspace_slug': unique_slug})
                    
        return super(Workspace, self).write(vals)

    @api.depends('workspace_slug')
    def _compute_resolved_path(self):
        """
        Computes the expected filesystem path for this workspace using the
        configured workspace root. This is a read-only display field.
        Does NOT require the directory to exist.
        """
        service = self.env['nexora.workspace_service']
        for record in self:
            if record.workspace_slug:
                record.resolved_path = service.resolve_workspace_path(record)
            else:
                record.resolved_path = ''

    @api.ondelete(at_uninstall=False)
    def _check_physical_directory_before_unlink(self):
        for record in self:
            if record.workspace_path:
                path_exists = os.path.exists(record.workspace_path)
                _logger.info(
                    f"[nexora.workspace ondelete validation] Checking workspace_path='{record.workspace_path}', "
                    f"os.path.exists={path_exists}"
                )
                if path_exists:
                    raise ValidationError(_(
                        "Please delete the physical workspace directory before deleting the Workspace record."
                    ))

    def unlink(self):
        for record in self:
            if record.workspace_path:
                path_exists = os.path.exists(record.workspace_path)
                _logger.info(
                    f"[nexora.workspace unlink validation] Checking workspace_path='{record.workspace_path}', "
                    f"os.path.exists={path_exists}"
                )
                if path_exists:
                    raise ValidationError(_(
                        "Please delete the physical workspace directory before deleting the Workspace record."
                    ))
        return super(Workspace, self).unlink()

    def action_initialize_workspace(self):
        """
        Initialize Workspace button action.
        """
        service = self.env['nexora.workspace_service']
        for record in self:
            record.status = 'initializing'
            try:
                # Passing the record directly to the service layer
                path = service.initialize_workspace(record)
                record.workspace_path = path
                record.initialized_at = fields.Datetime.now()
                record.status = 'ready'
                record.health = 'healthy'
                _logger.info(
                    f"Workspace '{record.name}' (Slug={record.workspace_slug}) "
                    f"initialized at '{path}'"
                )
            except Exception as e:
                record.status = 'error'
                raise e

    def action_reset_workspace(self):
        service = self.env['nexora.workspace_service']
        for record in self:
            record.status = 'initializing'
            try:
                path = service.reset_workspace(record)
                record.workspace_path = path
                # resetting doesn't change initialized_at, as it was already initialized
                record.status = 'ready'
                record.health = 'healthy'
            except Exception as e:
                record.status = 'error'
                raise e

    def action_delete_workspace(self):
        service = self.env['nexora.workspace_service']
        for record in self:
            service.delete_workspace(record)
            record.workspace_path = False
            record.status = 'missing'
            record.health = 'missing'

    def action_rename_workspace_folder(self):
        """Future action for safe physical renaming."""
        raise UserError(_("Renaming a workspace folder after initialization is not yet implemented."))
