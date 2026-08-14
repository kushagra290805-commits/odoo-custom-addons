import sys
import logging

def verify(env):
    print("Testing Production Website Generation...")
    
    # 1. Create a Configuration
    config = env['nexora.builder_configuration'].create({
        'name': 'Test Config 1',
        'environment': 'development'
    })
    
    import time
    ts = int(time.time())
    # 2. Create a Workspace
    workspace = env['nexora.workspace'].create({
        'name': f'Test Workspace {ts}',
        'workspace_slug': f'test_workspace_{ts}',
        'workspace_path': rf'D:\NexoraStudio\test_workspace_{ts}'
    })
    
    # 3. Create a Builder Session
    session = env['nexora.builder_session'].create({
        'name': 'Test Session',
        'builder_configuration_id': config.id,
        'workspace_id': workspace.id
    })
    
    print(f"Created Session {session.id}, kicking off run_generation()")
    
    pm = env['nexora.ai_provider_manager']
    print("AVAILABLE PROVIDERS AT START:", pm.get_available_providers())
    
    try:
        service = env['nexora.builder_session_service']
        service.transition_state(session, 'preparing', 'Testing preparation')
        service.run_generation(session, mode='FULL')
        env.cr.commit()
        print("Generation completed successfully and committed!")
    except Exception as e:
        print(f"Generation failed: {e}")
        import traceback
        traceback.print_exc()

if "env" in locals():
    verify(env)
