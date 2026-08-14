# -*- coding: utf-8 -*-
from odoo import models, fields

class ToolResult:
    def __init__(self, success=True, stdout="", stderr="", warnings=None, errors=None, metadata=None, execution_time=0.0):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.warnings = warnings or []
        self.errors = errors or []
        self.metadata = metadata or {}
        self.execution_time = execution_time

    def to_dict(self):
        return {
            'success': self.success,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'warnings': self.warnings,
            'errors': self.errors,
            'metadata': self.metadata,
            'execution_time': self.execution_time
        }
