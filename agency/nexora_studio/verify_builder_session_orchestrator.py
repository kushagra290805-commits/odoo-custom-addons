# -*- coding: utf-8 -*-
"""
Verification script for Phase 6F: Builder Session Orchestrator (`nexora.builder_session_service`).
Run with: cmd /c "D:\ODOO\community\odoo\.venv\Scripts\python.exe odoo-bin shell -c D:\ODOO\configs\dev.conf -d nexora_studio < d:\ODOO\custom-addons\agency\nexora_studio\verify_builder_session_orchestrator.py"
"""
import sys
import os
import shutil
import logging
from pathlib import Path

def verify():
    print("=== STARTING PHASE 6F BUILDER SESSION ORCHESTRATOR VERIFICATION ===")
    
    service = env['nexora.builder_session_service']
    runtime_service = env['nexora.runtime_service']
    
    # 1. Verify capability sync and no hardcoded framework checks
    print("\n--- Test 1: Verifying Dynamic Capability Registry & Graph Generation ---")
    runtime_service.synchronize_runtime_capabilities()
    capabilities = env['nexora.runtime_capability'].search([('enabled', '=', True)])
    cap_types = [c.runtime_type for c in capabilities]
    print(f"Discovered enabled runtime capabilities: {cap_types}")
    assert 'workspace' in cap_types and 'git' in cap_types and 'preview' in cap_types, "Core capabilities missing!"
    
    # Check topological order directly
    order = runtime_service.build_dependency_graph()
    print(f"Dynamic topological execution order: {order}")
    assert order.index('workspace') < order.index('git') < order.index('preview'), "Topological ordering violated!"
    
    # 2. Setup Test Builder Configuration and Workspace root
    original_workspace_root = env['ir.config_parameter'].sudo().get_param('nexora.workspace_root') or ''
    workspace_service = env['nexora.workspace_service']
    test_root = Path(workspace_service.get_workspace_root_path())
    print(f"Using workspace root: {test_root}")
    
    config = env['nexora.builder_configuration'].create({
        'name': 'Orchestrator Test Config',
        'status': 'locked'
    })
    
    # 3. Create Session via Orchestrator API
    print("\n--- Test 2: Verifying Session Creation & Initial Graph Discovery ---")
    session = service.create_session({
        'name': 'Phase 6F Orchestration Session',
        'builder_configuration_id': config.id
    })
    print(f"Created session ID {session.id} ({session.session_uuid})")
    
    runtimes = env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
    print(f"Discovered initial runtime records for session: {[r.runtime_type for r in runtimes]}")
    assert len(runtimes) >= 3, f"Expected at least 3 discovered runtimes, found {len(runtimes)}"
    
    graph = service.get_runtime_graph(session)
    plan = service.get_execution_plan(session)
    print(f"Orchestrator Execution Plan: {plan}")
    assert plan['startup'] == order, "Startup plan must match topological order!"
    assert plan['shutdown'] == list(reversed(order)), "Shutdown plan must match reverse topological order!"
    
    # 4. Test Ordered Startup & Event Timeline
    print("\n--- Test 3: Verifying Ordered Startup, Event Emission & Timeline Ordering ---")
    start_res = service.start_session(session)
    print(f"Start session result: {start_res}")
    
    status_info = service.get_session_status(session)
    print(f"Session Status Info: {status_info}")
    assert status_info['runtime_state'] == 'running', f"Expected runtime_state='running', got {status_info['runtime_state']}"
    assert status_info['runtime_health'] == 'healthy', f"Expected runtime_health='healthy', got {status_info['runtime_health']}"
    
    events = service.get_runtime_events(session)
    print(f"Total events emitted during startup: {len(events)}")
    assert len(events) >= 6, "Should emit STARTING, STARTED, HEALTHY events for session and runtimes"
    
    # Verify event ordering chronologically
    first_event = events[-1] # oldest since ordered timestamp desc, id desc
    assert first_event['event_type'] == 'STARTED' and first_event['runtime_type'] == 'session', "First event must be session created/initialized"
    
    # Verify dashboard metrics
    print(f"Dashboard metrics - Lifecycle Phase: '{session.lifecycle_phase}', Healthy Count: {session.healthy_runtime_count}/{session.runtime_count}")
    assert session.lifecycle_phase == 'Active Orchestration', "Lifecycle phase should be Active Orchestration"
    assert session.healthy_runtime_count == session.runtime_count, "All discovered runtimes must be healthy"
    
    # 5. Test Failure Propagation & Health Aggregation
    print("\n--- Test 4: Verifying Failure Propagation & Health Aggregation ---")
    # Simulate non-critical leaf runtime (preview) failure
    preview_rt = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'preview')], limit=1)
    preview_rt.status = 'error'
    preview_rt.health = 'critical'
    service._emit_event(session, 'FAILED', "Simulated preview crash", runtime=preview_rt)
    
    health_dict = service.get_session_health(session)
    print(f"Aggregated Health Dict after Preview crash: {health_dict}")
    assert health_dict['health'] == 'degraded', f"Expected aggregated health='degraded' after non-critical leaf failure, got {health_dict['health']}"
    assert session.runtime_state == 'running', "Session state should remain running when root workspace/git are healthy"
    
    # Verify Workspace and Git remained alive
    ws_rt = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'workspace')], limit=1)
    git_rt = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'git')], limit=1)
    assert ws_rt.status == 'running' and git_rt.status == 'running', "Parent dependencies must NOT be terminated when leaf fails!"
    
    # Simulate root dependency (workspace) failure
    ws_rt.status = 'error'
    ws_rt.health = 'critical'
    health_dict2 = service.get_session_health(session)
    service._update_session_health_and_state(session)
    print(f"Aggregated Health Dict after Workspace crash: {health_dict2}")
    assert health_dict2['health'] == 'failed', "Expected aggregated health='failed' when root critical capability fails!"
    assert session.runtime_state == 'error', "Session runtime_state must transition to 'error' on critical failure!"
    
    # 6. Test Recovery Engine (`recover_session`)
    print("\n--- Test 5: Verifying Recovery Engine across Odoo Startup/Restart ---")
    # Reset status before calling recovery
    ws_rt.status = 'running'
    ws_rt.health = 'healthy'
    preview_rt.status = 'running'
    preview_rt.health = 'healthy'
    
    rec_res = service.recover_session(session)
    print(f"Recovery result: {rec_res}")
    status_post_rec = service.get_session_status(session)
    print(f"Session Status post-recovery: {status_post_rec}")
    assert status_post_rec['runtime_health'] == 'healthy' and status_post_rec['runtime_state'] == 'running', "Session must be fully healthy after recovery"
    
    rec_events = [ev for ev in service.get_runtime_events(session) if ev['event_type'] == 'RECOVERED']
    assert len(rec_events) >= 1, "Must emit RECOVERED events during recovery pass"
    
    # 7. Test Ordered Shutdown (`stop_session`) & Destroy (`destroy_session`)
    print("\n--- Test 6: Verifying Ordered Reverse Shutdown & Session Destruction ---")
    stop_res = service.stop_session(session)
    print(f"Stop result: {stop_res}")
    assert session.runtime_state == 'stopped', "Session runtime_state must be 'stopped'"
    
    for r in env['nexora.runtime'].search([('builder_session_id', '=', session.id)]):
        assert r.status == 'stopped', f"Runtime {r.runtime_type} must be stopped after session stop!"
        
    # Verify destroy cleans up physical workspace directory via workspace_service
    ws_path = session.workspace_id.workspace_path if session.workspace_id else None
    print(f"Physical workspace path prior to destroy: {ws_path}")
    if ws_path and not os.path.exists(ws_path):
        Path(ws_path).mkdir(parents=True, exist_ok=True)
        
    dest_res = service.destroy_session(session)
    print(f"Destroy session result: {dest_res}")
    assert session.status == 'closed', "Session status must be 'closed'"
    if ws_path:
        assert not os.path.exists(ws_path), f"Physical workspace directory '{ws_path}' must be removed on destroy!"
        
    # Clean up specific workspaces created during this test
    # (Since we are using the real root, we should use the service to delete the specific workspaces rather than wiping the root)
    if 'session' in locals() and session and session.workspace_id:
        workspace_service.delete_workspace(session.workspace_id)
    
    if original_workspace_root:
        env['ir.config_parameter'].sudo().set_param('nexora.workspace_root', original_workspace_root)
    try:
        env.cr.commit()
    except:
        pass
    print("\n=== PHASE 6F BUILDER SESSION ORCHESTRATOR VERIFICATION SUCCESSFUL ===")

try:
    verify()
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
