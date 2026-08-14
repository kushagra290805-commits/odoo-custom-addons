# -*- coding: utf-8 -*-
import logging
import json
import os
from odoo import models, api, _

_logger = logging.getLogger(__name__)

class VariableEngine(models.AbstractModel):
    _name = 'nexora.variable_engine'
    _description = 'Abstract Variable Substitution & Configuration Engine'

    @api.model
    def substitute_variables(self, text, variable_dict):
        """
        Replaces placeholders e.g. {{KEY}} or ${KEY} with string values from variable_dict.
        """
        if not text or not variable_dict:
            return text
        result = text
        for key, value in variable_dict.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
            result = result.replace(f"${{{key}}}", str(value))
        return result

    @api.model
    def resolve_job_variables(self, job):
        """
        Converts job variable records into a clean python dictionary,
        merging default specifications from linked template metadata where applicable.
        """
        var_map = {}
        # Load defaults from template metadata if present
        if job.frontend_template_id and job.frontend_template_id.metadata_id:
            try:
                data = json.loads(job.frontend_template_id.metadata_id.raw_json or '{}')
                if 'defaults' in data and isinstance(data['defaults'], dict):
                    var_map.update(data['defaults'])
            except Exception:
                pass
        if job.backend_template_id and job.backend_template_id.metadata_id:
            try:
                data = json.loads(job.backend_template_id.metadata_id.raw_json or '{}')
                if 'defaults' in data and isinstance(data['defaults'], dict):
                    var_map.update(data['defaults'])
            except Exception:
                pass

        # Override with job-specific variable definitions
        for var in job.variable_ids:
            var_map[var.key] = var.value or ''
        return var_map

    @api.model
    def process_directory(self, target_path, variable_dict):
        """
        Recursively scan all copied text-based files (JSON, YAML, HTML, CSS, JS, TS, Python, Markdown, ENV)
        and apply variable substitutions. Binary files are ignored based on extension.
        """
        fs = self.env['nexora.filesystem_service']
        if not fs.file_exists(target_path):
            return
            
        binary_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.webm', '.pyc'}
        modified_files = []
        
        for root, dirs, files in fs.walk(target_path):
            for file_name in files:
                ext = file_name[file_name.rfind('.'):].lower() if '.' in file_name else ''
                if ext in binary_extensions:
                    continue
                    
                file_path = os.path.join(root, file_name)
                try:
                    content = fs.read_file(file_path, is_binary=False)
                    new_content = self.substitute_variables(content, variable_dict)
                    if new_content != content:
                        fs.write_file(file_path, new_content, is_binary=False)
                        modified_files.append(file_path)
                except UnicodeDecodeError:
                    # Fallback if it's binary without extension
                    pass
                except Exception as e:
                    _logger.warning(f"VariableEngine: Failed to process file {file_path}: {e}")
                    
        return modified_files

    @api.model
    def execute_stage_variables(self, stage, job):
        """
        Handler for variable replacement stages.
        """
        var_map = self.resolve_job_variables(job)
        modified = []
        if stage.stage_type == 'variable':
            modified = self.process_directory(job.target_workspace_path, var_map) or []
            count = len(modified)
            self.env['nexora.generation_service']._append_log(job, 'info', f"Variable substitution interface: replaced variables in {count} files.", stage.id)
        elif stage.stage_type == 'config':
            self.env['nexora.generation_service']._append_log(job, 'info', f"Configuration generation interface: preparing environment configuration based on variables.", stage.id)
        return {'modified_files': modified}
