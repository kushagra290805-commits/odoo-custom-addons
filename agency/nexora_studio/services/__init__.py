# -*- coding: utf-8 -*-
# Service layer — Odoo AbstractModel registrations and utilities.
#
# IMPORT ORDER IS CRITICAL — Odoo resolves _inherit at load time,
# so base classes must be imported before their subclasses.

# ── Pure Python utilities (no Odoo model) ─────────────────────────────────
from . import error_codes
from . import cache_backends
from . import plugin_repository
from . import plugin_repository_factory
from . import ai_provider_manager          # proxy/stub; not an Odoo model

# ── Utilities that ARE Odoo models but have no _inherit deps ──────────────
from . import base_service
from . import permission_service
from . import semantic_version_service
from . import metadata_version_service
from . import compatibility_service
from . import workspace_file_service
from . import runtime_version_service

# ── Auth & Users ───────────────────────────────────────────────────────────
from . import auth_service
from . import user_service
from . import session_service
from . import audit_service

# ── Core Runtime Services ──────────────────────────────────────────────────
from . import runtime_plugin
from . import builder_session_service
from . import builder_configuration_service
from . import runtime_service
from . import git_service
from . import workspace_service
from . import preview_launcher
from . import ide_launcher
from . import launchers
from . import preview_service
from . import ide_service

# ── Orchestration & Execution ──────────────────────────────────────────────
from . import generation_orchestrator
from . import builder_assistant_service
from . import project_planner_service
from . import execution_engine_service

# ── Tool & Capability Layer ────────────────────────────────────────────────
from . import tool_registry
from . import tools
from . import capability_discovery_service
from . import capability_cache_service
from . import capability_lifecycle_service

# ── MCP Layer ─────────────────────────────────────────────────────────────
from . import mcp_registry
from . import mcp_server
from . import mcp_service
from . import mcp_protocol_adapter

# ── Plugin infrastructure ──────────────────────────────────────────────────
from . import plugin_manifest_validator
from . import plugin_manager
from . import dependency_graph_service

from . import plugin_installer_service
from . import plugin_lifecycle_service
from . import builder_health_service

# ── Generation Pipeline ────────────────────────────────────────────────────
from . import generation
from . import ai
from . import model_resolution_service
from . import source_framework
from . import design

from . import builder_intelligence

from . import dependency_installer_service

from . import execution_sandbox_service

from . import capability_providers_service
from . import capabilities
