import os
import sys
import shutil
import time
import importlib.util

def load_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    
    # Mock odoo module for the imported file
    import sys
    class MockOdoo:
        class models:
            class AbstractModel:
                pass
        class api:
            @staticmethod
            def model(func):
                return func
    sys.modules['odoo'] = MockOdoo()
    
    spec.loader.exec_module(module)
    return module

def run_verification():
    print("====================================================")
    print("PHASE 22.2.5 — RUNTIME EXECUTION VERIFICATION (DIRECT)")
    print("====================================================")
    
    t0 = time.time()
    
    # 1. Select Plugin
    repo_url = "https://github.com/octocat/Hello-World.git"
    target_dir = r"D:\ODOO\runtime\repositories\hello-world"
    
    if os.path.exists(target_dir):
        def remove_readonly(func, path, excinfo):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(target_dir, onerror=remove_readonly)
        
    dep_mod = load_module_from_file('dep', r'D:\ODOO\custom-addons\agency\nexora_studio\services\dependency_installer_service.py')
    sandbox_mod = load_module_from_file('sandbox', r'D:\ODOO\custom-addons\agency\nexora_studio\services\execution_sandbox_service.py')
    
    installer = dep_mod.DependencyInstallerService()
    sandbox = sandbox_mod.ExecutionSandboxService()

    # 2. Real Installation (Lazy)
    print(f"\n[STEP 2] Executing Lazy Installation (DependencyInstallerService) for {repo_url}...")
    res = installer.install_git(repo_url, target_dir)
    if not res.get('success'):
        print(f"FAILED TO CLONE: {res.get('error')}")
        sys.exit(1)
    
    print("SUCCESS: Repository Cloned.")
    
    # 3. Sandbox Execution
    print("\n[STEP 3] Executing capability via ExecutionSandboxService...")
    t1 = time.time()
    exec_result = sandbox.execute_local(['git', 'log', '-1', '--oneline'], cwd=target_dir)
    t_exec = time.time() - t1
    
    if exec_result.get('success'):
        print(f"SUCCESS: Sandbox executed successfully. Output:\n{exec_result.get('stdout').strip()}")
    else:
        print(f"FAIL: Sandbox execution failed: {exec_result.get('error') or exec_result.get('stderr')}")
        sys.exit(1)
        
    # 4. Failure Isolation Test
    print("\n[STEP 4] Sandbox Failure / Isolation Test...")
    fail_res = sandbox.execute_local(['git', 'status'], cwd=r'C:\Windows')
    if fail_res.get('success'):
        print("FAIL: Sandbox allowed execution outside workspace!")
        sys.exit(1)
    else:
        print(f"SUCCESS: Sandbox correctly rejected out-of-bounds execution. Error: {fail_res.get('error')}")

    # 5. Timeout Test
    print("\n[STEP 5] Sandbox Timeout Test...")
    timeout_res = sandbox.execute_local(['python', '-c', 'import time; time.sleep(5)'], cwd=target_dir, timeout=1)
    if timeout_res.get('success'):
        print("FAIL: Sandbox failed to enforce timeout!")
        sys.exit(1)
    else:
        print(f"SUCCESS: Sandbox enforced timeout correctly. Error: {timeout_res.get('error')}")

    t_total = time.time() - t0
    print("\n====================================================")
    print("VERIFICATION COMPLETE")
    print(f"Total Execution Time: {t_total:.2f}s")
    print("====================================================")
    print("VERDICT: READY FOR MASS PLUGIN INTEGRATION")

if __name__ == "__main__":
    run_verification()
