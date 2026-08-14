from odoo import models, api, fields, _
import json

class BuilderSession(models.Model):
    _inherit = 'nexora.builder_session'

    mcp_healthy_tools = fields.Text(string='Healthy Tools', compute='_compute_mcp_metadata', store=False)
    mcp_failed_tools = fields.Text(string='Failed Tools', compute='_compute_mcp_metadata', store=False)
    mcp_last_tool = fields.Char(string='Last Tool Executed', compute='_compute_mcp_metadata', store=False)
    mcp_last_execution = fields.Char(string='Last Execution', compute='_compute_mcp_metadata', store=False)
    mcp_runtime_health = fields.Char(string='Runtime Health', compute='_compute_mcp_metadata', store=False)

    mcp_capability_ids = fields.Many2many('nexora.capability_registry', compute='_compute_mcp_metadata', string='Capabilities')

    # Enterprise Platform Status Fields
    plugin_count = fields.Integer(string="Total Plugins", compute="_compute_plugin_stats")
    enabled_plugins_count = fields.Integer(string="Enabled Plugins", compute="_compute_plugin_stats")
    disabled_plugins_count = fields.Integer(string="Disabled Plugins", compute="_compute_plugin_stats")
    dependency_status = fields.Char(string="Dependency Status", compute="_compute_plugin_stats")
    cache_status = fields.Char(string="Cache Status", compute="_compute_plugin_stats")
    compatibility_status = fields.Char(string="Compatibility Status", compute="_compute_plugin_stats")
    discovery_timestamp = fields.Datetime(string="Last Discovery", compute="_compute_plugin_stats")

    def _compute_plugin_stats(self):
        health_svc = self.env['nexora.builder_health_service']
        snapshot = health_svc.generate_snapshot()
        
        for record in self:
            record.plugin_count = snapshot.plugin_count
            record.enabled_plugins_count = snapshot.enabled_plugins
            record.disabled_plugins_count = snapshot.disabled_plugins
            record.dependency_status = snapshot.dependency_status
            record.cache_status = snapshot.cache_status
            record.compatibility_status = snapshot.compatibility_status
            record.discovery_timestamp = snapshot.discovery_timestamp

    def _compute_mcp_metadata(self):
        super()._compute_mcp_metadata()
        for session in self:
            mcp_runtime = self.env['nexora.runtime'].search([
                ('builder_session_id', '=', session.id),
                ('runtime_type', '=', 'mcp')
            ], limit=1)
            
            meta = {}
            if mcp_runtime:
                try:
                    meta = json.loads(mcp_runtime.metadata_json or '{}')
                except Exception:
                    pass
            
            session.mcp_healthy_tools = str(meta.get('healthy_tools', []))
            session.mcp_failed_tools = str(meta.get('failed_tools', []))
            session.mcp_last_tool = meta.get('last_tool', 'None')
            session.mcp_last_execution = meta.get('last_execution_status', 'None')
            session.mcp_runtime_health = mcp_runtime.health if mcp_runtime else 'unknown'
            
            session.mcp_capability_ids = self.env['nexora.capability_registry'].search([])

