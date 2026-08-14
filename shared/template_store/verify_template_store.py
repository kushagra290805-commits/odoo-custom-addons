# -*- coding: utf-8 -*-
"""
Verification Script for Phase 7 Architecture Refactor — Unified Template Store & Generation Engine
Runs inside Odoo shell:
python odoo-bin shell -c D:/ODOO/configs/dev.conf -d nexora_studio < D:/ODOO/custom-addons/shared/template_store/verify_template_store.py
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY_TEMPLATE_STORE")

def run_verification(current_env):
    print("=" * 70)
    print("=== STARTING PHASE 7 TEMPLATE STORE REFACTOR VERIFICATION ===")
    print("=" * 70)

    # 1. Verify Model Registrations (All 12 Models owned by template_store)
    print("\n--- Test 1: Template Store & Generation Engine Models ---")
    models_to_check = [
        'nexora.template_frontend',
        'nexora.template_backend',
        'nexora.template_version',
        'nexora.template_compatibility',
        'nexora.template_metadata',
        'nexora.generator_type',
        'nexora.generator_capability',
        'nexora.generation_pipeline',
        'nexora.generation_stage',
        'nexora.generation_job',
        'nexora.generation_variable',
        'nexora.generation_log'
    ]
    for model_name in models_to_check:
        assert model_name in current_env, f"Model `{model_name}` is missing from Odoo registry!"
        print(f"PASS: Model `{model_name}` is registered inside `template_store`.")

    # 2. Verify Abstract Service Registrations
    print("\n--- Test 2: Abstract Service Interfaces ---")
    services_to_check = [
        'nexora.generation_service',
        'nexora.pipeline_service',
        'nexora.validation_service',
        'nexora.variable_engine',
        'nexora.merge_service',
        'nexora.workspace_preparation_service'
    ]
    for service_name in services_to_check:
        assert service_name in current_env, f"Service `{service_name}` is missing from Odoo registry!"
        print(f"PASS: Abstract Service `{service_name}` is available in env.")

    # 3. Verify Seed Template Catalog & Metadata Loading
    print("\n--- Test 3: Seed Template Catalog & Metadata Specification ---")
    f_tpl = current_env['nexora.template_frontend'].search([('code', '=', 'vue3_spa')], limit=1)
    assert f_tpl, "Seed Frontend Template `vue3_spa` not found!"
    print(f"PASS: Found Frontend Template `{f_tpl.name}` (Path: {f_tpl.subfolder_path}).")

    b_tpl = current_env['nexora.template_backend'].search([('code', '=', 'fastapi_service')], limit=1)
    assert b_tpl, "Seed Backend Template `fastapi_service` not found!"
    print(f"PASS: Found Backend Template `{b_tpl.name}` (Path: {b_tpl.subfolder_path}).")

    compat = current_env['nexora.template_compatibility'].search([
        ('frontend_template_id', '=', f_tpl.id),
        ('backend_template_id', '=', b_tpl.id)
    ], limit=1)
    assert compat and compat.compatibility_level == 'verified', "Compatibility matrix verification failed!"
    print(f"PASS: Verified compatibility matrix pair `{compat.frontend_template_id.name}` <-> `{compat.backend_template_id.name}` ({compat.compatibility_level}).")

    meta = current_env['nexora.template_metadata'].search([('name', 'ilike', 'Standard Fullstack Metadata')], limit=1)
    assert meta, "Seed Metadata Specification not found!"
    print(f"PASS: Found Template Metadata Specification `{meta.name}` (v{meta.schema_version}).")

    # 4. Verify Seed Generator Types & Pipeline Configuration
    print("\n--- Test 4: Seed Generator Types & Pipeline Configuration ---")
    gen_type = current_env['nexora.generator_type'].search([('code', '=', 'fullstack_web')], limit=1)
    assert gen_type, "Seed Generator Type `fullstack_web` not found!"
    print(f"PASS: Found Generator Type `{gen_type.name}` (Category: {gen_type.category}).")

    pipeline = current_env['nexora.generation_pipeline'].search([('code', '=', 'fullstack_standard')], limit=1)
    assert pipeline, "Seed Generation Pipeline `fullstack_standard` not found!"
    print(f"PASS: Found Pipeline `{pipeline.name}` (Stages: {len(pipeline.stage_ids)}).")
    assert len(pipeline.stage_ids) == 8, f"Expected 8 pipeline stages, found {len(pipeline.stage_ids)}."

    expected_stages = [
        'validate', 'prepare', 'clone_frontend', 'clone_backend',
        'merge', 'variables', 'config', 'finalize'
    ]
    loaded_stages = [s.code for s in pipeline.stage_ids.sorted('sequence')]
    assert loaded_stages == expected_stages, f"Stage sequence mismatch: {loaded_stages} vs {expected_stages}"
    print(f"PASS: Verified exactly 8 ordered pipeline stages: {loaded_stages}")

    # 5. Verify Variable Engine Substitution & Metadata Defaults Resolution
    print("\n--- Test 5: Variable Substitution Engine & Metadata Defaults ---")
    sample_text = "Server running for {{PROJECT_NAME}} on port ${PORT} at {{API_URL}}."
    var_dict = {'PROJECT_NAME': 'ClientPortal', 'PORT': '8080', 'API_URL': 'https://api.nexora.dev'}
    subbed = current_env['nexora.variable_engine'].substitute_variables(sample_text, var_dict)
    expected_sub = "Server running for ClientPortal on port 8080 at https://api.nexora.dev."
    assert subbed == expected_sub, f"Substitution output `{subbed}` did not match expected!"
    print("PASS: Variable engine correctly substituted {{KEY}} and ${KEY} placeholders.")

    # 6. Verify End-to-End Generation Job Lifecycle & Registry Resolution
    print("\n--- Test 6: End-to-End Generation Job Lifecycle & Registry Resolution ---")
    target_path = "D:/NexoraStudio/workspaces/test-gen-workspace"
    job_vars = {'PROJECT_NAME': 'TestProject', 'ENVIRONMENT': 'development'}
    job = current_env['nexora.generation_service'].create_job(
        pipeline.id,
        target_path,
        frontend_ref="template_store://frontend/vue-spa",
        backend_ref="template_store://backend/fastapi-service",
        variables=job_vars
    )
    assert job and job.id, "Failed to create generation job record!"
    assert job.status == 'draft', f"Job status should be draft upon creation, got {job.status}"
    assert job.frontend_template_id == f_tpl, f"Registry Many2one pointer resolution failed! Expected {f_tpl.name}, got {job.frontend_template_id.name}"
    assert job.backend_template_id == b_tpl, f"Registry Many2one pointer resolution failed! Expected {b_tpl.name}, got {job.backend_template_id.name}"
    print(f"PASS: Created job `{job.name}` (UUID: {job.job_uuid}) with resolved templates: `{job.frontend_template_id.name}` & `{job.backend_template_id.name}`.")

    # Check defaults merging from metadata specification
    resolved_map = current_env['nexora.variable_engine'].resolve_job_variables(job)
    assert resolved_map.get('PROJECT_NAME') == 'TestProject', "Explicit variable should override default!"
    assert resolved_map.get('API_URL') == 'http://localhost:8000', "Metadata default API_URL should be merged automatically!"
    print("PASS: Variable engine correctly merged metadata defaults with explicit job variables.")

    # Execute Job
    print("Executing job pipeline stages...")
    job.action_start_generation()
    assert job.status == 'completed', f"Job status should be completed after execution, got `{job.status}`!"
    assert job.end_time, "Job end_time was not recorded!"
    print(f"PASS: Job `{job.name}` completed successfully (`{job.status}`).")

    # Verify Telemetry Logs
    assert len(job.log_ids) >= 8, f"Expected at least 8 execution logs, found {len(job.log_ids)}."
    print(f"PASS: Recorded {len(job.log_ids)} telemetry execution logs for job.")
    for log in job.log_ids.sorted('timestamp')[:3]:
        print(f"   -> [{log.level.upper()}] {log.message}")

    # Test Rollback
    print("Testing transactional rollback orchestration...")
    job.action_rollback()
    assert job.status == 'rolled_back', f"Job status should be rolled_back, got `{job.status}`!"
    print(f"PASS: Job rollback completed cleanly (`{job.status}`).")

    # Clean up test job
    job.unlink()
    print("PASS: Cleaned up test generation job record.")

    # 7. Regression Check across Nexora Studio
    print("\n--- Test 7: Regression Check across Nexora Studio ---")
    if 'nexora.runtime_service' in current_env:
        order = current_env['nexora.runtime_service'].build_dependency_graph()
        assert order == ['workspace', 'git', 'ide', 'preview'], f"Regression! Dependency order changed: {order}"
        print(f"PASS: Nexora Studio capability ordering regression check passed: {order}")
    else:
        print("INFO: `nexora.runtime_service` not checked directly in standalone test.")

    print("\n" + "=" * 70)
    print("=== PHASE 7 TEMPLATE STORE REFACTOR VERIFICATION SUCCESSFUL ===")
    print("=" * 70)

# When executed via `odoo-bin shell`, `env` is inside the shell's local/global dictionary.
if 'env' in locals():
    run_verification(locals()['env'])
elif 'env' in globals():
    run_verification(globals()['env'])
else:
    print("ERROR: `env` not found in shell execution scope.")
