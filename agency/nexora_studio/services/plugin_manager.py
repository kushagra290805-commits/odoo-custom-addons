# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class PluginManager(models.AbstractModel):
    _name = 'nexora.plugin_manager'
    _description = 'Enterprise Plugin Package Manager Facade'

    @api.model
    def install_plugin(self, manifest_str):
        validator = self.env['nexora.plugin_manifest_validator']
        descriptor = validator.create_descriptor(manifest_str)
        return self.env['nexora.plugin_installer_service'].install_descriptor(descriptor)

    @api.model
    def enable_plugin(self, plugin):
        self.env['nexora.plugin_lifecycle_service'].enable_plugin(plugin)

    @api.model
    def disable_plugin(self, plugin):
        self.env['nexora.plugin_lifecycle_service'].disable_plugin(plugin)

    @api.model
    def uninstall_plugin(self, plugin):
        self.env['nexora.plugin_lifecycle_service'].uninstall_plugin(plugin)

    @api.model
    def upgrade_plugin(self, capability_code, new_manifest_str):
        validator = self.env['nexora.plugin_manifest_validator']
        new_descriptor = validator.create_descriptor(new_manifest_str)
        return self.env['nexora.plugin_lifecycle_service'].upgrade_plugin(capability_code, new_descriptor)

    @api.model
    def downgrade_plugin(self, capability_code, target_version):
        return self.env['nexora.plugin_lifecycle_service'].downgrade_plugin(capability_code, target_version)

    @api.model
    def reload_plugin(self, plugin):
        self.env['nexora.plugin_lifecycle_service'].reload_plugin(plugin)
