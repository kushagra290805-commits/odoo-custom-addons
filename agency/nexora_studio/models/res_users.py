from odoo import models, fields, api, exceptions, _

class ResUsers(models.Model):
    _inherit = 'res.users'

    is_nexora_user = fields.Boolean(string="Is Nexora User", default=False, tracking=True)
    nexora_last_login = fields.Datetime(string="Nexora Last Login", readonly=True, tracking=True)
    must_change_password = fields.Boolean(string="Must Change Password", default=False, tracking=True)
    account_locked = fields.Boolean(string="Account Locked", default=False, tracking=True)
    failed_login_count = fields.Integer(string="Failed Login Count", default=0, tracking=True)

    def write(self, vals):
        if 'login' in vals:
            # Username is immutable unless explicitly forced by Super Admin in a specific context
            # We enforce strict immutability.
            if not self.env.context.get('force_change_username'):
                for user in self:
                    if user.login and user.login != vals['login']:
                        raise exceptions.UserError(_("Username (login) is immutable and cannot be changed."))
        
        return super(ResUsers, self).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_nexora_user') and not vals.get('password'):
                vals['must_change_password'] = True
        return super(ResUsers, self).create(vals_list)

