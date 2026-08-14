# -*- coding: utf-8 -*-
"""
Test AI Provider Adapter - Deterministic adapter for stress testing.
"""
from odoo import models
import json
import logging
import time
import os

_logger = logging.getLogger(__name__)


class TestAIAdapter(models.AbstractModel):
    _name = 'nexora.ai_adapter.test'
    _inherit = 'nexora.ai_adapter_base'
    _description = 'Test AI Provider Adapter'

    def get_provider_name(self):
        return 'test'

    def get_display_name(self):
        return 'Deterministic Test Provider'

    def get_provider_metadata(self):
        return {
            'name': 'Deterministic Test Provider',
            'key': 'test',
            'required_config': [],
            'default_base_url': '',
            'supports_catalog_sync': False,
        }

    def is_available(self, provider_input=None):
        return True
        
    def run_diagnostics(self, provider_input):
        return {'connectivity_state': 'reachable', 'latency_ms': 5}
        
    def authenticate(self, provider_input):
        return {'authentication_state': 'authenticated'}
        
    def fetch_catalog(self, provider_input):
        return []

    def chat_completion(self, messages, credentials=None, model=None, temperature=0.7,
                        max_tokens=4096, json_mode=False, timeout=120,
                        retries=2):
        start_time = time.time()
        
        # Simulate network latency (small configurable jitter for realism if needed, 
        # but the prompt asks for deterministic behavior, so we use a fixed short delay).
        time.sleep(0.1)
        
        prompt = ""
        if messages:
            prompt = messages[-1].get('content', '')

        response_content = ""

        if "sim_timeout" in prompt:
            return {'error': 'Mock Provider Timeout', 'status': 'failed'}
            
        if "sim_validation_failure" in prompt:
            if json_mode:
                response_content = '{"malformed": true'
            else:
                response_content = 'BAD_OUTPUT'
        
        elif json_mode:
            if 'information_architecture' in prompt or 'Generate Project Blueprint' in prompt:
                payload = {
                    "information_architecture": "Test IA",
                    "navigation_structure": "Test Nav",
                    "pages_json": [{"name": "Home", "path": "/", "description": "Home Page"}],
                    "component_hierarchy_json": [{"name": "Header", "type": "UI"}],
                    "design_system_json": {"colors": {}},
                    "integrations_json": [],
                    "seo_requirements": "Test SEO",
                    "performance_goals": "Test Perf"
                }
                response_content = json.dumps(payload)
            elif 'tasks' in prompt or 'Execution Plan' in prompt:
                payload = {
                    "stages": [
                        {
                            "name": "Test Stage 1",
                            "sequence": 10,
                            "tasks": [
                                {
                                    "name": "Setup Repository",
                                    "objective": "Initialize the Git repository for the project",
                                    "required_capability": "mcp.tool.git",
                                    "inputs": {"instruction": "Initialize empty git repo"},
                                    "outputs": {"status": "initialized"},
                                    "depends_on": []
                                },
                                {
                                    "name": "Create Homepage",
                                    "objective": "Scaffold the index.html file",
                                    "required_capability": "mcp.tool.write_to_file",
                                    "inputs": {"file_path": "index.html", "content": "<html></html>"},
                                    "outputs": {"file_path": "index.html"},
                                    "depends_on": ["Setup Repository"]
                                }
                            ]
                        }
                    ]
                }
                response_content = json.dumps(payload)
            else:
                response_content = json.dumps({"status": "success", "mocked": True})
        else:
            response_content = "Deterministic Test Response"

        execution_time = time.time() - start_time
        
        return {
            'provider': self.get_provider_name(),
            'model': model or 'test-model',
            'prompt': prompt,
            'response': response_content,
            'token_usage': 100,
            'execution_time': execution_time,
            'error': None,
        }
