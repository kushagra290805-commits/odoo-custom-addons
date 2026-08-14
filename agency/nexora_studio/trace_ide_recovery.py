"""
Mini-test to trace IDE recovery status step by step.
"""
import json

session_service = env['nexora.builder_session_service']
ide_service = env['nexora.ide_service']
runtime_service = env['nexora.runtime_service']

# Quick setup
config = env['nexora.builder_configuration'].search([], limit=1)
import tempfile, os, uuid as u
temp_root = os.path.join(tempfile.gettempdir(), f'ide_trace_{str(u.uuid4())[:8]}')
os.makedirs(temp_root, exist_ok=True)
env['ir.config_parameter'].sudo().set_param('nexora.workspace_root', temp_root)

session = session_service.create_session({
    'name': f'TraceSession_{str(u.uuid4())[:6]}',
    'builder_configuration_id': config.id,
})
session_service.start_session(session)
env.cr.commit()

ide_runtime = env['nexora.runtime'].search([
    ('builder_session_id', '=', session.id),
    ('runtime_type', '=', 'ide')
], limit=1)

print(f"\n[1] After start: IDE status={ide_runtime.status}, health={ide_runtime.health}")
meta1 = json.loads(ide_runtime.metadata_json or '{}')
print(f"    metadata: {meta1}")

# Simulate crash
ide_runtime.write({'status': 'error', 'health': 'critical', 'process_id': 0,
    'metadata_json': json.dumps({**meta1, 'attachment_status': 'detached', 'ide_pid': 0})})
env.cr.commit()

ide_runtime.invalidate_recordset()
print(f"\n[2] After crash sim: IDE status={ide_runtime.status}")
meta2 = json.loads(ide_runtime.metadata_json or '{}')
print(f"    metadata: {meta2}")

# STEP: synchronize_runtime_capabilities (what recover_session does first)
print(f"\n[3] Calling synchronize_runtime_capabilities...")
runtime_service.synchronize_runtime_capabilities()
env.cr.commit()
ide_runtime.invalidate_recordset()
print(f"    After sync_caps: IDE status={ide_runtime.status}")

# STEP: discover_runtimes
runtimes = runtime_service.discover_runtimes(session)
order = runtime_service.build_dependency_graph()
sorted_runtimes = sorted(runtimes, key=lambda r: order.index(r.runtime_type) if r.runtime_type in order else 999)

# STEP: recover_runtime_instance
print(f"\n[4] Calling recover_runtime_instance on IDE runtime...")
ide_rt_from_list = next((r for r in sorted_runtimes if r.runtime_type == 'ide'), None)
if ide_rt_from_list:
    print(f"    IDE runtime (from discover): status={ide_rt_from_list.status}")
    cap = env['nexora.runtime_capability'].search([('runtime_type', '=', 'ide')], limit=1)
    service = env.get(cap.plugin_service)
    try:
        service.recover_runtime_instance(ide_rt_from_list)
        print(f"    After recover_runtime_instance: status={ide_rt_from_list.status}")
    except Exception as ex:
        import traceback
        print(f"    EXCEPTION: {ex}")
        print(traceback.format_exc())
    
    env.cr.commit()
    ide_rt_from_list.invalidate_recordset()
    print(f"    After commit + invalidate: status={ide_rt_from_list.status}")

# ALSO: check original ide_runtime object
ide_runtime.invalidate_recordset()
print(f"\n[5] Original ide_runtime (same DB record, re-read): status={ide_runtime.status}")

# Cleanup
env.cr.rollback()
import shutil
shutil.rmtree(temp_root, ignore_errors=True)
print("\nTrace complete.")
