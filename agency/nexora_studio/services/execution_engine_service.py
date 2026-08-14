# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.modules.registry import Registry as OdooRegistry
import json
import logging
import threading
from ..models.runtime_event_constants import RuntimeEvents

_logger = logging.getLogger(__name__)

class ExecutionEngineService(models.AbstractModel):
    _name = 'nexora.execution_engine_service'
    _description = 'Execution Engine Service'

    @api.model
    def start_execution(self, session_id, target_task_ids=None):
        session = self.env['nexora.builder_session'].browse(int(session_id))
        if not session.exists():
            return {'status': 'error', 'error': 'Session not found'}

        plan = self.env['nexora.execution_plan'].search([('builder_session_id', '=', session.id)], limit=1)
        if not plan:
            return {'status': 'error', 'error': 'Execution plan not found'}

        # Mark plan as executing
        plan.write({'status': 'executing'})

        # Build Manifest
        self._build_manifest(plan)

        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_ENGINE_STARTED,
            'message': 'Autonomous Website Generation Engine started.',
        })

        # Launch the execution loop in a background thread to prevent blocking the HTTP request
        db_name = self.env.cr.dbname
        uid = self.env.uid
        
        def run_loop():
            db_registry = OdooRegistry(db_name)
            with db_registry.cursor() as cr:
                env = api.Environment(cr, uid, {})
                try:
                    env['nexora.execution_engine_service']._execute_dag(session.id, plan.id, target_task_ids)
                except Exception as e:
                    _logger.error(f"Execution Engine crashed: {e}")
                    env['nexora.runtime_event'].create({
                        'builder_session_id': session.id,
                        'runtime_type': 'ai',
                        'event_type': RuntimeEvents.GENERATION_ENGINE_FAILED,
                        'message': f"Catastrophic failure: {e}",
                    })
                    plan = env['nexora.execution_plan'].browse(plan.id)
                    plan.write({'status': 'failed'})

        thread = threading.Thread(target=run_loop)
        thread.start()

        return {'status': 'success'}

    @api.model
    def _build_manifest(self, plan):
        blueprint = plan.project_blueprint_id
        if not blueprint:
            return
            
        manifest = self.env['nexora.generation_manifest'].search([('execution_plan_id', '=', plan.id)], limit=1)
        if not manifest:
            manifest = self.env['nexora.generation_manifest'].create({
                'builder_session_id': plan.builder_session_id.id,
                'execution_plan_id': plan.id,
            })
            
        manifest.write({
            'pages_json': blueprint.pages_json,
            'components_json': blueprint.component_hierarchy_json,
            'seo_requirements': blueprint.seo_requirements,
            'metadata_json': json.dumps({'timestamp': fields.Datetime.now().isoformat()})
        })

    @api.model
    def _execute_dag(self, session_id, plan_id, target_task_ids=None):
        plan = self.env['nexora.execution_plan'].browse(plan_id)
        session = self.env['nexora.builder_session'].browse(session_id)
        
        # Git Pre-Execution Checkpoint
        self.env['nexora.git_service'].commit_session(session_id, "Pre-Execution Checkpoint")

        # Get all tasks
        domain = [('stage_id.plan_id', '=', plan_id)]
        if target_task_ids:
            domain.append(('id', 'in', target_task_ids))
            
        tasks = self.env['nexora.execution_task'].search(domain)
        
        # We need to process topologically
        # For simplicity in this demo logic, we'll iterate until no pending tasks are left or we're stuck
        
        while True:
            # Refresh tasks
            pending_tasks = tasks.filtered(lambda t: t.status in ['pending', 'failed'])
            if not pending_tasks:
                break # All done!
                
            # Find a task with no uncompleted dependencies
            ready_task = None
            for t in pending_tasks:
                deps = self.env['nexora.plan_dependency'].search([('task_id', '=', t.id)])
                can_run = True
                for dep in deps:
                    if dep.depends_on_task_id.status != 'completed':
                        can_run = False
                        break
                if can_run:
                    ready_task = t
                    break
                    
            if not ready_task:
                # Deadlock or cyclic dependency or all remaining are blocked by failed tasks
                raise Exception("DAG resolution stuck. Unresolved dependencies or blocking failures.")

            # Process ready_task
            self._process_task(ready_task, session)
            
        # Post-Execution Checkpoint
        self.env['nexora.git_service'].commit_session(session_id, "Post-Execution Checkpoint")
        plan.write({'status': 'completed'})
        
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_ENGINE_COMPLETED,
            'message': 'Execution DAG completed successfully.',
        })

    def _process_task(self, task, session):
        task.write({'status': 'running'})
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_TASK_STARTED,
            'message': f"Executing Task: {task.name}",
        })
        
        manifest = self.env['nexora.generation_manifest'].search([('execution_plan_id', '=', task.stage_id.plan_id.id)], limit=1)
        
        # We use provider_manager natively
        provider = self.env['nexora.ai_provider_manager']
        prompt = (
            f"You are a capability executor for capability '{task.required_capability}'.\n"
            f"Objective: {task.objective}\n"
            f"Manifest Pages: {manifest.pages_json}\n"
            f"Manifest Components: {manifest.components_json}\n"
            f"Inputs: {task.inputs_json}\n"
            "Return ONLY the raw file content you generate, or a structured JSON response if no file is needed."
        )
        
        response = provider.route_request('task_execution', prompt)
        
        if response.get('error'):
            task.write({'status': 'failed', 'last_error': response['error']})
            self.env['nexora.runtime_event'].create({
                'builder_session_id': session.id,
                'runtime_type': 'ai',
                'event_type': RuntimeEvents.GENERATION_TASK_FAILED,
                'message': f"Task {task.name} failed: {response['error']}",
            })
            return

        task.write({'status': 'generated'})
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_TASK_GENERATED,
            'message': f"Task {task.name} generated. Running validation...",
        })
        
        # Validation
        if not self._validate_output(response['response'], task.validation_rules):
            task.write({'status': 'failed', 'last_error': 'Validation Failed'})
            self.env['nexora.runtime_event'].create({
                'builder_session_id': session.id,
                'runtime_type': 'ai',
                'event_type': RuntimeEvents.GENERATION_TASK_FAILED,
                'message': f"Task {task.name} validation failed.",
            })
            return
            
        task.write({'status': 'validated'})
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_TASK_VALIDATED,
            'message': f"Task {task.name} validated.",
        })
        
        # Commit to File System
        file_path = self._extract_target_path(task.outputs_json) or f"src/generated_{task.id}.js"
        
        ws_file_service = self.env['nexora.workspace_file_service']
        res = ws_file_service.save_file(session.id, file_path, response['response'])
        
        if res.get('status') == 'error':
            task.write({'status': 'failed', 'last_error': res['error']})
            return
            
        task.write({'status': 'committed'})
        
        # Git Checkpoint
        self.env['nexora.git_service'].commit_session(session.id, f"Auto-checkpoint for task {task.name}")
        
        task.write({'status': 'completed'})
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_TASK_COMPLETED,
            'message': f"Task {task.name} completed successfully.",
        })
        
        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_PREVIEW_UPDATED,
            'message': f"Preview triggers updated.",
        })

    def _validate_output(self, content, rules):
        # Basic mock validation logic
        if not content or len(content.strip()) == 0:
            return False
        return True
        
    def _extract_target_path(self, outputs_json):
        try:
            outputs = json.loads(outputs_json)
            if isinstance(outputs, dict) and 'file_path' in outputs:
                return outputs['file_path']
        except:
            pass
        return None
