# -*- coding: utf-8 -*-
"""
nexora_studio test registration.

Phase 44.2 (W13 / G-11): every importable test module is registered so the
Odoo test runner actually discovers it. Modules are grouped by classification:

  UNIT          — pure unit tests, mocks only, no DB / no network
  INTEGRATION   — TransactionCase; require the Odoo test DB
  LIVE          — require a running server / external service; self-skip
                  when the prerequisite is absent
  CERTIFICATION — heavyweight end-to-end suites (npm builds, browsers)

NOT registered (import would fail and break test discovery):
  - test_platform_runtime_mcp_bootstrap, test_runtime_health:
      import the deleted legacy package services.runtime.mcp (Phase 44.1 G-11).
      Re-enable only after they are rewritten against the canonical
      connector runtime path.
  - test_playwright_interaction, test_playwright_validation:
      require the 'playwright' package, which is not installed.
"""

# --- UNIT -------------------------------------------------------------------
from . import test_mcp_sse_generic_transport
from . import test_firecrawl_integration
from . import test_encryption_key_config
from . import test_lifecycle_bootstrap
from . import test_routing_isolation
from . import test_auth_service_unit
from . import test_permission_service
from . import test_component_synthesis
from . import test_component_manifest
from . import test_design_system_engine
from . import test_design_token_binding
from . import test_interaction_builder
from . import test_design_blueprint_engine
from . import test_layout_composition
from . import test_asset_content_engine
from . import test_layout_engine
from . import test_accessibility_behavior
from . import test_pipeline_contract_validation
from . import test_props_generation
from . import test_react_provider
from . import test_react_rendering_provider
from . import test_provider_registry
from . import test_provider_interface
from . import test_render_model_validation
from . import test_interaction_translation
from . import test_phase44_2_hardening
from . import test_phase47_2_workflow_closure
from . import test_phase47_2_lifecycle
from . import test_phase47_3_runtime_contract
from . import test_phase47_3_runtime_odoo
from . import test_phase47_4_state_integrity
from . import test_phase47_4_progress_odoo
from . import test_phase47_5_pipeline_output
from . import test_phase47_5_pipeline_behavior
from . import test_phase47_6_csf_operations
from . import test_phase47_7_artifact_consumers

# --- PHASE 47.3x (client backend chain; TransactionCase) ----------------------
from . import test_phase47_33_client_lifecycle
from . import test_phase47_34_module_provisioning
from . import test_phase47_34x_safety_hardening
from . import test_phase47_35_client_api
from . import test_phase47_35x_security_invariants

# --- INTEGRATION (TransactionCase; require the Odoo test DB) -----------------
from . import test_unified_provider_platform
from . import test_unified_production_integration
from . import test_phase15c_design_intelligence
from . import test_phase16_autonomous_generation
from . import test_phase17_builder_intelligence
from . import test_mcp_source_adapter_mappings
from . import test_penpot_failure_isolation
from . import test_mcp_source_adapter
from . import test_mcp_credentials
from . import test_lifecycle_integrity
from . import test_credential_injection
from . import test_19g1_integration
from . import test_phase18_2_catalog_integration
from . import test_phase18_provider_integration
from . import test_dip_orm

# --- LIVE (self-skip without a running server / RUN_LIVE_TESTS=1) ------------
from . import test_auth_integration
from . import test_phase15c_live_smoke

# --- CERTIFICATION (heavyweight end-to-end; npm builds) -----------------------
from . import test_end_to_end_pipeline
from . import test_runtime_validation
from . import test_connector_restart_persistence
