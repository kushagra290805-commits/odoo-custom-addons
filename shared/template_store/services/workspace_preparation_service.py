# -*- coding: utf-8 -*-
import logging
import os
from odoo import models, api, _

_logger = logging.getLogger(__name__)

class WorkspacePreparationService(models.AbstractModel):
    _name = 'nexora.workspace_preparation_service'
    _description = 'Workspace Preparation & Finalization Service'

    @api.model
    def prepare_directory(self, target_path, job=False, stage=False):
        """
        Creates the workspace and the required standard folder structure.
        """
        _logger.info(f"WorkspacePreparationService: Preparing workspace directory at `{target_path}`.")
        fs = self.env['nexora.filesystem_service']
        
        # Create standard layout
        folders = [
            '',
            'frontend',
            'backend',
            'shared',
            'deployment',
            'documentation'
        ]
        
        created_paths = []
        for folder in folders:
            folder_path = os.path.join(target_path, folder)
            if fs.create_directory(folder_path):
                created_paths.append(folder_path)
            
        if job and stage:
            self.env['nexora.generation_service']._append_log(job, 'info', f"Prepared standard workspace layout in `{target_path}`.", stage.id)
            
        return created_paths

    @api.model
    def finalize_workspace(self, job, stage=False):
        """
        Finalizing and sealing the generated workspace for Builder Session attachment.
        """
        _logger.info(f"WorkspacePreparationService: Finalizing workspace generation for job {job.job_uuid}.")
        if stage:
            self.env['nexora.generation_service']._append_log(job, 'info', "Workspace generated successfully and sealed.", stage.id)
        return True

    @api.model
    def prepare_stage(self, stage, job):
        created_paths = self.prepare_directory(job.target_workspace_path, job, stage)
        return {'created_directories': created_paths}

    @api.model
    def finalize_stage(self, stage, job):
        return self.finalize_workspace(job, stage)
