# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class PipelineService(models.AbstractModel):
    _name = 'nexora.pipeline_service'
    _description = 'Abstract Pipeline Registry Service'

    @api.model
    def _get_stage_registry(self):
        """
        Dynamically builds a registry of stage models based on `_stage_type`.
        Returns a dict mapping stage_type -> model_name.
        """
        registry = {}
        for model_name, model in self.env.registry.items():
            if hasattr(model, '_stage_type') and getattr(model, '_stage_type', None):
                registry[model._stage_type] = model_name
        return registry

    @api.model
    def get_stage_implementation(self, stage_type):
        """
        Returns the registered model name for a given stage_type.
        """
        registry = self._get_stage_registry()
        model_name = registry.get(stage_type)
        if not model_name:
            raise ValueError(f"No stage implementation registered for type: {stage_type}")
        return self.env[model_name]
