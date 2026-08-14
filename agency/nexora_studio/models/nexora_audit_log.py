from odoo import models, fields

class NexoraAuditLog(models.Model):
    _name = 'nexora.audit.log'
    _description = 'Nexora Audit Log'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string="User", ondelete='set null', index=True)
    action = fields.Selection([
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('password_reset', 'Password Reset'),
        ('password_change', 'Password Change'),
        ('account_lock', 'Account Lock'),
        ('account_unlock', 'Account Unlock'),
        ('user_create', 'User Creation'),
        ('user_delete', 'User Deletion'),
        ('permission_change', 'Permission Change'),
        ('role_assign', 'Role Assignment'),
        ('force_logout', 'Force Logout')
    ], string="Action", required=True, index=True)
    ip_address = fields.Char(string="IP Address")
    browser = fields.Char(string="Browser")
    session_id = fields.Char(string="Session ID")
    result = fields.Selection([
        ('success', 'Success'),
        ('failure', 'Failure')
    ], string="Result", default='success', required=True)
    details = fields.Text(string="Details")
