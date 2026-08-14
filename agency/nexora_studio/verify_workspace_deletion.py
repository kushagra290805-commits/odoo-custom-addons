# -*- coding: utf-8 -*-
"""
Verification script for Workspace Deletion validation path.
Run with: cmd /c "D:\ODOO\community\odoo\.venv\Scripts\python.exe odoo-bin shell -c D:\ODOO\configs\dev.conf -d nexora_studio < d:\ODOO\custom-addons\agency\nexora_studio\verify_workspace_deletion.py"
"""
import sys
import os
import shutil
import logging
from pathlib import Path

def verify():
    print("=== STARTING WORKSPACE DELETION VERIFICATION ===")
    
    # Setup test directory as our test workspace root
    workspace_service = env['nexora.workspace_service']
    test_root = Path(workspace_service.get_workspace_root_path()) / "nexora_test_workspace_unlink"
    if test_root.exists():
        shutil.rmtree(test_root, ignore_errors=True)
    test_root.mkdir(parents=True, exist_ok=True)
    
    # Create test workspace directory
    ws_dir = test_root / "test_workspace_dir"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "test_file.txt").write_text("workspace content", encoding="utf-8")
    
    # Create Workspace record in DB pointing to ws_dir
    ws_record = env['nexora.workspace'].create({
        'name': 'Test Deletion Workspace',
        'status': 'ready',
        'health': 'healthy',
        'workspace_path': str(ws_dir)
    })
    ws_id = ws_record.id
    print(f"Created Workspace record ID {ws_id} with workspace_path='{ws_record.workspace_path}'")
    
    # 1. Test safety check: Attempting to unlink while directory EXISTS MUST fail
    print("\n--- Test 1: Verifying safety check prevents deletion when physical directory exists ---")
    assert os.path.exists(ws_record.workspace_path), "Precondition failed: physical directory should exist."
    try:
        ws_record.unlink()
        raise Exception("FAIL: unlink() succeeded even though physical directory existed on disk!")
    except Exception as e:
        if "Please delete the physical workspace directory before deleting the Workspace record." not in str(e):
            raise Exception(f"FAIL: Unexpected error message when physical directory exists: {e}")
        print(f"PASS: Safety check triggered correctly when physical directory exists. Error: {e}")
        
    # Verify record still exists in database
    ws_check = env['nexora.workspace'].browse(ws_id)
    if not ws_check.exists():
        raise Exception("FAIL: Workspace record was deleted from DB despite physical directory existing!")
    print("PASS: Workspace record preserved in database.")
    
    # 2. Remove physical directory from filesystem (`shutil.rmtree`) while `workspace_path` is still populated in DB
    print("\n--- Test 2: Verifying deletion succeeds after physical directory is removed from disk ---")
    shutil.rmtree(ws_dir, ignore_errors=True)
    path_exists_now = os.path.exists(ws_check.workspace_path)
    print(f"Removed physical directory from disk. Checked os.path.exists('{ws_check.workspace_path}') -> {path_exists_now}")
    if path_exists_now:
        raise Exception("Precondition failed: physical directory should be removed.")
        
    # Attempt unlink now that physical directory is gone
    print("Executing ws_check.unlink() with populated workspace_path after physical directory removal...")
    unlink_res = ws_check.unlink()
    
    # Verify record is successfully deleted
    ws_final = env['nexora.workspace'].search([('id', '=', ws_id)])
    if ws_final:
        raise Exception(f"FAIL: Workspace record ID {ws_id} still exists in DB after unlink()!")
    print(f"PASS: Workspace record ID {ws_id} successfully deleted from database after physical directory removal.")
    
    # Clean up test root
    shutil.rmtree(test_root, ignore_errors=True)
    print("\n=== WORKSPACE DELETION VERIFICATION SUCCESSFUL ===")

try:
    verify()
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
