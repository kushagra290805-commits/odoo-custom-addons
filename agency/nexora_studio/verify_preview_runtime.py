# -*- coding: utf-8 -*-
"""
Verification script for Phase 6E - Framework-Agnostic Preview Launcher Architecture.
Run with: python odoo-bin shell -c D:\ODOO\configs\dev.conf -d nexora_studio < d:\ODOO\custom-addons\agency\nexora_studio\verify_preview_runtime.py
"""
import sys
import os
import shutil
import time
import urllib.request
from pathlib import Path

def verify():
    print("=== STARTING PHASE 6E PREVIEW LAUNCHER ARCHITECTURE VERIFICATION ===")
    
    # 1. Verify source code separation & zero framework conditionals
    service_file = Path("d:/ODOO/custom-addons/agency/nexora_studio/services/preview_service.py")
    if not service_file.exists():
        raise Exception("FAIL: preview_service.py does not exist!")
        
    code = service_file.read_text(encoding="utf-8")
    forbidden_strings = ["python -m http.server", "npm run dev", "if framework ==", "if launcher_type ==", "if vite", "if next"]
    for s in forbidden_strings:
        if s in code:
            raise Exception(f"FAIL: preview_service.py contains forbidden framework-specific string or conditional: '{s}'")
    print("PASS: preview_service.py contains zero framework-specific startup commands or conditionals.")
    
    # 2. Dynamic Launcher Discovery (Requirement 1)
    preview_service = env['nexora.preview_service']
    all_launchers = preview_service.get_all_launchers()
    if not all_launchers or len(all_launchers) < 3:
        raise Exception(f"FAIL: get_all_launchers() returned insufficient launchers: {[l._name for l in all_launchers]}")
    
    launcher_ids = [l.launcher_manifest().get('launcher_id') for l in all_launchers]
    for required_id in ['vite', 'python_http', 'static_file']:
        if required_id not in launcher_ids:
            raise Exception(f"FAIL: Required launcher id '{required_id}' not found in dynamically discovered registry: {launcher_ids}")
            
    # Verify priority sorting descending (Vite priority 200 > PythonHttp priority 100 > StaticFile priority 80)
    priorities = [l.launcher_manifest().get('priority', 0) for l in all_launchers]
    if priorities != sorted(priorities, reverse=True):
        raise Exception(f"FAIL: Launchers not sorted by priority descending: {priorities}")
    print(f"PASS: Dynamic Launcher Discovery verified. Discovered launchers in priority order: {launcher_ids} ({priorities})")
    
    # 3. Launcher Contract Compliance (Requirement 12)
    required_methods = ['validate', 'prepare', 'start', 'stop', 'restart', 'health', 'reattach', 'cleanup', 'get_runtime_info', 'detect_project']
    required_manifest_keys = ['launcher_id', 'display_name', 'supported_frameworks', 'priority', 'supported_platforms', 'dependency_requirements', 'health_strategy', 'recovery_strategy']
    
    for launcher in all_launchers:
        for m in required_methods:
            if not hasattr(launcher, m):
                raise Exception(f"FAIL: Launcher {launcher._name} missing required method: '{m}'")
        manifest = launcher.launcher_manifest()
        for k in required_manifest_keys:
            if k not in manifest:
                raise Exception(f"FAIL: Launcher {launcher._name} manifest missing required key: '{k}'")
    print("PASS: Launcher Contract Compliance verified across all discovered launcher plugins.")
    
    # 4. Framework Detection & Launcher Selection (Requirement 2)
    workspace_service = env['nexora.workspace_service']
    test_selection_root = Path(workspace_service.get_workspace_root_path()) / "nexora_test_framework_detection"
    if test_selection_root.exists():
        shutil.rmtree(test_selection_root, ignore_errors=True)
    test_selection_root.mkdir(parents=True, exist_ok=True)
    
    # Vite project directory
    vite_dir = test_selection_root / "vite_project"
    vite_dir.mkdir()
    (vite_dir / "package.json").write_text('{"name": "test-vite", "devDependencies": {"vite": "^5.0.0"}}', encoding="utf-8")
    (vite_dir / "vite.config.js").write_text('export default {}', encoding="utf-8")
    
    # Static project directory (index.html only)
    static_dir = test_selection_root / "static_project"
    static_dir.mkdir()
    (static_dir / "index.html").write_text('<h1>Static HTML</h1>', encoding="utf-8")
    
    # Python static workspace directory
    py_dir = test_selection_root / "py_project"
    py_dir.mkdir()
    (py_dir / "app.py").write_text('print("Python Workspace")', encoding="utf-8")
    
    selected_vite = preview_service.detect_launcher(str(vite_dir))
    selected_static = preview_service.detect_launcher(str(static_dir))
    selected_py = preview_service.detect_launcher(str(py_dir))
    
    if selected_vite.launcher_manifest().get('launcher_id') != 'vite':
        raise Exception(f"FAIL: Expected 'vite' launcher for vite_dir, got: {selected_vite.launcher_manifest().get('launcher_id')}")
    if selected_static.launcher_manifest().get('launcher_id') != 'static_file':
        raise Exception(f"FAIL: Expected 'static_file' launcher for static_dir, got: {selected_static.launcher_manifest().get('launcher_id')}")
    if selected_py.launcher_manifest().get('launcher_id') != 'python_http':
        raise Exception(f"FAIL: Expected 'python_http' launcher for py_dir, got: {selected_py.launcher_manifest().get('launcher_id')}")
    print("PASS: Automatic framework detection and dynamic launcher selection verified (ViteLauncher, StaticFileLauncher, PythonHttpLauncher).")
    
    # 5. Dependency Validation & Missing Dependency Handling (Requirements 3 & 11)
    # Test valid validation on python launcher
    py_launcher = preview_service.resolve_launcher('python_http')
    val_py = py_launcher.validate(str(py_dir))
    if not isinstance(val_py, dict) or 'valid' not in val_py or 'errors' not in val_py or 'dependencies_checked' not in val_py:
        raise Exception(f"FAIL: Invalid structured validation dict returned by PythonHttpLauncher: {val_py}")
    if not val_py['valid']:
        raise Exception(f"FAIL: PythonHttpLauncher validation failed unexpectedly: {val_py['errors']}")
        
    # Test missing dependency/invalid project validation on ViteLauncher
    vite_launcher = preview_service.resolve_launcher('vite')
    empty_dir = test_selection_root / "empty_dir"
    empty_dir.mkdir()
    val_vite = vite_launcher.validate(str(empty_dir))
    if not isinstance(val_vite, dict) or 'valid' not in val_vite:
        raise Exception(f"FAIL: Invalid structured validation dict returned by ViteLauncher: {val_vite}")
    if val_vite['valid'] or "package.json not found" not in " ".join(val_vite['errors']):
        raise Exception(f"FAIL: ViteLauncher did not return expected structured errors for missing package.json: {val_vite}")
    print(f"PASS: Structured dependency validation and missing dependency handling verified: {val_vite['errors']}")
    
    # 6. Setup runtime regression session and workspace directory
    test_root = Path(workspace_service.get_workspace_root_path()) / "nexora_test_preview_workspace"
    if test_root.exists():
        shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True, exist_ok=True)
    (test_root / 'workspace').mkdir(parents=True, exist_ok=True)
    
    config = env['nexora.builder_configuration'].create({
        'name': 'Preview Test Config'
    })
    session = env['nexora.builder_session'].create({
        'name': 'Preview Regression Test Session',
        'builder_configuration_id': config.id
    })
    env['nexora.runtime_service'].discover_runtimes(session)
    
    ws_runtime = env['nexora.runtime_service'].get_runtime(session, 'workspace')
    ws_runtime.endpoint = str(test_root)
    
    project_dir = env['nexora.workspace_service'].get_project_directory(ws_runtime)
    logs_dir = env['nexora.workspace_service'].get_logs_directory(ws_runtime)
    
    # Create index.html inside project_dir
    index_file = Path(project_dir) / "index.html"
    index_file.write_text("<html><body><h1>Hello Nexora Preview</h1></body></html>", encoding="utf-8")
    
    # 7. Test form view button click: Start Preview (action_start_preview) & Port Allocation (Requirements 4 & 10)
    preview_runtime = env['nexora.runtime_service'].get_runtime(session, 'preview')
    preview_rt_record = preview_service._get_or_create_preview_runtime(preview_runtime)
    try:
        print("Testing form view button click: Start Preview (action_start_preview)...")
        preview_rt_record.action_start_preview()
        
        pid = preview_rt_record.process_id
        port = preview_rt_record.allocated_port
        url = preview_rt_record.preview_url
        cmd = preview_rt_record.preview_command
        
        print(f"Started Preview via action_start_preview() PID: {pid}, Port: {port}, URL: {url}, Command: {cmd}")
        if not pid or pid <= 0:
            raise Exception("FAIL: process_id not allocated (> 0) after action_start_preview()!")
        if port < 3000:
            raise Exception(f"FAIL: allocated_port {port} is less than 3000!")
        if url != f"http://127.0.0.1:{port}":
            raise Exception(f"FAIL: preview_url '{url}' mismatch with expected 'http://127.0.0.1:{port}'")
        if preview_runtime.status != 'running' or preview_runtime.health != 'healthy':
            raise Exception(f"FAIL: Runtime status '{preview_runtime.status}' / health '{preview_runtime.health}' incorrect after action_start_preview()!")
            
        log_file = Path(logs_dir) / "preview_static.log" if preview_rt_record.launcher_type == 'static_file' else Path(logs_dir) / "preview.log"
        if not log_file.exists() and not (Path(logs_dir) / "preview.log").exists():
            raise Exception(f"FAIL: log file not generated in {logs_dir}!")
        print("PASS: Launcher startup and port allocation verified successfully.")
        
        # 8. Verify live HTTP server response & Health Monitoring Contract (Requirement 7)
        time.sleep(0.5)
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            content = resp.read().decode("utf-8")
            if "Hello Nexora Preview" not in content:
                raise Exception(f"FAIL: Unexpected content retrieved from preview server: {content}")
        print("PASS: Live preview server HTTP request verified successfully.")
        
        # Verify identical structured runtime info contract
        info = preview_service.get_preview_status(preview_runtime)
        required_info_keys = ['status', 'health', 'pid', 'port', 'endpoint', 'process_information', 'last_health_check', 'last_activity']
        for k in required_info_keys:
            if k not in info:
                raise Exception(f"FAIL: get_preview_status/get_runtime_info missing identical contract key: '{k}'")
        if info['status'] != 'running' or info['health'] != 'healthy' or info['pid'] != pid or info['port'] != port:
            raise Exception(f"FAIL: Structured runtime info mismatch: {info}")
        print("PASS: Health monitoring and identical structured runtime info contract verified.")
        
        # 9. Test form view button click: Restart Preview (Requirement 5)
        print("Testing form view button click: Restart Preview (action_restart_preview)...")
        old_pid = preview_rt_record.process_id
        preview_rt_record.action_restart_preview()
        new_pid = preview_rt_record.process_id
        if not new_pid or new_pid <= 0 or new_pid == old_pid:
            raise Exception(f"FAIL: process_id did not restart properly ({old_pid} -> {new_pid}) after action_restart_preview()!")
        if preview_rt_record.status != 'running' or preview_rt_record.health != 'healthy':
            raise Exception("FAIL: status not running/healthy after action_restart_preview()!")
        print(f"PASS: Launcher restart verified successfully ({old_pid} -> {new_pid}).")
        
        time.sleep(0.5)
        pid = new_pid
        port = preview_rt_record.allocated_port
        url = preview_rt_record.preview_url
        
        # 10. Simulate Odoo Restart & Startup Recovery (Requirement 8)
        print("\n--- Simulating Odoo Restart & Startup Recovery ---")
        active_launcher = preview_service.resolve_launcher(preview_rt_record.launcher_type)
        if hasattr(active_launcher, 'clear_active_processes_cache'):
            active_launcher.clear_active_processes_cache()
        elif hasattr(active_launcher, '_active_static_processes'):
            active_launcher._active_static_processes.clear()
            
        from odoo.addons.nexora_studio.services import preview_service as preview_service_mod
        preview_service_mod.PreviewService._init_done = False
        
        print("Triggering synchronize_runtime_capabilities / service initialization after restart...")
        env['nexora.runtime_service'].synchronize_runtime_capabilities()
        
        preview_rt_record = env['nexora.preview_runtime'].search([('runtime_id', '=', preview_runtime.id)], limit=1)
        if preview_rt_record.process_id != pid or preview_rt_record.allocated_port != port:
            raise Exception(f"FAIL: Automatic recovery failed to preserve PID {pid} / Port {port} across restart!")
        if preview_runtime.status != 'running' or preview_runtime.health != 'healthy':
            raise Exception(f"FAIL: Runtime status '{preview_runtime.status}' / health '{preview_runtime.health}' incorrect after recovery!")
        print("PASS: Runtime recovery across Odoo restarts verified successfully.")
        
        # 11. Simulate Orphan Process Detection & Cleanup (Requirement 9)
        print("\n--- Simulating Orphan Process Detection & Cleanup ---")
        import subprocess
        orphan_port = 3088
        orphan_cmd = [sys.executable, "-m", "http.server", str(orphan_port), "--bind", "127.0.0.1"]
        orphan_proc = subprocess.Popen(orphan_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        orphan_pid = orphan_proc.pid
        print(f"Spawned orphan preview process PID {orphan_pid} on port {orphan_port} without DB ownership...")
        time.sleep(0.5)
        
        preview_service_mod.PreviewService._init_done = False
        preview_service.initialize_service()
        
        time.sleep(0.5)
        orphan_alive = active_launcher._is_process_alive(orphan_pid)
        if orphan_alive:
            try:
                orphan_proc.kill()
            except Exception:
                pass
            raise Exception(f"FAIL: Orphan PID {orphan_pid} was not terminated during dynamic cleanup!")
        print("PASS: Dynamic orphan cleanup across all launcher plugins verified successfully.")
        
        # 12. Test form view button click: Stop Preview (Requirement 6)
        print("\nTesting form view button click: Stop Preview (action_stop_preview)...")
        preview_rt_record.action_stop_preview()
        
        if preview_runtime.status != 'stopped' or preview_rt_record.process_id != 0 or preview_rt_record.allocated_port != 0:
            raise Exception(f"FAIL: Runtime not cleanly stopped! status={preview_runtime.status}, pid={preview_rt_record.process_id}, port={preview_rt_record.allocated_port}")
            
        time.sleep(0.3)
        unreachable = False
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                content = resp.read()
        except Exception:
            unreachable = True
            
        if not unreachable:
            raise Exception(f"FAIL: {url} is STILL REACHABLE after action_stop_preview()!")
        print("PASS: Launcher stop and port release verified successfully.")
        
    finally:
        try:
            preview_service.stop_preview(preview_runtime)
        except Exception:
            pass
        session.unlink()
        config.unlink()
        shutil.rmtree(test_root, ignore_errors=True)
        shutil.rmtree(test_selection_root, ignore_errors=True)
        
    print("=== PHASE 6E PREVIEW LAUNCHER ARCHITECTURE VERIFICATION SUCCESSFUL ===")

try:
    verify()
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
