# -*- coding: utf-8 -*-

class GenerationStageResult:
    SUCCESS = 'success'
    FAILURE = 'failure'
    SKIPPED = 'skipped'

    def __init__(self, status, message="", data=None):
        self.status = status
        self.message = message
        self.data = data or {}
        
    @property
    def is_success(self):
        return self.status == self.SUCCESS
        
    @property
    def is_skipped(self):
        return self.status == self.SKIPPED
        
    def to_dict(self):
        return {
            'status': self.status,
            'message': self.message,
            'data': self.data
        }
