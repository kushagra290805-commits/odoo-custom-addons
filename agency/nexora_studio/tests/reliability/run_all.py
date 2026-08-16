import subprocess
import sys

scripts = [
    "audit_real_health_recovery.py",
    "audit_real_worker_isolation.py",
    "audit_storm_and_resource.py",
    "audit_db_integrity.py",
    "audit_post_restart.py"
]

all_passed = True
for script in scripts:
    print(f"Running {script}...")
    try:
        subprocess.run([sys.executable, f"tests/reliability/{script}"], check=True, text=True, cwd="d:\\ODOO\\custom-addons\\agency\\nexora_studio")
        print(f"SUCCESS: {script}")
    except subprocess.CalledProcessError as e:
        print(f"FAIL: {script} (exit code {e.returncode})")
        all_passed = False

if all_passed:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
