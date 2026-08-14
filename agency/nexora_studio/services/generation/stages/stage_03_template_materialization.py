# -*- coding: utf-8 -*-
from odoo import models
import os
import shutil
import hashlib
import json
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore

class TemplateMaterializationStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.template_materialization'
    _inherit = 'nexora.ai_generation_stage'

    _description = 'Stage 03: Template Materialization'

    def validate(self, context):
        if not context.get('template_path'):
            raise ValueError("Template path is missing from context. Did Stage 02 fail?")
        return True

    def execute(self, context):
        template_path = context.get('template_path')
        if not template_path:
            return GenerationStageResult(GenerationStageResult.FAILURE, "Template path not found in context.")
            
        workspace_path = context.workspace_path
        target_src = os.path.join(workspace_path, 'src')
        
        if not os.path.exists(template_path):
            return GenerationStageResult(GenerationStageResult.FAILURE, f"Resolved template path does not exist: {template_path}")
                
        # Validate template metadata
        meta_path = os.path.join(template_path, 'template.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                context.set('template_metadata', meta)
            except Exception as e:
                return GenerationStageResult(GenerationStageResult.FAILURE, f"Invalid template metadata: {str(e)}")

        ignore_rules = ['.git', 'node_modules', '__pycache__', '.nexora_ignore']
        
        def ignore_func(dir_name, files):
            return [f for f in files if any(rule in f for rule in ignore_rules)]
            
        try:
            # Recursive materialization respecting symlinks
            shutil.copytree(template_path, target_src, symlinks=True, ignore=ignore_func, dirs_exist_ok=True)
            
            # Record copied files for rollback
            copied_files = []
            for root, dirs, files in os.walk(target_src):
                for file in files:
                    copied_files.append(os.path.join(root, file))
                    
            context.set('materialized_files', copied_files)
            
        except Exception as e:
            return GenerationStageResult(GenerationStageResult.FAILURE, f"Materialization failed: {str(e)}")
            
        return GenerationStageResult(GenerationStageResult.SUCCESS, "Template materialized successfully.")

    def rollback(self, context, execution_data):
        files = context.get('materialized_files', [])
        for file in files:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except OSError:
                    pass
