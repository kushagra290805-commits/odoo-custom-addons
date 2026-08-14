# -*- coding: utf-8 -*-
from odoo import models, api
import re

class SemanticVersionService(models.AbstractModel):
    _name = 'nexora.semantic_version_service'
    _description = 'Enterprise Semantic Version Service'

    @api.model
    def parse_version(self, version_str):
        if not version_str:
            raise ValueError("Version string cannot be empty")
        
        match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?$', str(version_str))
        if not match:
            raise ValueError(f"Invalid semantic version format: {version_str}. Expected X.Y or X.Y.Z")
        
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else 0
        
        return (major, minor, patch)

    @api.model
    def compare_versions(self, v1_str, v2_str):
        """ Returns 1 if v1 > v2, -1 if v1 < v2, 0 if v1 == v2 """
        v1 = self.parse_version(v1_str)
        v2 = self.parse_version(v2_str)
        
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1
        return 0

    @api.model
    def validate_runtime_bounds(self, min_version, max_version):
        runtime_version = self.env['nexora.runtime_version_service'].get_runtime_version()
        
        if min_version:
            if self.compare_versions(runtime_version, min_version) < 0:
                raise ValueError(f"Runtime version {runtime_version} does not meet minimum requirement {min_version}")
                
        if max_version:
            if self.compare_versions(runtime_version, max_version) > 0:
                raise ValueError(f"Runtime version {runtime_version} exceeds maximum allowed {max_version}")
