# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

class RuntimePlugin(models.AbstractModel):
    _name = 'nexora.runtime_plugin'
    _description = 'Runtime Plugin Base Class'

    @api.model
    def plugin_manifest(self):
        """
        Returns the plugin manifest metadata dictionary.
        Must be overridden by subclasses.
        """
        raise NotImplementedError("Plugins must implement plugin_manifest")

    @api.model
    def start_runtime_instance(self, runtime):
        raise NotImplementedError("Plugins must implement start_runtime_instance")

    @api.model
    def stop_runtime_instance(self, runtime):
        raise NotImplementedError("Plugins must implement stop_runtime_instance")

    @api.model
    def restart_runtime_instance(self, runtime):
        raise NotImplementedError("Plugins must implement restart_runtime_instance")

    @api.model
    def refresh_runtime(self, runtime):
        raise NotImplementedError("Plugins must implement refresh_runtime")

    @api.model
    def check_health(self, runtime):
        raise NotImplementedError("Plugins must implement check_health")

