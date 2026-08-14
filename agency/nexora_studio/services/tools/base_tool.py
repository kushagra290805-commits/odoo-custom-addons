# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult


class BaseTool(models.AbstractModel):
    _name = 'nexora.tool.base'
    _description = 'Base Abstract Tool Contract'

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        context = request.context
        kwargs = request.payload
        raise NotImplementedError("Tools must implement execute()")

    def validate(self, context, **kwargs):
        raise NotImplementedError("Tools must implement validate()")

    def health(self):
        raise NotImplementedError("Tools must implement health()")

    def cleanup(self, context, **kwargs):
        pass

    def rollback(self, context, **kwargs):
        pass

    def metadata(self):
        """
        Returns standardized capability metadata.
        Must conform to Step 8 Enterprise Metadata schema.
        """
        raise NotImplementedError("Tools must return metadata()")
