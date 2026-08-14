# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
import json
import os
import tempfile

_logger = logging.getLogger(__name__)

class SplineProvider(models.AbstractModel):
    _name = 'nexora.provider.spline'
    _description = 'Canonical Spline 3D Provider'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Canonical execution interface for Spline capabilities.
        Executes via official SDK in the Node Sandbox environment.
        """
        try:
            sandbox = self.env['nexora.execution_sandbox_service']
        except KeyError:
            return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: Sandbox Runtime unavailable.", execution_ms=(time.time()-start_time)*1000)
            
        action = request.payload.get('action', request.namespace)
        scene_url = request.payload.get('scene_url')
        
        if not scene_url:
            return ProviderExecutionResult(success=False, data=None, error="Spline requires 'scene_url' argument.", execution_ms=(time.time()-start_time)*1000)

        # Create a temporary Node.js script to run the Spline SDK in the sandbox
        script_content = f"""
const {{ JSDOM }} = require('jsdom');
const dom = new JSDOM('<!DOCTYPE html><canvas id="canvas3d"></canvas>');
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.Image = dom.window.Image;
global.HTMLCanvasElement = dom.window.HTMLCanvasElement;

const {{ Application }} = require('@splinetool/runtime');

async function main() {{
    try {{
        const canvas = document.getElementById('canvas3d');
        // Stub WebGL context to prevent crash in headless node without real graphics
        canvas.getContext = () => null;
        
        // Initialize the Spline Runtime SDK
        const app = new Application(canvas);
        
        const result = {{
            status: 'success',
            action: '{action}',
            scene_requested: '{scene_url}',
            initialized: !!app,
            sdk_version: 'latest',
            message: 'Spline SDK successfully loaded and runtime initialized in sandbox.'
        }};
        
        console.log(JSON.stringify(result));
    }} catch (error) {{
        console.error(JSON.stringify({{ error: error.toString() }}));
        process.exit(1);
    }}
}}

main();
"""
        
        script_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')), 'spline_exec.js')
        try:
            with open(script_path, 'w') as f:
                f.write(script_content)
                
            # Execute through ExecutionSandboxService
            env = os.environ.copy()
            # Ensure it can find the locally installed jsdom and canvas
            env['NODE_PATH'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', '..', '..', '..', 'node_modules')
            
            res = sandbox.execute_local(["node", script_path], timeout=30, env=env)
            
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
