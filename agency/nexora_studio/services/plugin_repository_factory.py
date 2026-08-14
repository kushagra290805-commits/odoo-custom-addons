# -*- coding: utf-8 -*-
import os
from odoo.tools import config
from .plugin_repository import AbstractPluginRepository, LocalPluginRepository

class PluginRepositoryFactory:
    _instance = None
    
    @classmethod
    def get_repository(cls) -> AbstractPluginRepository:
        if cls._instance is None:
            repo_type = config.get('nexora_plugin_repository', 'local')
            if repo_type == 'local':
                # Base dir of nexora_studio plugins/core
                base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'core')
                cls._instance = LocalPluginRepository(base_dir)
            else:
                raise ValueError(f"Unsupported repository type: {repo_type}")
        return cls._instance
