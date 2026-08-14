# -*- coding: utf-8 -*-
import logging

class ToolContext:
    def __init__(self, builder_session, workspace, runtime, variables=None, metadata=None, environment=None, logger=None):
        self.builder_session = builder_session
        self.workspace = workspace
        self.runtime = runtime
        self.variables = variables or {}
        self.metadata = metadata or {}
        self.environment = environment or {}
        self.logger = logger or logging.getLogger('nexora.tool')
