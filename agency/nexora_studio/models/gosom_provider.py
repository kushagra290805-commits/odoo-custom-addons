# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
import json
import os
import tempfile
import subprocess

_logger = logging.getLogger(__name__)

class GosomProvider(models.AbstractModel):
    _name = 'nexora.provider.gosom'
    _description = 'Canonical Gosom Maps Scraper Provider'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Canonical execution interface for Gosom capabilities.
        Executes via official downloaded binary in the Sandbox environment.
        """
        try:
            sandbox = self.env['nexora.execution_sandbox_service']
        except KeyError:
            return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: Sandbox Runtime unavailable.", execution_ms=(time.time()-start_time)*1000)
            
        query = request.payload.get('query', 'restaurants near me')
        depth = request.payload.get('depth', 1)
        
        # Path to the downloaded binary
        binary_path = os.path.join('d:\\', 'ODOO', 'custom-addons', 'agency', 'nexora_studio', 'plugins', 'gosom', 'google-maps-scraper.exe')
        
        if not os.path.exists(binary_path):
             return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: Binary not found at {binary_path}.", execution_ms=(time.time()-start_time)*1000)

        # Create a temporary python script to run the binary in the sandbox safely
        script_content = f"""
import subprocess
import json
import sys
import tempfile
import os

def main():
    try:
        # Create input file for gosom
        fd, input_file = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, 'w') as f:
            f.write("{query}")
            
        cmd = [
            r"{binary_path}", 
            "-input", input_file, 
            "-depth", str({depth}), 
            "-c", "1", 
            "-json"
        ]
        
        # We run the command
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=120)
        
        out = {{
            "status": "success",
            "query_executed": "{query}",
            "depth": {depth},
            "stderr_log": result.stderr.strip(),
            "results": []
        }}
        
        # Parse stdout JSON
        if result.stdout.strip():
            for line in result.stdout.strip().split('\\n'):
                try:
                    out["results"].append(json.loads(line))
                except Exception:
                    pass

        # Cleanup input file
        if os.path.exists(input_file):
            os.remove(input_file)
            
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))
        sys.exit(1)

main()
"""
        # Fixing json.stringify to json.dumps
        script_content = script_content.replace('json.stringify', 'json.dumps')

        fd, script_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(script_content)
                
            # Execute EXCLUSIVELY through ExecutionSandboxService
            cmd = ["python", script_path]
            res = sandbox.execute_local(cmd, timeout=120)
            
            if res.get('success'):
                try:
                    result = json.loads(res.get('stdout', '{}'))
                except:
                    result = {"output": res.get('stdout')}
                return ProviderExecutionResult(success=True, data=result, error=None, execution_ms=(time.time()-start_time)*1000)
            else:
                raise Exception(res.get('stderr') or res.get('error') or "Sandbox execution failed.")
                
        except Exception as e:
            _logger.error(f"{self._description} execution error: {e}")
            return ProviderExecutionResult(success=False, data=None, error=f"{self._description} error: {str(e)}", execution_ms=(time.time()-start_time)*1000)
        finally:
            if 'script_path' in locals() and os.path.exists(script_path):
                os.remove(script_path)
