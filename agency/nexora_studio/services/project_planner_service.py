# -*- coding: utf-8 -*-
import uuid
import json
from odoo import models, api
import logging
from ..models.runtime_event_constants import RuntimeEvents

_logger = logging.getLogger(__name__)

class ProjectPlannerService(models.AbstractModel):
    _name = 'nexora.project_planner_service'
    _description = 'Project Planner Service (Meta-Orchestrator)'

    @api.model
    def start_planning(self, session_id, requirements):
        """
        Initializes a generation job exclusively for planning stages and invokes
        the Generation Orchestrator to run them.
        """
        session = self.env['nexora.builder_session'].browse(int(session_id))
        if not session.exists():
            return {'status': 'error', 'error': 'Session not found'}

        # Derive workspace path from session
        workspace_path = getattr(session, 'workspace_path', None) or f'/tmp/nexora_workspace/{session.id}'

        # Create a unique pipeline code that won't conflict with existing ones
        pipeline_code = f'PLAN_{session.id}_{uuid.uuid4().hex[:8]}'

        # Create a planning pipeline with the required planning stages
        pipeline = self.env['nexora.generation_pipeline'].create({
            'name': f'Planning Pipeline for {session.name}',
            'code': pipeline_code,
            'description': 'Dynamically created planning pipeline',
            'metadata_json': '{"completion_policy": {"status": "developer_review", "current_stage": "Awaiting Review"}}',
            'stage_ids': [
                (0, 0, {
                    'sequence': 10,
                    'name': 'Generate Project Blueprint',
                    'code': 'planner_blueprint',
                    'stage_type': 'planner_blueprint',
                    'service_name': 'nexora.ai_generation_stage.planner_blueprint'
                }),
                (0, 0, {
                    'sequence': 20,
                    'name': 'Generate Execution Plan',
                    'code': 'planner_execution',
                    'stage_type': 'planner_execution',
                    'service_name': 'nexora.ai_generation_stage.planner_execution'
                }),
            ]
        })

        # Retrieve the primary provider and its default model to persist in the job metadata
        adapters = self.env['nexora.ai_provider_manager']._get_adapters()
        cost_router = self.env['nexora.ai_cost_router']
        fallback_chain = cost_router.get_fallback_chain('medium') # Planner usually uses complex/medium
        
        provider_key = fallback_chain[0] if fallback_chain else 'openrouter'
        model = 'unknown'
        try:
            adapter = self.env['nexora.ai_provider_manager'].get_adapter(provider_key)
            model = self.env['nexora.ai_configuration_service'].get_active_model(provider_key) or 'unknown'
            # Layer 2 Validation: Abort immediately if model is invalid or unavailable
            self.env['nexora.ai_provider_manager'].validate_model(provider_key, model)
        except Exception as e:
            # Catch the validation error and return it cleanly
            return {'status': 'error', 'error': f"Provider Configuration Error: {str(e)}"}
        # Create Generation Job with all required fields
        job_uuid = str(uuid.uuid4())
        job = self.env['nexora.generation_job'].create({
            'name': f'Planning Job — {session.name}',
            'job_uuid': job_uuid,
            'builder_session_id': session.id,
            'pipeline_id': pipeline.id,
            'target_workspace_path': workspace_path,
            'status': 'queued',
            'metadata_json': json.dumps({
                'requirements': requirements,
                'session_id': session.id,
                'ai_provider': provider_key,
                'ai_model': model
            })
        })

        # Emit planning started event
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.PLANNER_STARTED,
            'message': f'Planning job {job_uuid} queued for session {session.name}.',
        })

        # Launch the Generation Orchestrator — pass the job record (not ID)
        orchestrator = self.env['nexora.generation_orchestrator']
        try:
            orchestrator.execute_job(job)
            return {'status': 'success', 'job_id': job.id, 'job_uuid': job_uuid}
        except Exception as e:
            _logger.error(f"Failed to run planner job: {e}")
            self.env['nexora.runtime_event'].create({
                'builder_session_id': session.id,
                'runtime_type': 'ai',
                'event_type': RuntimeEvents.PLANNER_FAILED,
                'message': f"Planner orchestration failed: {e}",
            })
            return {'status': 'error', 'error': str(e)}


    @api.model
    def get_plan_status(self, session_id):
        plan = self.env['nexora.execution_plan'].sudo().search([('builder_session_id', '=', int(session_id))], limit=1)
        if not plan:
            return {'status': 'not_found'}
            
        stages_data = []
        for stage in plan.stage_ids:
            tasks_data = []
            for task in stage.task_ids:
                tasks_data.append({
                    'name': task.name,
                    'objective': task.objective,
                    'required_capability': task.required_capability,
                    'status': task.status
                })
            stages_data.append({
                'name': stage.name,
                'sequence': stage.sequence,
                'status': stage.status,
                'tasks': tasks_data
            })
            
        blueprint = plan.project_blueprint_id
        
        return {
            'status': plan.status,
            'blueprint': {
                'information_architecture': blueprint.information_architecture if blueprint else '',
                'seo_requirements': blueprint.seo_requirements if blueprint else ''
            },
            'stages': stages_data
        }
