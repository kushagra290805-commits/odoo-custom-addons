# -*- coding: utf-8 -*-
"""
Verify End-to-End Builder & Telemetry (Phase 18.3.1)
"""
import sys
import json
import time

def verify_e2e(env):
    try:
        print("[INFO] Starting End-to-End Builder Verification")
        
        # 1. Create a Workspace & Project
        workspace = env['nexora.workspace'].create({'name': 'Test Workspace E2E'})
        project = env['nexora.project'].create({
            'name': 'Test Project E2E',
            'status': 'draft'
        })
        
        # Create a mock config
        config = env['nexora.builder_configuration'].create({
            'name': 'Test Config'
        })
        # 2. Create a Builder Session
        session = env['nexora.builder_session'].create({
            'name': 'Test Session E2E',
            'builder_configuration_id': config.id,
            'workspace_id': workspace.id,
            'status': 'generating'
        })
        print(f"[INFO] Created Builder Session {session.id}")
        
        # 3. Simulate an Execution Context via Provider Manager
        # We will use the 'test' provider to avoid real API calls but still trigger the telemetry pipeline.
        pm = env['nexora.ai_provider_manager']
        
        # Prepare params
        params = {
            'builder_session_id': session.id,
            'workspace_id': workspace.id,
            'project_id': project.id,
            'use_test_provider': True,
            'temperature': 0.1,
            'max_tokens': 500,
        }
        
        from odoo.addons.nexora_studio.services.ai.ai_execution_context import AIExecutionContext
        ctx = AIExecutionContext(
            job_id=0,
            builder_session_id=session.id,
            capability='code_generation',
            project_id=project.id,
            correlation_metadata={
                'workspace_id': workspace.id,
                'execution_type': 'chat',
                'is_streaming': False
            }
        )
        
        # Execute
        print("[INFO] Executing route_request...")
        result = pm.route_request('code_generation', 'Hello world', parameters=params, ctx=ctx)
        
        print(f"[INFO] Execution completed. Result: {result}")
        print(f"[INFO] Token Usage: {result.get('token_usage') if result else 'None'}")
        
        # 4. Verify Telemetry: Execution History
        history = env['nexora.ai_execution_history'].search([('builder_session_id', '=', session.id)], limit=1)
        assert history, "Execution history record missing"
        assert history.project_id.id == project.id, "Project ID trace missing in history"
        assert history.workspace_id.id == workspace.id, "Workspace ID trace missing in history"
        assert history.provider == 'test', "Provider mismatch"
        assert history.token_usage > 0, "Token counting failed"
        assert history.status == 'success', "Execution failed"
        print("[PASS] Telemetry: Execution History Verified")
        
        # 5. Verify Telemetry: Cost Ledger
        # Test provider might have cost 0, let's just ensure no crash.
        ledger = env['nexora.provider.cost_ledger'].search([('session_uuid', '=', str(session.id))], limit=1)
        if ledger:
            print("[PASS] Telemetry: Cost Ledger Verified")
        else:
            print("[INFO] Telemetry: Cost Ledger skipped (Cost is 0 for test provider)")
            
        # 6. Verify Telemetry: Metrics Aggregation
        metrics = env['nexora.provider.metrics_aggregation'].search([('provider_id', '=', 'test')], limit=1)
        assert metrics, "Metrics Aggregation missing"
        assert metrics.request_count >= 1, "Request count not incremented"
        print("[PASS] Telemetry: Metrics Aggregation Verified")
        
        # 7. Verify Telemetry: Runtime Events
        events = env['nexora.runtime_event'].search([
            ('builder_session_id', '=', session.id),
            ('event_type', '=', 'ai.execution.completed')
        ])
        assert events, "Runtime Event missing"
        print("[PASS] Telemetry: Runtime Events Verified")
        
        # 8. Verify Dashboard API Service
        dashboard_svc = env['nexora.ai_dashboard_service']
        dashboard_data = dashboard_svc.get_dashboard_metrics(days=7)
        assert dashboard_data['overview']['total_requests'] >= 1, "Dashboard missing total requests"
        assert len(dashboard_data['provider_breakdown']) > 0, "Dashboard missing provider breakdown"
        assert dashboard_data['recent_executions'][0]['provider'] == 'test', "Recent executions missing our test"
        print("[PASS] Dashboard Service Data Aggregation Verified")
        
        print("[PASS] END-TO-END BUILDER & TELEMETRY VERIFICATION SUCCESSFUL")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[FAIL] End-to-End Verification Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    verify_e2e(env)
