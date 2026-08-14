# -*- coding: utf-8 -*-
"""
nexora.mcp_connection_test_wizard
Phase 28 — MCP Connector Onboarding Platform
"""
import json
from odoo import models, fields, api
from odoo.exceptions import UserError

class NexoraMcpConnectionTestWizard(models.TransientModel):
    _name = 'nexora.mcp_connection_test_wizard'
    _description = 'MCP Connection Test Wizard'

    connector_id = fields.Many2one('nexora.connector', string='Connector', required=True)
    
    # Results
    success = fields.Boolean(string='Success', readonly=True)
    latency_ms = fields.Float(string='Latency (ms)', readonly=True)
    tool_count = fields.Integer(string='Tools Found', readonly=True)
    resource_count = fields.Integer(string='Resources Found', readonly=True)
    prompt_count = fields.Integer(string='Prompts Found', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    
    state = fields.Selection([
        ('init', 'Ready'),
        ('done', 'Done')
    ], default='init', string='State')

    def action_run_test(self):
        """Execute the ephemeral connection test and show results."""
        self.ensure_one()
        
        try:
            from odoo.addons.nexora_studio.services.connector.onboarding.connection_tester import McpConnectionTester
            from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService

            def onboarding_factory(rt, pipeline, env):
                return McpOnboardingService(rt, pipeline, env)

            tester = McpConnectionTester(
                onboarding_service_factory=onboarding_factory,
                odoo_env=self.env,
            )
            result = tester.test(self.connector_id)
            
            self.write({
                'success': result.success,
                'latency_ms': result.latency_ms,
                'tool_count': result.tool_count,
                'resource_count': result.resource_count,
                'prompt_count': result.prompt_count,
                'error_message': result.error_message or '',
                'state': 'done'
            })
            
            # Update the config record with the result
            config = self.env['nexora.mcp_server_config'].search([('connector_id', '=', self.connector_id.id)], limit=1)
            if config:
                # result.tested_at is an isoformat string or datetime object
                from datetime import datetime
                if isinstance(result.tested_at, str):
                    try:
                        tested_at = datetime.fromisoformat(result.tested_at).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        tested_at = result.tested_at[:19].replace('T', ' ')
                else:
                    tested_at = result.tested_at.strftime('%Y-%m-%d %H:%M:%S')

                config.write({
                    'last_tested_at': tested_at,
                    'last_test_result_json': json.dumps({
                        'success': result.success,
                        'latency_ms': result.latency_ms,
                        'tool_count': result.tool_count,
                        'resource_count': result.resource_count,
                        'prompt_count': result.prompt_count,
                        'error_message': result.error_message
                    })
                })
                
        except Exception as e:
            self.write({
                'success': False,
                'error_message': f"Unexpected error during test: {e}",
                'state': 'done'
            })
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nexora.mcp_connection_test_wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }
