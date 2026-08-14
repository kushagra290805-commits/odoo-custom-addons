# -*- coding: utf-8 -*-
import sys
import os
import shutil

def verify(env):
    print('Starting Real Generation Verification Suite...')
    
    # 0. Create Mock Template directories
    base_dir = r'D:\NexoraStudio\test_templates'
    front_dir = os.path.join(base_dir, 'frontend')
    back_dir = os.path.join(base_dir, 'backend')
    target_dir = os.path.join(base_dir, 'target_workspace')
    
    for d in [front_dir, back_dir, target_dir]:
        if os.path.exists(d):
            shutil.rmtree(d, onerror=remove_readonly)
        os.makedirs(d, exist_ok=True)
        
    # Create frontend files
    os.makedirs(os.path.join(front_dir, 'src'))
    os.makedirs(os.path.join(front_dir, 'shared'))
    with open(os.path.join(front_dir, 'src', 'App.vue'), 'w') as f:
        f.write('<template><h1>{{PROJECT_NAME}}</h1></template>')
    with open(os.path.join(front_dir, 'shared', 'model.json'), 'w') as f:
        f.write('{"model": "frontend"}')
        
    # Create backend files
    os.makedirs(os.path.join(back_dir, 'api'))
    os.makedirs(os.path.join(back_dir, 'shared'))
    with open(os.path.join(back_dir, 'api', 'main.py'), 'w') as f:
        f.write('print("API for {{PROJECT_NAME}}")')
    with open(os.path.join(back_dir, 'shared', 'model.json'), 'w') as f:
        f.write('{"model": "backend_override"}')
        
    # 1. Create Mock Pipeline and Templates in DB
    front_tpl = env['nexora.template_frontend'].create({
        'name': 'Test Frontend',
        'code': 'test_front',
        'subfolder_path': front_dir
    })
    
    back_tpl = env['nexora.template_backend'].create({
        'name': 'Test Backend',
        'code': 'test_back',
        'subfolder_path': back_dir
    })
    
    pipeline = env['nexora.generation_pipeline'].create({
        'name': 'Real Verification Pipeline',
        'code': 'REAL_TEST_PIPE',
    })
    
    stages_data = [
        ('validation', 10, 'Validate', 'validate_requirements'),
        ('preparation', 20, 'Prepare', 'prepare_workspace'),
        ('cloning', 30, 'Clone Frontend', 'clone_frontend'),
        ('cloning', 35, 'Clone Backend', 'clone_backend'),
        ('merge', 40, 'Merge', 'merge_templates'),
        ('variable', 50, 'Variables', 'replace_variables'),
        ('config', 60, 'Config', 'generate_config'),
        ('finalize', 70, 'Finalize', 'finalize_generation')
    ]
    
    for stage_type, seq, name, code in stages_data:
        env['nexora.generation_stage'].create({
            'name': name,
            'code': code,
            'pipeline_id': pipeline.id,
            'sequence': seq,
            'stage_type': stage_type,
            'service_name': 'nexora.generation_service'
        })
        
    # 1.5 Create Git Capability if not exists
    if not env['nexora.runtime_capability'].search([('runtime_type', '=', 'git')]):
        env['nexora.runtime_capability'].create({
            'name': 'Git Runtime',
            'runtime_type': 'git',
            'plugin_service': 'nexora.git_service',
            'sequence': 10
        })
        
    print('Pipeline, Templates and Capabilities created successfully.')

    # 2. Create Job
    job = env['nexora.generation_service'].create_job(
        pipeline_id=pipeline.id,
        target_workspace_path=target_dir,
        frontend_ref=front_tpl.id,
        backend_ref=back_tpl.id,
        variables={'PROJECT_NAME': 'My Super Project'}
    )
    
    # We must explicitly link the template IDs since create_job expects ref strings normally,
    # but we just bypassed that. Let's force them.
    job.frontend_template_id = front_tpl.id
    job.backend_template_id = back_tpl.id
    
    print(f'Job {job.job_uuid} created with status {job.status}.')

    # 3. Test Orchestrator
    job.action_start_generation()
    
    if job.status != 'completed':
        print(f'ERROR: Job ended with status {job.status}')
        print(f'Error Message: {job.error_message}')
        sys.exit(1)
        
    session = env['nexora.builder_session'].search([], order='id desc', limit=1)
    git_runtime = env['nexora.runtime'].search([('builder_session_id', '=', session.id), ('runtime_type', '=', 'git')], limit=1)
    if git_runtime:
        print(f"GIT REPO PATH: {env['nexora.git_service']._get_workspace_path(git_runtime)}")
    
    print('Generation successful. Verifying Filesystem...')
    
    # Verify variable replacement
    with open(os.path.join(target_dir, 'frontend', 'src', 'App.vue'), 'r') as f:
        content = f.read()
        if 'My Super Project' not in content:
            print(f'ERROR: Variable not replaced in App.vue. Found: {content}')
            sys.exit(1)
            
    # Verify merge resolution
    with open(os.path.join(target_dir, 'shared', 'model.json'), 'r') as f:
        content = f.read()
        if 'backend_override' not in content:
            print(f'ERROR: Merge conflict not resolved correctly. Found: {content}')
            sys.exit(1)
            
    # Verify configuration generated
    if not os.path.exists(os.path.join(target_dir, '.env.example')):
        print('ERROR: .env.example was not generated.')
        sys.exit(1)
        
    # Verify Git initialization
    if not os.path.exists(os.path.join(target_dir, '.git')):
        print('ERROR: Git repository was not initialized.')
        sys.exit(1)
        
    # 4. Test Rollback
    print('Testing Rollback...')
    job.status = 'failed' # Override for test to allow rollback
    try:
        job.action_rollback()
    except Exception as e:
        print(f'ERROR during rollback: {e}')
        sys.exit(1)
        
    if job.status != 'rolled_back':
        print(f'ERROR: Rollback failed. Status is {job.status}')
        sys.exit(1)
        
    # Ensure artifacts are deleted
    if os.path.exists(os.path.join(target_dir, 'frontend')):
        print('ERROR: Rollback failed to remove frontend directory.')
        sys.exit(1)
        
    print('Verification suite passed successfully.')

if "env" in locals():
    verify(env)
