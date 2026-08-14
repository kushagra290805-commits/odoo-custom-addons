# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time

class PlaceholderProvider(models.AbstractModel):
    _name = 'nexora.provider.placeholder'
    _description = 'Canonical Placeholder Provider for Reviewers'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Gracefully returns a structured response indicating the capability is not installed,
        allowing the ReviewEngine to continue without failing.
        """
        return [{"severity": "info", "message": "Capability Not Installed"}]
