# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ValidationService(models.AbstractModel):
    _name = 'nexora.validation_service'
    _description = 'Abstract Template & Stage Validation Service'

    @api.model
    def validate_templates(self, frontend_ref, backend_ref):
        """
        Validates template references and checks the compatibility matrix inside template_store.
        """
        _logger.info(f"ValidationService: Validating templates frontend=`{frontend_ref}`, backend=`{backend_ref}`")
        if frontend_ref and backend_ref and isinstance(frontend_ref, str) and isinstance(backend_ref, str):
            f_code = frontend_ref.split('/')[-1]
            b_code = backend_ref.split('/')[-1]
            f_rec = self.env['nexora.template_frontend'].search([('subfolder_path', 'ilike', f_code)], limit=1)
            b_rec = self.env['nexora.template_backend'].search([('subfolder_path', 'ilike', b_code)], limit=1)
            if f_rec and b_rec:
                compat = self.env['nexora.template_compatibility'].search([
                    ('frontend_template_id', '=', f_rec.id),
                    ('backend_template_id', '=', b_rec.id)
                ], limit=1)
                if compat and compat.compatibility_level == 'incompatible':
                    raise UserError(_(f"Templates `{f_rec.name}` and `{b_rec.name}` are marked as incompatible: {compat.notes}"))
        return True

    @api.model
    def validate_stage_requirements(self, stage, job):
        """
        Validates stage dependencies and job prerequisites prior to stage execution.
        """
        if not job.target_workspace_path:
            raise UserError(_("Job has no target workspace path assigned for stage validation."))
        self.validate_templates(job.template_frontend_ref, job.template_backend_ref)
        self.env['nexora.generation_service']._append_log(job, 'info', f"Validation requirements verified for stage `{stage.name}`.", stage.id)
        return True

    @api.model
    def validate_stage(self, stage, job):
        return self.validate_stage_requirements(stage, job)
