# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class ModelResolutionService(models.AbstractModel):
    _name = 'nexora.model_resolution_service'
    _description = 'Canonical Model Resolution Service'

    @api.model
    def resolve_model(self, job_id, workload='default'):
        """
        Determines the canonical model to use for a given generation job using a deterministic fallback chain:
        1. Job Assignment
        2. Project Assignment
        3. Provider Default (via Provider Registry, workload-aware)
        
        Note: Builder Session assignment is intentionally excluded per current business requirements.
        """
        job = self.env['nexora.generation_job'].browse(job_id)
        if not job.exists():
            _logger.error(f"Cannot resolve model for non-existent job ID: {job_id}")
            return None

        # Step 1: Job-Level Assignment
        if getattr(job, 'assigned_model_id', False) and job.assigned_model_id:
            _logger.info(f"ModelResolutionService [Job {job_id}]: Selected Job Assigned Model -> {job.assigned_model_id.name} ({job.assigned_model_id.model_id})")
            return job.assigned_model_id

        # Step 2: Project-Level Assignment
        if hasattr(job, 'builder_session_id') and job.builder_session_id:
            project = job.builder_session_id.project_id
            if project and getattr(project, 'assigned_model_id', False) and project.assigned_model_id:
                _logger.info(f"ModelResolutionService [Job {job_id}]: Selected Project Assigned Model -> {project.assigned_model_id.name} ({project.assigned_model_id.model_id})")
                return project.assigned_model_id

        # Step 3: Provider Default Model via Registry
        ICPSudo = self.env['ir.config_parameter'].sudo()
        provider_id = ICPSudo.get_param('nexora.active_ai_provider', 'openrouter')
        
        reg = self.env['nexora.provider.registry'].sudo().search([('provider_id', '=', provider_id), ('is_active', '=', True)], limit=1)
        if reg:
            target_model = None
            if workload == 'chat' and reg.default_chat_model_id:
                target_model = reg.default_chat_model_id
            elif workload == 'code' and reg.default_code_model_id:
                target_model = reg.default_code_model_id
            elif workload == 'reasoning' and reg.default_reasoning_model_id:
                target_model = reg.default_reasoning_model_id
            elif workload == 'vision' and reg.default_vision_model_id:
                target_model = reg.default_vision_model_id
            elif workload == 'embedding' and reg.default_embedding_model_id:
                target_model = reg.default_embedding_model_id
            elif reg.default_model_id:
                target_model = reg.default_model_id
                
            if target_model:
                _logger.info(f"ModelResolutionService [Job {job_id}]: Selected Registry Model (Workload: {workload}) -> {target_model.name} ({target_model.model_id})")
                return target_model

        _logger.warning(f"ModelResolutionService [Job {job_id}]: Exhausted all resolution layers. No model resolved.")
        return None
