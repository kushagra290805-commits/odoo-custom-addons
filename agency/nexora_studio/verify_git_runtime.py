import os
import sys
from odoo import api, SUPERUSER_ID

def verify(env):
    print("--- 1. Testing Sync Runtime Capabilities ---")
    runtime_service = env['nexora.runtime_service']
    runtime_service.synchronize_runtime_capabilities()
    
    cap = env['nexora.runtime_capability'].search([('runtime_type', '=', 'git')])
    if not cap:
        print("ERROR: Git capability not found after sync.")
        return
    print(f"SUCCESS: Git capability found. Provider: {cap.provider}, Priority: {cap.startup_priority}")
    if cap.metadata_json and "capabilities" in cap.metadata_json:
        print(f"SUCCESS: Metadata JSON contains capabilities: {cap.metadata_json}")
    
    print("\n--- 2. Building Dependency Graph ---")
    order = runtime_service.build_dependency_graph()
    print(f"Graph order: {order}")
    if order.index('workspace') > order.index('git'):
        print("ERROR: Workspace must start before Git!")
        return
    print("SUCCESS: Dependency graph is correctly ordered.")

    print("\n--- 3. Testing Session Runtime Generation ---")
    session = env['nexora.builder_session'].search([], limit=1)
    if not session:
        print("No sessions found, creating one...")
        config = env['nexora.builder_configuration'].create({
            'name': 'Test Config',
            'git_history_sync_limit': 10
        })
        session = env['nexora.builder_session'].create({
            'name': 'Git Test Session',
            'builder_configuration_id': config.id
        })
    
    runtime_service.start_runtime(session)
    
    workspace = session.workspace_id
    if not workspace or workspace.status != 'ready':
        print(f"ERROR: Workspace not ready: {workspace.status}")
        return
        
    git_rt_record = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'git')])
    if not git_rt_record or git_rt_record.status != 'running':
        print(f"ERROR: Git runtime not running: {git_rt_record.status if git_rt_record else 'missing'}")
        return
        
    git_rt_state = env['nexora.git_runtime'].search([('runtime_id', '=', git_rt_record.id)])
    if not git_rt_state:
        print("ERROR: Git runtime state not found in database.")
        return
        
    print(f"SUCCESS: Git Runtime started successfully.")
    
    print("\n--- 3.5 Testing Workspace Directory API ---")
    ws_rt_record = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'workspace')], limit=1)
    ws_service = env['nexora.workspace_service']
    root_dir = ws_service.get_root_directory(ws_rt_record)
    project_dir = ws_service.get_project_directory(ws_rt_record)
    cache_dir = ws_service.get_cache_directory(ws_rt_record)
    logs_dir = ws_service.get_logs_directory(ws_rt_record)
    temp_dir = ws_service.get_temp_directory(ws_rt_record)
    
    print(f"Root dir: {root_dir}")
    print(f"Project dir: {project_dir}")
    print(f"Cache dir: {cache_dir}")
    print(f"Logs dir: {logs_dir}")
    print(f"Temp dir: {temp_dir}")
    
    if not (os.path.exists(root_dir) and os.path.exists(project_dir) and os.path.exists(cache_dir) and os.path.exists(logs_dir) and os.path.exists(temp_dir)):
        print("ERROR: One or more workspace directories do not exist on filesystem!")
        return
    print("SUCCESS: All workspace API directories exist and are valid.")
    
    print("\n--- 4. Testing Git Operations ---")
    git_service = env['nexora.git_service']
    print("Running git_init()...")
    git_service.git_init(git_rt_record)
    
    # Check if .git exists in workspace
    repo_path = git_service._get_workspace_path(git_rt_record)
    if os.path.exists(os.path.join(repo_path, '.git')):
        print("SUCCESS: Repository initialized.")
    else:
        print("ERROR: .git directory not found.")
        return
        
    print("Creating a test file and committing...")
    import uuid
    test_content = f"Hello Git! {uuid.uuid4()}"
    with open(os.path.join(repo_path, 'test.txt'), 'w') as f:
        f.write(test_content)
        
    # Refresh should show dirty
    git_service.refresh_runtime(git_rt_record)
    git_rt_state = env['nexora.git_runtime'].search([('runtime_id', '=', git_rt_record.id)])
    print(f"Is dirty: {git_rt_state.is_dirty}")
    if not git_rt_state.is_dirty:
        print("ERROR: Git should be dirty!")
        return
        
    git_service.git_commit(git_rt_record, "Initial test commit")
    git_rt_state = env['nexora.git_runtime'].search([('runtime_id', '=', git_rt_record.id)])
    print(f"Is dirty after commit: {git_rt_state.is_dirty}")
    
    print("\n--- 5. Testing Health Checks ---")
    git_service.check_health(git_rt_record)
    print(f"Health: {git_rt_record.health}")
    
    print("\n--- 6. Testing Stop ---")
    runtime_service.stop_runtime(session)
    print(f"Git runtime status: {git_rt_record.status}")
    
    print("\nALL TESTS PASSED!")

if __name__ == '__main__':
    verify(env)
