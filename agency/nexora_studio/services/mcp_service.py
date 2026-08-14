# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import logging
import json
import traceback

_logger = logging.getLogger(__name__)

class MCPService(models.AbstractModel):
    _name = 'nexora.mcp_service'
    _inherit = 'nexora.runtime_plugin'
    _description = 'MCP Runtime Service'

    @api.model
    def plugin_manifest(self):
        return {
            'runtime_type': 'mcp',
            'version': '1.0.0',
            'provider': 'nexora',
            'priority': 40,
            'dependencies': ['workspace', 'git', 'ide'],
            'supports_health_checks': True,
            'restart_policy': 'always',
            'description': 'Model Context Protocol (MCP) Runtime. Wraps local tools.',
            'name': 'MCP Runtime',
            'capabilities': [
                "mcp.server",
                "mcp.tools"
            ]
        }

    @api.model
    def start_runtime_instance(self, runtime):
        session = runtime.builder_session_id
        
        # Discover capabilities via capability_registry cache
        capabilities = self.env['nexora.capability_cache_service'].get_sorted_capabilities()
        
        # Validate them
        healthy_caps = []
        failed_caps = []
        registered_tools = []
        for cap in capabilities:
            self.env['nexora.builder_session_service']._emit_event(
                session, 'capability.discovered', f"Discovered capability {cap.capability_code} v{cap.version}", runtime=runtime
            )
            is_valid = cap.validate_capability()
            if is_valid:
                cap.check_health()
                if cap.health_status == 'healthy':
                    healthy_caps.append(cap.capability_name)
                    if cap.capability_type == 'tool':
                        registered_tools.append(cap.capability_name)
                    self.env['nexora.builder_session_service']._emit_event(
                        session, 'capability.loaded', f"Loaded capability {cap.capability_code} v{cap.version}", runtime=runtime
                    )
                else:
                    failed_caps.append(cap.capability_name)
            else:
                failed_caps.append(cap.capability_name)
                self.env['nexora.builder_session_service']._emit_event(
                    session, 'capability.validation_failed', f"Validation failed for capability {cap.capability_code} v{cap.version}", runtime=runtime
                )
        
        metadata = {
            'status': 'online',
            'registered_tools': registered_tools,
            'healthy_tools': healthy_caps,
            'failed_tools': failed_caps
        }
        
        runtime.endpoint = "mcp://local"
        runtime.metadata_json = json.dumps(metadata)
        runtime.health = 'healthy'
        
        self.env['nexora.builder_session_service']._emit_event(
            session, 'mcp.started', f"MCP Runtime initialized with {len(registered_tools)} tools and {len(capabilities)} capabilities.", runtime=runtime
        )
        self.env['nexora.builder_session_service']._emit_event(
            session, 'mcp.ready', "MCP Runtime ready to accept execution requests.", runtime=runtime
        )

    @api.model
    def stop_runtime_instance(self, runtime):
        session = runtime.builder_session_id
        runtime.health = 'unknown'
        runtime.endpoint = ''
        self.env['nexora.builder_session_service']._emit_event(
            session, 'mcp.stopped', "MCP Runtime stopped.", runtime=runtime
        )

    @api.model
    def restart_runtime_instance(self, runtime):
        self.stop_runtime_instance(runtime)
        self.start_runtime_instance(runtime)

    @api.model
    def refresh_runtime(self, runtime):
        if runtime.health == 'failed':
            return
            
        capabilities = self.env['nexora.capability_registry'].search([('enabled', '=', True)])
        metadata = json.loads(runtime.metadata_json) if runtime.metadata_json else {}
        
        healthy_caps = []
        failed_caps = []
        registered_tools = []
        for cap in capabilities:
            try:
                cap.check_health()
                if cap.health_status == 'healthy':
                    healthy_caps.append(cap.capability_name)
                    if cap.capability_type == 'tool':
                        registered_tools.append(cap.capability_name)
                else:
                    failed_caps.append(cap.capability_name)
            except Exception:
                failed_caps.append(cap.capability_name)
                
        metadata['healthy_tools'] = healthy_caps
        metadata['failed_tools'] = failed_caps
        metadata['registered_tools'] = registered_tools
        runtime.metadata_json = json.dumps(metadata)

    @api.model
    def recover_runtime_instance(self, runtime):
        session = runtime.builder_session_id
        self.env['nexora.builder_session_service']._emit_event(
            session, 'mcp.recovered', "MCP Runtime recovered and re-initialized.", runtime=runtime
        )
        self.restart_runtime_instance(runtime)
        runtime.status = 'running'

    @api.model
    def check_health(self, runtime):
        self.refresh_runtime(runtime)
        
    @api.model
    def execute_tool_safely(self, runtime, tool_id, context, **kwargs):
        """
        Executes a tool with full error isolation and recovery logic.
        """
        session = runtime.builder_session_id
        self.env['nexora.builder_session_service']._emit_event(
            session, 'tool.started', f"Executing tool: {tool_id}", runtime=runtime
        )
        
        try:
            result = self.env['nexora.tool_registry'].execute_tool(tool_id, context, **kwargs)
            if result.success:
                self.env['nexora.builder_session_service']._emit_event(
                    session, 'tool.completed', f"Tool {tool_id} completed successfully.", runtime=runtime
                )
            else:
                self.env['nexora.builder_session_service']._emit_event(
                    session, 'tool.warning', f"Tool {tool_id} returned warnings or non-fatal errors: {result.errors}", runtime=runtime
                )
            return result
        except Exception as e:
            error_msg = f"{e}\n{traceback.format_exc()}"
            _logger.error(f"Tool {tool_id} crashed: {error_msg}")
            self.env['nexora.builder_session_service']._emit_event(
                session, 'tool.failed', f"Tool {tool_id} crashed unexpectedly: {e}", runtime=runtime
            )
            
            # Isolate failure and rollback if supported
            try:
                tool = self.env['nexora.tool_registry'].get_tool(tool_id=tool_id)
                tool.rollback(context, **kwargs)
                self.env['nexora.builder_session_service']._emit_event(
                    session, 'tool.rollback', f"Tool {tool_id} rolled back successfully.", runtime=runtime
                )
            except Exception as rollback_err:
                _logger.error(f"Tool {tool_id} rollback failed: {rollback_err}")
                
            from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionResult
            return ProviderExecutionResult(success=False, data=None, error=str(e))
