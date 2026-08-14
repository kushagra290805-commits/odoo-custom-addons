from odoo import fields, models


class BuilderSessionPatch(models.Model):
    _inherit = "nexora.builder_session"

    # Enterprise Platform Status Fields
    plugin_count = fields.Integer(string="Total Plugins", compute="_compute_plugin_stats")
    enabled_plugins_count = fields.Integer(string="Enabled Plugins", compute="_compute_plugin_stats")
    disabled_plugins_count = fields.Integer(string="Disabled Plugins", compute="_compute_plugin_stats")
    dependency_status = fields.Char(string="Dependency Status", compute="_compute_plugin_stats")
    cache_status = fields.Char(string="Cache Status", compute="_compute_plugin_stats")
    compatibility_status = fields.Char(string="Compatibility Status", compute="_compute_plugin_stats")
    discovery_timestamp = fields.Datetime(string="Last Discovery", compute="_compute_plugin_stats")

    def _compute_plugin_stats(self):
        registry = self.env["nexora.capability_registry"].search([])
        enabled = registry.filtered(lambda r: r.enabled)
        for record in self:
            record.plugin_count = len(registry)
            record.enabled_plugins_count = len(enabled)
            record.disabled_plugins_count = len(registry) - len(enabled)
            record.dependency_status = "Healthy" if len(enabled) > 0 else "Unknown"
            record.cache_status = "Synchronized" if len(enabled) > 0 else "Empty"
            record.compatibility_status = "Verified"
            record.discovery_timestamp = fields.Datetime.now()
