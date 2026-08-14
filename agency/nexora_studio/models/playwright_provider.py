# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
import json
import os
import tempfile

_logger = logging.getLogger(__name__)

class PlaywrightProvider(models.AbstractModel):
    _name = 'nexora.provider.playwright'
    _description = 'Canonical Playwright Provider'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Canonical execution interface for Playwright capabilities.
        Executes exclusively through ExecutionSandboxService.
        """
        try:
            sandbox = self.env['nexora.execution_sandbox_service']
        except KeyError:
            return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: Sandbox Runtime unavailable.", execution_ms=(time.time()-start_time)*1000)
            
        action = request.payload.get('action')
        url = request.payload.get('url')
        
        if not action or not url:
            return ProviderExecutionResult(success=False, data=None, error="Playwright requires 'action' and 'url' arguments.", execution_ms=(time.time()-start_time)*1000)

        # Create a temporary python script to run playwright in the sandbox
        # This eliminates raw subprocess usage outside of the canonical sandbox layer.
        script_content = f'''
import sys
import json
import base64
from playwright.sync_api import sync_playwright

def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("{url}")
            
            result = {{}}
            if "{action}" == "snapshot":
                page.wait_for_load_state("networkidle", timeout=10000)
                
                content = page.content()
                title = page.title()
                current_url = page.url
                
                screenshot_bytes = page.screenshot(type="png")
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                result["status"] = "snapshot_taken"
                result["title"] = title
                result["url"] = current_url
                result["content_length"] = len(content)
                result["screenshot_base64_prefix"] = screenshot_b64[:30] + "... (truncated for logging)"
                result["screenshot_captured"] = True
            else:
                result["status"] = "unknown_action"
                
            browser.close()
            print(json.dumps(result))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        fd, script_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(script_content)
                
            # Execute EXCLUSIVELY through ExecutionSandboxService
            cmd = ["python", script_path]
            res = sandbox.execute_local(cmd, timeout=30)
            
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
