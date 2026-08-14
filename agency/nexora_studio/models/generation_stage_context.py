# -*- coding: utf-8 -*-

class GenerationStageContext:
    def __init__(self, builder_session, mode='FULL', targets=None, force=False):
        self.builder_session = builder_session
        self.mode = mode
        self.targets = targets or []
        self.force = force
        self.workspace_path = builder_session.workspace_id.workspace_path if builder_session.workspace_id else None
        
        # Shared state that stages can read/write
        self.state = {
            'template_path': None,
            'generated_files': [],
            'missing_dependencies': [],
            'artifacts': {}
        }
        
    def set(self, key, value):
        self.state[key] = value
        
    def get(self, key, default=None):
        return self.state.get(key, default)
