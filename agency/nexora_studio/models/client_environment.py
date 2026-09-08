# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ClientEnvironment(models.Model):
    _name = 'nexora.client_environment'
    _description = 'Client Environment'
    _order = 'create_date desc'

    project_id = fields.Many2one('nexora.project', string='Project', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Environment Name', required=True)
    db_name = fields.Char(string='Database Name', required=True, index=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('provisioning', 'Provisioning'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
        ('deleting', 'Deleting'),
        ('deleted', 'Deleted'),
    ], string='Status', default='draft', required=True, index=True)
    error_message = fields.Text(string='Error Message')
    encrypted_admin_password = fields.Text(string='Encrypted Admin Password')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)

    # ── Phase 47.34: module provisioning state ────────────────────────────────
    # Deliberately SEPARATE from the DB lifecycle `status` field:
    #   DB lifecycle state    = ready / failed / deleted (database existence)
    #   module provisioning   = approved plan execution outcome (47.34)
    # A module provisioning failure never falsifies the DB lifecycle state.
    module_provisioning_state = fields.Selection([
        ('none', 'Not Provisioned'),
        ('provisioning', 'Provisioning Modules'),
        ('provisioned', 'Modules Provisioned'),
        ('partial', 'Partially Provisioned'),
        ('failed', 'Module Provisioning Failed'),
    ], string='Module Provisioning State', default='none', required=True, index=True)
    module_plan = fields.Text(string='Approved Module Plan (JSON)')
    module_provisioning_result = fields.Text(string='Module Provisioning Result (JSON)')
    module_provisioning_error = fields.Text(string='Module Provisioning Error')

    # ── Phase 47.35: client API authentication credential ────────────────────
    # ONE active client API token per environment. The PLAINTEXT token is
    # returned exactly once at issuance (control-plane action); only a
    # SHA-256 hash is stored. The token — never a db_name or environment
    # id — is the sole client-side resolution key.
    client_api_token_hash = fields.Char(string='Client API Token (SHA-256)')
    client_api_token_issued_at = fields.Datetime(string='Client API Token Issued At')
    client_api_token_expires_at = fields.Datetime(string='Client API Token Expires At')
    client_api_token_active = fields.Boolean(string='Client API Token Active', default=False)

    _sql_constraints = [
        ('db_name_uniq', 'unique(db_name)', 'Database name must be unique.'),
    ]

    @api.constrains('db_name')
    def _check_db_name(self):
        import re
        for rec in self:
            if not re.match(r'^[a-zA-Z0-9_]+$', rec.db_name):
                raise ValidationError(_('Database name must contain only letters, numbers, and underscores.'))
            # Phase 47.34.x safety hardening: a client environment can
            # never be (re-)pointed at the agency database, regardless of
            # the write path. Fail closed on ambiguous identity.
            if self.env['nexora.client_environment_service']._is_agency_database(rec.db_name):
                raise ValidationError(
                    _('Database name %s is reserved for the agency database '
                      'and cannot be used for a client environment.') % rec.db_name
                )

    def action_provision(self):
        self.ensure_one()
        if self.status not in ('draft', 'failed'):
            raise ValidationError(_('Only draft or failed environments can be provisioned.'))
        self.write({'status': 'provisioning'})
        self.env['nexora.client_environment_service']._provision(self)

    def action_delete(self):
        self.ensure_one()
        if self.status in ('deleted', 'deleting'):
            return
        self.write({'status': 'deleting'})
        self.env['nexora.client_environment_service']._delete(self)

    def action_provision_modules(self, capabilities):
        """Phase 47.34: install the approved module plan for this environment.

        Delegates to the canonical provisioning owner
        (``nexora.client_environment_service``); the model itself carries
        only state, never installation logic.
        """
        self.ensure_one()
        return self.env['nexora.client_environment_service'].provision_modules(
            self.id, capabilities
        )

    # ── Phase 47.35: client API token lifecycle (control plane only) ─────

    def action_issue_client_api_token(self):
        """Issue (or rotate) the client API token for this environment.

        The plaintext token is shown exactly once; only its SHA-256 hash
        is persisted. Rotation invalidates the previous token immediately.
        """
        self.ensure_one()
        result = self.env['nexora.client_environment_service'].issue_client_api_token(
            self.id
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Client API token issued'),
                'message': _('New client API token (shown once, store it now): %s')
                % result['token'],
                'sticky': True,
                'type': 'warning',
            },
        }

    def action_revoke_client_api_token(self):
        """Revoke the active client API token for this environment."""
        self.ensure_one()
        self.env['nexora.client_environment_service'].revoke_client_api_token(self.id)
        return True
