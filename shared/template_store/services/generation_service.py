# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class GenerationService(models.AbstractModel):
    _name = 'nexora.generation_service'
    _description = 'Abstract Template Generation Service Interface & Orchestrator'

    @api.model
    def create_job(self, pipeline_id, target_workspace_path, frontend_ref=False, backend_ref=False, variables=None):
        """
        Creates and initializes a new generation job from a pipeline and variable dictionary.
        """
        pipeline = self.env['nexora.generation_pipeline'].browse(pipeline_id)
        if not pipeline.exists():
            raise UserError(_("Specified generation pipeline does not exist."))
            
        vals = {
            'name': f"Generate: {pipeline.name}",
            'pipeline_id': pipeline.id,
            'generator_type_id': pipeline.generator_type_id.id if pipeline.generator_type_id else False,
            'target_workspace_path': target_workspace_path,
            'template_frontend_ref': frontend_ref,
            'template_backend_ref': backend_ref,
            'status': 'draft',
        }

        # Resolve Many2one pointers from registry if exact subfolder paths match
        if frontend_ref and isinstance(frontend_ref, str) and frontend_ref.startswith('template_store://'):
            subpath = frontend_ref.replace('template_store://', '')
            f_rec = self.env['nexora.template_frontend'].search([('subfolder_path', '=', subpath)], limit=1)
            if f_rec:
                vals['frontend_template_id'] = f_rec.id

        if backend_ref and isinstance(backend_ref, str) and backend_ref.startswith('template_store://'):
            subpath = backend_ref.replace('template_store://', '')
            b_rec = self.env['nexora.template_backend'].search([('subfolder_path', '=', subpath)], limit=1)
            if b_rec:
                vals['backend_template_id'] = b_rec.id

        job = self.env['nexora.generation_job'].create(vals)
        
        if variables and isinstance(variables, dict):
            for k, v in variables.items():
                self.env['nexora.generation_variable'].create({
                    'job_id': job.id,
                    'key': str(k),
                    'value': str(v),
                    'variable_type': 'string'
                })
        _logger.info(f"GenerationService: Created job {job.job_uuid} (`{job.name}`) for target path `{target_workspace_path}`.")
        return job

    @api.model
    def execute_job(self, job):
        """
        Orchestrates running all stages defined in the job's pipeline.
        Establishes the execution state machine and delegates to PipelineService.
        """
        if not job or not job.exists():
            raise UserError(_("Invalid generation job record."))
        
        _logger.info(f"GenerationService: Initiating execution for job {job.job_uuid} (`{job.name}`).")
        job.write({
            'status': 'validating',
            'start_time': fields.Datetime.now(),
            'error_message': False
        })
        self._append_log(job, 'info', "Job execution initiated across generation pipeline.")
        
        try:
            self.env['nexora.pipeline_service'].run_pipeline(job)
        except Exception as e:
            _logger.error(f"GenerationService: Job {job.job_uuid} failed with error: {e}")
            job.write({
                'status': 'failed',
                'end_time': fields.Datetime.now(),
                'error_message': str(e)
            })
            self._append_log(job, 'error', f"Job execution failed: {e}")
            raise

    @api.model
    def rollback_job(self, job):
        """
        Orchestrates transactional rollback of any completed stages in the job.
        """
        if not job or not job.exists():
            raise UserError(_("Invalid generation job record for rollback."))
            
        _logger.info(f"GenerationService: Initiating rollback for job {job.job_uuid}.")
        self._append_log(job, 'warning', "Initiating rollback of generation job stages.")
        try:
            self.env['nexora.pipeline_service'].rollback_pipeline(job)
            job.write({
                'status': 'rolled_back',
                'end_time': fields.Datetime.now()
            })
            self._append_log(job, 'info', "Job stages successfully rolled back.")
        except Exception as e:
            _logger.error(f"GenerationService: Rollback failed for job {job.job_uuid}: {e}")
            self._append_log(job, 'error', f"Rollback encountered error: {e}")
            raise

    @api.model
    def execute_stage_cloning(self, stage, job):
        """
        Handler for 'cloning' stage type.
        Copies the template directories into the target workspace using the Filesystem Service.
        """
        fs = self.env['nexora.filesystem_service']
        self._append_log(job, 'info', f"Executing stage `{stage.name}` (Code: {stage.code}, Type: {stage.stage_type}).", stage.id)
        
        target_path = job.target_workspace_path
        created_paths = []
        
        if stage.code == 'clone_frontend' and job.frontend_template_id:
            src = job.frontend_template_id.subfolder_path
            dst = target_path + '/frontend'
            if fs.file_exists(src):
                fs.copy_tree(src, dst)
                self._append_log(job, 'info', f"Copied frontend template from `{src}` to `{dst}`.", stage.id)
                created_paths.append(dst)
            else:
                self._append_log(job, 'warning', f"Frontend template source `{src}` does not exist.", stage.id)
                
        elif stage.code == 'clone_backend' and job.backend_template_id:
            src = job.backend_template_id.subfolder_path
            dst = target_path + '/backend'
            if fs.file_exists(src):
                fs.copy_tree(src, dst)
                self._append_log(job, 'info', f"Copied backend template from `{src}` to `{dst}`.", stage.id)
                created_paths.append(dst)
            else:
                self._append_log(job, 'warning', f"Backend template source `{src}` does not exist.", stage.id)
                
        return {'copied_paths': created_paths}

    @api.model
    def _append_log(self, job, level, message, stage_id=False):
        try:
            self.env['nexora.generation_log'].create({
                'job_id': job.id,
                'stage_id': stage_id or False,
                'level': level,
                'message': message
            })
        except Exception as e:
            _logger.warning(f"GenerationService: Could not append log: {e}")
