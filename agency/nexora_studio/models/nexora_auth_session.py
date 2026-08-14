from odoo import models, fields, api

class NexoraAuthSession(models.Model):
    _name = 'nexora.auth.session'
    _description = 'Nexora Auth Session Tracking'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string="User", required=True, ondelete='cascade', index=True)
    session_id = fields.Char(string="Odoo Session ID", required=True, index=True)
    ip_address = fields.Char(string="IP Address")
    browser = fields.Char(string="Browser / User Agent")
    last_activity = fields.Datetime(string="Last Activity", default=fields.Datetime.now)
    logout_time = fields.Datetime(string="Logout Time")
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('logged_out', 'Logged Out'),
        ('forced_logout', 'Forced Logout')
    ], string="Status", default='active', required=True)

    def action_force_logout(self):
        for record in self:
            if record.status == 'active':
                record.status = 'forced_logout'
                record.logout_time = fields.Datetime.now()
                # A cron or middleware would intercept session_id if forced_logout.
                # Since we use Odoo native sessions, killing the session natively might require deleting it from ir.sessions (if database backed) or clearing session store.
                # For now, mark it in this tracking model. We can enforce it in the controller if we check this model, but typically standard Odoo session works.
