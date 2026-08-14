# -*- coding: utf-8 -*-
from odoo import models
import re
import os
import logging

_logger = logging.getLogger(__name__)

class VariableInjectionService(models.AbstractModel):
    _name = 'nexora.variable_injection_service'
    _description = 'Variable Injection Engine'

    def inject_variables(self, workspace_path: str, variables: dict, ignore_patterns: list = None):
        """
        Recursively scans the workspace path and injects variables into files.
        Uses a Jinja2-esque syntax: {{ variable.name }}
        """
        if ignore_patterns is None:
            ignore_patterns = ['.git', 'node_modules', 'dist', 'build', '__pycache__']

        success_count = 0
        error_count = 0
        
        for root, dirs, files in os.walk(workspace_path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in ignore_patterns)]
            
            for file in files:
                if any(pattern in file for pattern in ignore_patterns):
                    continue
                    
                file_path = os.path.join(root, file)
                
                # Basic binary check (heuristic)
                try:
                    with open(file_path, 'tr') as check_file:
                        check_file.read(1024)
                except UnicodeDecodeError:
                    continue # Skip binary files
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    new_content = self._process_template(content, variables)
                    
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        success_count += 1
                except Exception as e:
                    _logger.warning(f"Failed to inject variables in {file_path}: {str(e)}")
                    error_count += 1
                    
        return {'success': success_count, 'errors': error_count}

    def _process_template(self, content: str, variables: dict) -> str:
        """
        Processes standard {{ var_name }} replacements.
        Advanced nested resolution could be expanded here.
        """
        def replace_match(match):
            key = match.group(1).strip()
            # Simple dot-notation resolution
            parts = key.split('.')
            val = variables
            try:
                for part in parts:
                    val = val.get(part, '')
                    if val == '':
                        break
                return str(val) if val != '' else match.group(0) # Keep original if not found
            except Exception:
                return match.group(0)

        # Regex for {{ variable }}
        pattern = re.compile(r'\{\{(.*?)\}\}')
        return pattern.sub(replace_match, content)
