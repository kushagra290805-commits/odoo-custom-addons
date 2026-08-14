# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid
from typing import Dict, Any, Optional, List, Union

class BuilderSession(models.Model):
    _name = 'nexora.builder_session'
    _description = 'Builder Session'
    
    # FUTURE RELATIONSHIPS:
    # Future versions will relate Builder Sessions to:
    # - Project Configuration
    # - Template Store
    # - Deployment
    # - Workspace
    # - Git Repository
    # - Preview Server
    # - AI Context
    # - Design Orchestrator (nexora.design_orchestrator via DesignProvider interface, default: Penpot)

    name = fields.Char(string='Name', required=True)
    builder_configuration_id = fields.Many2one(
        'nexora.builder_configuration',
        string="Builder Configuration",
        required=True,
        ondelete='restrict'
    )
    session_uuid = fields.Char(string='Session UUID', required=True, default=lambda self: str(uuid.uuid4()), copy=False, readonly=True)
    originating_job_uuid = fields.Char(string='Originating Job UUID', readonly=True, copy=False, help="Immutable identifier of the Generation Job that spawned this session.")
    status = fields.Selection([
        ('draft', 'Draft'),
        ('preparing', 'Preparing'),
        ('generating', 'Generating'),
        ('ai_reviewing', 'AI Reviewing'),
        ('developer_review', 'Developer Review'),
        ('running', 'Running'),
        ('testing', 'Testing'),
        ('qa', 'QA'),
        ('client_review', 'Client Review'),
        ('approved', 'Approved'),
        ('deploying', 'Deploying'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    project_name = fields.Char(string='Project Name')
    target_workspace_path = fields.Char(string='Target Workspace Path', help='Path provided by the Generation Engine')
    
    workspace_id = fields.Many2one('nexora.workspace', string='Linked Workspace', ondelete='set null')
    workspace_status = fields.Selection(related='workspace_id.status', string='Workspace Status', readonly=True)
    workspace_health = fields.Selection(related='workspace_id.health', string='Workspace Health', readonly=True)
    
    # RUNTIME ORCHESTRATION FIELDS
    runtime_state = fields.Selection([
        ('stopped', 'Stopped'),
        ('starting', 'Starting'),
        ('running', 'Running'),
        ('busy', 'Busy'),
        ('stopping', 'Stopping'),
        ('error', 'Error')
    ], string='Runtime State', default='stopped', required=True, copy=False)
    
    runtime_started_at = fields.Datetime(string='Runtime Started At', copy=False)
    runtime_stopped_at = fields.Datetime(string='Runtime Stopped At', copy=False)
    runtime_last_activity = fields.Datetime(string='Runtime Last Activity', copy=False)
    
    runtime_health = fields.Selection([
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('failed', 'Failed')
    ], string='Runtime Health', default='unknown', readonly=True, copy=False)
    
    runtime_errors = fields.Text(string='Runtime Errors', copy=False)
    
    # ORCHESTRATION TIMELINE & METRICS (PHASE 6F)
    event_ids = fields.One2many('nexora.runtime_event', 'builder_session_id', string='Runtime Events')
    lifecycle_phase = fields.Char(string='Lifecycle Phase', compute='_compute_orchestration_metrics', store=False)
    execution_order_display = fields.Char(string='Execution Order', compute='_compute_orchestration_metrics', store=False)
    dependency_graph_display = fields.Text(string='Dependency Graph', compute='_compute_orchestration_metrics', store=False)
    runtime_count = fields.Integer(string='Runtime Count', compute='_compute_orchestration_metrics', store=False)
    healthy_runtime_count = fields.Integer(string='Healthy Count', compute='_compute_orchestration_metrics', store=False)
    failed_runtime_count = fields.Integer(string='Failed Count', compute='_compute_orchestration_metrics', store=False)
    last_event_display = fields.Char(string='Last Event', compute='_compute_orchestration_metrics', store=False)

    started_at = fields.Datetime(string='Started At')
    closed_at = fields.Datetime(string='Closed At')
    last_activity = fields.Datetime(string='Last Activity')
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    # DEVELOPER ASSIGNMENT (Phase 9A)
    developer_id = fields.Many2one('res.users', string='Assigned Developer')
    developer_notes = fields.Html(string='Developer Notes')
    
    # Versioning
    active_version_id = fields.Many2one('nexora.builder.workspace.version', string='Active Version')
    version_ids = fields.One2many('nexora.builder.workspace.version', 'session_id', string='Versions')
    execution_plan_ids = fields.One2many('nexora.builder.execution_plan', 'session_id', string='Execution Plans')


    # PROGRESS TRACKING (Phase 9A)
    progress_percent = fields.Float(string='Progress (%)', default=0.0)
    current_stage = fields.Char(string='Current Stage')
    total_stages = fields.Integer(string='Total Stages', default=0)
    completed_stages = fields.Integer(string='Completed Stages', default=0)
    generation_attempts = fields.Integer(string='Generation Attempts', default=0)
    last_generation_at = fields.Datetime(string='Last Generation At')
    
    # IDE METADATA FIELDS (Phase 6G)
    ide_name = fields.Char(string='IDE Name', compute='_compute_ide_metadata', store=False)
    ide_status = fields.Char(string='IDE Status', compute='_compute_ide_metadata', store=False)
    ide_workspace_path = fields.Char(string='IDE Workspace Path', compute='_compute_ide_metadata', store=False)
    ide_session_uuid = fields.Char(string='Attached Session UUID', compute='_compute_ide_metadata', store=False)
    ide_workspace_uuid = fields.Char(string='Attached Workspace UUID', compute='_compute_ide_metadata', store=False)
    ide_pid = fields.Integer(string='IDE PID', compute='_compute_ide_metadata', store=False)
    ide_heartbeat = fields.Char(string='Heartbeat', compute='_compute_ide_metadata', store=False)
    ide_last_seen = fields.Char(string='Last Seen', compute='_compute_ide_metadata', store=False)
    ide_launcher_id = fields.Char(string='Launcher ID', compute='_compute_ide_metadata', store=False)
    ide_attachment_status = fields.Char(string='Attachment Status', compute='_compute_ide_metadata', store=False)

    # MCP METADATA FIELDS (Phase 7G)
    mcp_server_uuid = fields.Char(string='MCP Server UUID', compute='_compute_mcp_metadata', store=False)
    mcp_session_uuid = fields.Char(string='MCP Session UUID', compute='_compute_mcp_metadata', store=False)
    mcp_workspace_uuid = fields.Char(string='MCP Workspace UUID', compute='_compute_mcp_metadata', store=False)
    mcp_heartbeat = fields.Char(string='MCP Heartbeat', compute='_compute_mcp_metadata', store=False)
    mcp_connected_client = fields.Char(string='Connected Client', compute='_compute_mcp_metadata', store=False)
    mcp_connected_ide = fields.Char(string='Connected IDE', compute='_compute_mcp_metadata', store=False)
    mcp_registered_tools = fields.Text(string='Registered Tools', compute='_compute_mcp_metadata', store=False)
    mcp_server_version = fields.Char(string='Server Version', compute='_compute_mcp_metadata', store=False)
    mcp_status = fields.Char(string='MCP Status', compute='_compute_mcp_metadata', store=False)
    mcp_server_state = fields.Char(string='Server State', compute='_compute_mcp_metadata', store=False)
    mcp_last_activity = fields.Char(string='Last Activity', compute='_compute_mcp_metadata', store=False)
    mcp_tool_count = fields.Integer(string='Tool Count', compute='_compute_mcp_metadata', store=False)

    _sql_constraints = [
        ('session_uuid_uniq', 'unique(session_uuid)', 'Session UUID must be unique!'),
    ]

    @api.depends('event_ids', 'runtime_state', 'runtime_health')
    def _compute_orchestration_metrics(self):
        for session in self:
            if not session.id:
                session.lifecycle_phase = session.runtime_state.capitalize() if session.runtime_state else 'Draft'
                session.execution_order_display = "Not computed"
                session.dependency_graph_display = "{}"
                session.runtime_count = 0
                session.healthy_runtime_count = 0
                session.failed_runtime_count = 0
                session.last_event_display = "None"
                continue

            runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
            session.runtime_count = len(runtimes)
            session.healthy_runtime_count = sum(1 for r in runtimes if r.health == 'healthy' and r.status == 'running')
            session.failed_runtime_count = sum(1 for r in runtimes if r.status in ['error', 'failed'] or r.health in ['critical', 'failed'])

            try:
                service = self.env['nexora.builder_session_service']
                plan = service.get_execution_plan(session)
                session.execution_order_display = " -> ".join(plan.get('startup', []))
                graph = service.get_runtime_graph(session)
                session.dependency_graph_display = str(graph)
            except Exception:
                session.execution_order_display = "Pending discovery"
                session.dependency_graph_display = "{}"

            last_ev = self.env['nexora.runtime_event'].search([('builder_session_id', '=', session.id)], limit=1)
            if last_ev:
                session.last_event_display = f"{last_ev.timestamp or ''} [{last_ev.runtime_type}] {last_ev.event_type}: {last_ev.message or ''}"
            else:
                session.last_event_display = "No events recorded."

            if session.runtime_state == 'running':
                session.lifecycle_phase = 'Active Orchestration'
            elif session.runtime_state == 'starting':
                session.lifecycle_phase = 'Startup in Progress'
            elif session.runtime_state == 'stopping':
                session.lifecycle_phase = 'Shutdown in Progress'
            elif session.runtime_state == 'error':
                session.lifecycle_phase = 'Orchestration Failed / Degraded'
            else:
                session.lifecycle_phase = 'Idle / Stopped'

    @api.depends('runtime_state', 'runtime_health')
    def _compute_ide_metadata(self):
        import json
        for session in self:
            ide_runtime = self.env['nexora.runtime'].search([
                ('builder_session_id', '=', session.id),
                ('runtime_type', '=', 'ide')
            ], limit=1)
            
            meta = {}
            if ide_runtime:
                try:
                    meta = json.loads(ide_runtime.metadata_json or '{}')
                except Exception:
                    pass
                    
            session.ide_name = meta.get('ide_name', 'Unknown')
            session.ide_status = ide_runtime.status if ide_runtime else 'stopped'
            session.ide_workspace_path = meta.get('workspace_path', ide_runtime.endpoint if ide_runtime else '')
            session.ide_session_uuid = meta.get('session_uuid', '')
            session.ide_workspace_uuid = meta.get('workspace_uuid', '')
            session.ide_pid = meta.get('ide_pid', ide_runtime.process_id if ide_runtime else 0)
            session.ide_heartbeat = meta.get('heartbeat_timestamp', '')
            session.ide_last_seen = meta.get('last_seen_timestamp', '')
            session.ide_launcher_id = meta.get('launcher_id', '')
            session.ide_attachment_status = meta.get('attachment_status', 'detached')

    @api.depends('runtime_state', 'runtime_health')
    def _compute_mcp_metadata(self):
        import json
        for session in self:
            mcp_runtime = self.env['nexora.runtime'].search([
                ('builder_session_id', '=', session.id),
                ('runtime_type', '=', 'mcp')
            ], limit=1)
            
            meta = {}
            if mcp_runtime:
                try:
                    meta = json.loads(mcp_runtime.metadata_json or '{}')
                except Exception:
                    pass
                    
            session.mcp_server_uuid = meta.get('server_uuid', '')
            session.mcp_session_uuid = meta.get('session_uuid', '')
            session.mcp_workspace_uuid = meta.get('workspace_uuid', '')
            session.mcp_heartbeat = meta.get('heartbeat', '')
            session.mcp_connected_client = meta.get('connected_client', '')
            session.mcp_connected_ide = meta.get('connected_ide', '')
            session.mcp_server_version = meta.get('server_version', '')
            session.mcp_status = mcp_runtime.status if mcp_runtime else 'stopped'
            session.mcp_server_state = meta.get('server_state') or meta.get('status') or 'offline'
            session.mcp_last_activity = meta.get('last_activity', '')
            reg_tools = meta.get('registered_tools')
            if isinstance(reg_tools, list):
                session.mcp_registered_tools = json.dumps(reg_tools)
                session.mcp_tool_count = len(reg_tools)
            else:
                session.mcp_registered_tools = reg_tools if reg_tools else '[]'
                try:
                    session.mcp_tool_count = len(json.loads(session.mcp_registered_tools))
                except Exception:
                    session.mcp_tool_count = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'session_uuid' not in vals:
                vals['session_uuid'] = str(uuid.uuid4())
        return super(BuilderSession, self).create(vals_list)

    def unlink(self):
        for record in self:
            if record.workspace_id:
                raise ValidationError(_("Delete or detach the workspace before deleting the Builder Session."))
        return super(BuilderSession, self).unlink()

    # [MIGRATION]: React Developer API endpoint (Future REST: POST /api/v1/sessions/{id}/start)
    def action_start_runtime(self):
        service = self.env['nexora.builder_session_service']
        for record in self:
            service.start_session(record)
            
    # [MIGRATION]: React Developer API endpoint (Future REST: POST /api/v1/sessions/{id}/stop)
    def action_stop_runtime(self):
        service = self.env['nexora.builder_session_service']
        for record in self:
            service.stop_session(record)
            
    # [MIGRATION]: React Developer API endpoint (Future REST: POST /api/v1/sessions/{id}/restart)
    def action_restart_runtime(self):
        service = self.env['nexora.builder_session_service']
        for record in self:
            service.restart_session(record)
            
    # [MIGRATION]: Administration endpoint / React API endpoint (Future REST: POST /api/v1/sessions/{id}/refresh)
    def action_refresh_runtime_status(self):
        service = self.env['nexora.builder_session_service']
        for record in self:
            service.get_session_status(record)

    # [MIGRATION]: Administration endpoint (Future REST: POST /api/v1/sessions/{id}/recover)
    def action_recover_session(self):
        service = self.env['nexora.builder_session_service']
        for record in self:
            service.recover_session(record)

    # [MIGRATION]: Administration endpoint (Future REST: DELETE /api/v1/sessions/{id})
    def action_destroy_session(self):
        service = self.env['nexora.builder_session_service']
        for record in self:
            service.destroy_session(record)

    # [MIGRATION]: Administration endpoint (UI Navigation)
    def action_view_originating_job(self):
        self.ensure_one()
        if not self.originating_job_uuid:
            raise UserError(_("This session does not have an originating job UUID."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Originating Generation Job'),
            'res_model': 'nexora.generation_job',
            'view_mode': 'list,form',
            'domain': [('job_uuid', '=', self.originating_job_uuid)],
            'context': self.env.context,
        }

    # [MIGRATION]: Deprecated wrapper (UI specific, will not be migrated to REST API)
    def action_copy_workspace_path(self):
        self.ensure_one()
        path = self.ide_workspace_path
        if not path and self.workspace_id:
            path = self.workspace_id.workspace_path
        if not path:
            raise ValidationError(_("No workspace path is available to copy."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Copied'),
                'message': _('Workspace path copied to clipboard.'),
                'type': 'success',
                'sticky': False,
            }
        }

    # [MIGRATION]: Deprecated wrapper (UI specific, will not be migrated to REST API)
    def action_open_workspace_in_explorer(self):
        self.ensure_one()
        service = self.env['nexora.ide_service']
        return service.open_workspace_in_explorer(self)

    def recommend_component_composition(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Recommend a composition of intelligent, reusable component definitions from the
        Design System Component Library based on client requirements instead of isolated sections (Phase 11D).
        """
        self.ensure_one()
        engine = self.env['nexora.design_system_engine']
        req = requirements or {}
        if 'project_name' not in req and self.project_name:
            req['project_name'] = self.project_name
        elif 'project_name' not in req and self.name:
            req['project_name'] = self.name
        return engine.compose_design(req)

    def recommend_page_layout(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Recommend an adaptive layout definition from the Layout Catalog and generate responsive trees
        across four standard viewports based on client requirements (Phase 11E).
        """
        self.ensure_one()
        engine = self.env['nexora.layout_engine']
        req = requirements or {}
        if 'project_name' not in req and self.project_name:
            req['project_name'] = self.project_name
        elif 'project_name' not in req and self.name:
            req['project_name'] = self.name
        return engine.recommend_layout_tree(req)

    def generate_asset_plan(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a validated, provider-neutral Asset Plan via AssetPlanningEngine (Phase 11F).
        """
        self.ensure_one()
        engine = self.env['nexora.asset_planning_engine']
        req = requirements or {}
        if 'project_name' not in req and self.project_name:
            req['project_name'] = self.project_name
        elif 'project_name' not in req and self.name:
            req['project_name'] = self.name
        return engine.generate_asset_plan(req)

    def generate_content_plan(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a validated, provider-neutral Content Plan via ContentIntelligenceEngine (Phase 11F).
        """
        self.ensure_one()
        engine = self.env['nexora.content_intelligence_engine']
        req = requirements or {}
        if 'project_name' not in req and self.project_name:
            req['project_name'] = self.project_name
        elif 'project_name' not in req and self.name:
            req['project_name'] = self.name
        return engine.generate_content_plan(req)

    def generate_design_blueprint(self, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a validated, provider-neutral Design Blueprint via DesignBlueprintEngine,
        enrich/validate it through DesignSystemEngine (Phase 11D), transform section compositions
        into adaptive responsive layouts through LayoutEngine (Phase 11E), and enrich with
        AssetPlanningEngine and ContentIntelligenceEngine (Phase 11F).
        Replaces legacy raw structural outputs with a first-class, 5-stage AI design pipeline.
        """
        self.ensure_one()
        bp_engine = self.env['nexora.design_blueprint_engine']
        sys_engine = self.env['nexora.design_system_engine']
        layout_engine = self.env['nexora.layout_engine']
        asset_engine = self.env['nexora.asset_planning_engine']
        content_engine = self.env['nexora.content_intelligence_engine']
        req = requirements or {}
        if 'project_name' not in req and self.project_name:
            req['project_name'] = self.project_name
        elif 'project_name' not in req and self.name:
            req['project_name'] = self.name
            
        bp_res = bp_engine.generate_blueprint(req)
        if not bp_res.get("is_valid") or not bp_res.get("blueprint"):
            return bp_res
            
        sys_res = sys_engine.process_blueprint(bp_res["blueprint"])
        enriched_bp = sys_res.get("enriched_blueprint", bp_res["blueprint"])
        
        layout_res = layout_engine.process_blueprint(enriched_bp)
        enriched_bp = layout_res.get("enriched_blueprint", enriched_bp)
        
        asset_res = asset_engine.process_blueprint(enriched_bp, req)
        enriched_bp = asset_res.get("enriched_blueprint", enriched_bp)
        
        content_res = content_engine.process_blueprint(enriched_bp, req)
        enriched_bp = content_res.get("enriched_blueprint", enriched_bp)
        
        bp_res["blueprint"] = enriched_bp
        bp_res["asset_plan"] = asset_res.get("asset_plan", {})
        bp_res["content_plan"] = content_res.get("content_plan", {})
        
        bp_res["design_system_compliance"] = {
            "is_compliant": sys_res.get("is_system_compliant"),
            "library_components_resolved": sys_res.get("library_components_resolved", []),
            "metrics": sys_res.get("validation_metrics", {}),
            "warnings": sys_res.get("validation_warnings", [])
        }
        bp_res["layout_intelligence_compliance"] = {
            "is_compliant": layout_res.get("is_layout_compliant"),
            "resolved_layouts_count": layout_res.get("resolved_layouts_count", 0),
            "metrics": layout_res.get("validation_metrics", {}),
            "warnings": layout_res.get("validation_warnings", []),
            "errors": layout_res.get("validation_errors", []),
            "quality_score": layout_res.get("quality_score", {})
        }
        bp_res["asset_planning_compliance"] = {
            "is_compliant": asset_res.get("is_asset_compliant"),
            "metrics": asset_res.get("validation_metrics", {}),
            "warnings": asset_res.get("validation_warnings", []),
            "errors": asset_res.get("validation_errors", []),
            "quality_score": asset_res.get("quality_score", {})
        }
        bp_res["content_intelligence_compliance"] = {
            "is_compliant": content_res.get("is_content_compliant"),
            "metrics": content_res.get("validation_metrics", {}),
            "warnings": content_res.get("validation_warnings", []),
            "errors": content_res.get("validation_errors", []),
            "quality_score": content_res.get("quality_score", {})
        }
        return bp_res

