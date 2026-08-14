# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PreviewRuntime(models.Model):
    _name = 'nexora.preview_runtime'
    _description = 'Preview Runtime State'
    
    runtime_id = fields.Many2one('nexora.runtime', string='Runtime', required=True, ondelete='cascade')
    @api.model
    def _get_launcher_types(self):
        launchers = [
            ('python_http', 'Python HTTP Server'),
            ('static_file', 'Static File Server'),
            ('vite', 'Vite Dev Server'),
            ('react', 'React Dev Server'),
            ('nextjs', 'Next.js Dev Server'),
            ('vue', 'Vue Dev Server'),
            ('astro', 'Astro Dev Server'),
            ('odoo', 'Odoo Dev Server'),
            ('custom', 'Custom Launcher')
        ]
        try:
            for l in self.env['nexora.preview_service'].get_all_launchers():
                manifest = l.launcher_manifest()
                l_id = manifest.get('launcher_id') or manifest.get('launcher_type')
                display = manifest.get('display_name', l_id)
                if l_id and not any(x[0] == l_id for x in launchers):
                    launchers.append((l_id, display))
        except Exception:
            pass
        return launchers

    launcher_type = fields.Selection(selection='_get_launcher_types', string='Launcher Type', default='python_http', required=True)
    
    status = fields.Selection(related='runtime_id.status', string='Status', readonly=True)
    health = fields.Selection(related='runtime_id.health', string='Health', readonly=True)
    
    preview_command = fields.Char(string='Preview Command', help="Exact command string used by the launcher strategy")
    allocated_port = fields.Integer(string='Allocated Port', default=0)
    preview_url = fields.Char(string='Preview URL')
    process_id = fields.Integer(string='Process ID', default=0)
    
    started_at = fields.Datetime(string='Started At', readonly=True)
    stopped_at = fields.Datetime(string='Stopped At', readonly=True)
    last_health_check = fields.Datetime(string='Last Health Check', readonly=True)
    last_activity = fields.Datetime(string='Last Activity', readonly=True)

    def _ensure_not_transitioning(self):
        for record in self:
            if record.status in ('starting', 'stopping'):
                raise ValidationError(_("Lifecycle action disabled while runtime is transitioning (status: %s)." % record.status))

    def action_start_preview(self):
        self._ensure_not_transitioning()
        service = self.env['nexora.preview_service']
        for record in self:
            service.start_preview(record.runtime_id)
        return True

    def action_stop_preview(self):
        self._ensure_not_transitioning()
        service = self.env['nexora.preview_service']
        for record in self:
            service.stop_preview(record.runtime_id)
        return True

    def action_restart_preview(self):
        self._ensure_not_transitioning()
        service = self.env['nexora.preview_service']
        for record in self:
            service.restart_preview(record.runtime_id)
        return True

    def action_refresh_status(self):
        self._ensure_not_transitioning()
        service = self.env['nexora.preview_service']
        for record in self:
            service.check_health(record.runtime_id)
        return True

    def action_open_preview(self):
        self.ensure_one()
        if not self.preview_url:
            raise ValidationError(_("Preview URL is not available. Please start the preview first."))
        return {
            'type': 'ir.actions.act_url',
            'url': self.preview_url,
            'target': 'new',
        }
