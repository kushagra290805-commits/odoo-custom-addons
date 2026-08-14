# -*- coding: utf-8 -*-
import logging
import os
from odoo import models, api, _

_logger = logging.getLogger(__name__)

class MergeService(models.AbstractModel):
    _name = 'nexora.merge_service'
    _description = 'Abstract Frontend & Backend Template Merge Service'

    @api.model
    def merge_templates(self, frontend_path, backend_path, target_path, strategy='overwrite'):
        """
        Abstract contract for merging frontend and backend directory trees into target_path.
        """
        _logger.info(f"MergeService: Merging `{frontend_path}` and `{backend_path}` into `{target_path}` using strategy `{strategy}`.")
        return True

    @api.model
    def merge_templates_interface(self, job, stage):
        """
        Orchestration handler called by pipeline execution for stage_type='merge'.
        """
        f_name = job.frontend_template_id.name if job.frontend_template_id else (job.template_frontend_ref or 'Frontend')
        b_name = job.backend_template_id.name if job.backend_template_id else (job.template_backend_ref or 'Backend')
        
        fs = self.env['nexora.filesystem_service']
        target_path = job.target_workspace_path
        
        frontend_path = target_path + '/frontend'
        backend_path = target_path + '/backend'
        shared_path = target_path + '/shared'
        
        conflicts = []
        merged = []
        
        # Example logic: if both frontend and backend provide a shared model, merge them into /shared.
        # For simplicity, we just detect files with the same name in shared regions.
        if fs.file_exists(frontend_path + '/shared') and fs.file_exists(backend_path + '/shared'):
            for root, dirs, files in fs.walk(frontend_path + '/shared'):
                for f in files:
                    rel_path = root.replace(frontend_path + '/shared', '').lstrip('/\\')
                    dest = os.path.join(shared_path, rel_path, f)
                    src1 = os.path.join(root, f)
                    src2 = os.path.join(backend_path + '/shared', rel_path, f)
                    
                    fs.create_directory(os.path.dirname(dest))
                    
                    if fs.file_exists(src2):
                        conflicts.append(f)
                        # Overwrite policy: backend wins
                        content = fs.read_file(src2, is_binary=False)
                        fs.write_file(dest, content, is_binary=False)
                    else:
                        content = fs.read_file(src1, is_binary=False)
                        fs.write_file(dest, content, is_binary=False)
                    merged.append(f)

        self.env['nexora.generation_service']._append_log(job, 'info', f"Merge interface: combined `{f_name}` and `{b_name}`. Conflicts resolved: {len(conflicts)}. Total merged: {len(merged)}", stage.id)
        return {'conflicts': conflicts, 'merged': merged}

    @api.model
    def execute_stage_merge(self, stage, job):
        return self.merge_templates_interface(job, stage)
