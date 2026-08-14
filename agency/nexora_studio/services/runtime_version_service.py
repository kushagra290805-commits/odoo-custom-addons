# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.tools import config

class RuntimeVersionService(models.AbstractModel):
    _name = 'nexora.runtime_version_service'
    _description = 'Enterprise Runtime Version Service'

    @api.model
    def get_runtime_version(self):
        # In a real environment, this might read from __manifest__.py or environment variables.
        # We will use a config fallback or hardcoded default for the platform itself.
        # This eliminates hardcoded versions scattered across plugins and compatibility layers.
        return config.get('nexora_runtime_version', '1.0.0')
