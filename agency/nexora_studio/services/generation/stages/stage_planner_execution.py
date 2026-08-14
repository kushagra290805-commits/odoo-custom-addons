# -*- coding: utf-8 -*-
from odoo import models
import json
import logging
# pyrefly: ignore [missing-import]
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult
# pyrefly: ignore [missing-import]
from odoo.addons.nexora_studio.models.runtime_event_constants import RuntimeEvents
# type: ignore

_logger = logging.getLogger(__name__)

class StagePlannerExecution(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.planner_execution'
    _inherit = 'nexora.ai_generation_stage'
    _stage_type = 'planner_execution'
    _description = 'Stage: Generate Execution Plan DAG'

    def execute(self, job, stage, context):

        metadata = {}
        if job.metadata_json:
            try:
                metadata = json.loads(job.metadata_json)
            except:
                pass
        
        session_id = metadata.get('session_id')
        session = self.env['nexora.builder_session'].sudo().browse(session_id)
        blueprint_id = context.stage_data.get('blueprint_id')
        
        if not blueprint_id:
            return GenerationStageResult(GenerationStageResult.FAILURE, "Missing blueprint_id in context")

        blueprint = self.env['nexora.project_blueprint'].sudo().browse(blueprint_id)
        if not blueprint.exists():
            return GenerationStageResult(GenerationStageResult.FAILURE, "Blueprint not found")

        self.env['nexora.runtime_event'].sudo().create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.PLANNER_CAPABILITIES_SELECTED,
            'message': 'Selecting capabilities and mapping to execution plan.',
        })

        # To avoid passing huge context, summarize blueprint
        blueprint_summary = {
            "pages": json.loads(blueprint.pages_json),
            "components": json.loads(blueprint.component_hierarchy_json),
            "integrations": json.loads(blueprint.integrations_json)
        }

        # Fetch capabilities
        capabilities = self.env['nexora.runtime_capability'].sudo().search_read([], ['name', 'runtime_type', 'provider'])

        prompt = (
            "You are an expert technical project manager. Based on the Blueprint, create a precise Execution Plan "
            "represented as a list of Stages and Tasks.\n"
            f"Blueprint Summary: {json.dumps(blueprint_summary)}\n"
            f"Available Capabilities: {json.dumps(capabilities)}\n\n"
            "Constraints:\n"
            "1. Sequence must be logical (Setup -> Config -> UI -> API).\n"
            "2. Each Task MUST define a required_capability from the list (use runtime_type).\n"
            "3. Return ONLY valid JSON matching this schema:\n"
            "{\n"
            "  \"stages\": [\n"
            "    {\n"
            "      \"name\": \"Stage Name\",\n"
            "      \"sequence\": 10,\n"
            "      \"tasks\": [\n"
            "        {\n"
            "          \"name\": \"Task Name\",\n"
            "          \"objective\": \"string\",\n"
            "          \"required_capability\": \"runtime_type\",\n"
            "          \"inputs\": {}, \"outputs\": {},\n"
            "          \"depends_on\": [\"Other Task Name\"]\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        provider_manager = self.env['nexora.ai_provider_manager']
        response = provider_manager.route_request(
            'planner_execution', prompt,
            parameters={'temperature': 0.1, 'json_mode': True}
        )

        if response.get('error'):
            self.env['nexora.runtime_event'].sudo().create({
                'builder_session_id': session.id,
                'runtime_type': 'ai',
                'event_type': RuntimeEvents.PLANNER_FAILED,
                'message': f"Execution plan generation failed: {response['error']}",
            })
            return GenerationStageResult(GenerationStageResult.FAILURE, response['error'])

        try:
            raw_response = response['response']
            if raw_response.startswith('```json'):
                raw_response = raw_response[7:-3]
            elif raw_response.startswith('```'):
                raw_response = raw_response[3:-3]
            
            plan_data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            return GenerationStageResult(GenerationStageResult.FAILURE, f"Invalid JSON returned: {str(e)}")

        # Create Execution Plan Model
        plan = self.env['nexora.execution_plan'].sudo().create({
            'builder_session_id': session.id,
            'project_blueprint_id': blueprint.id,
            'status': 'validated'
        })
        
        # Keep track of tasks for dependency linking
        task_map = {}

        for stage_data in plan_data.get('stages', []):
            stage = self.env['nexora.execution_stage'].sudo().create({
                'plan_id': plan.id,
                'name': stage_data.get('name', 'Unnamed Stage'),
                'sequence': stage_data.get('sequence', 10),
            })
            
            for t_data in stage_data.get('tasks', []):
                task = self.env['nexora.execution_task'].sudo().create({
                    'stage_id': stage.id,
                    'name': t_data.get('name', 'Unnamed Task'),
                    'objective': t_data.get('objective', ''),
                    'required_capability': t_data.get('required_capability', ''),
                    'inputs_json': json.dumps(t_data.get('inputs', {})),
                    'outputs_json': json.dumps(t_data.get('outputs', {})),
                })
                task_map[task.name] = {
                    'record': task,
                    'depends_on': t_data.get('depends_on', [])
                }

        # Resolve dependencies (Edges of DAG)
        for task_name, meta in task_map.items():
            for dep_name in meta['depends_on']:
                dep_meta = task_map.get(dep_name)
                if dep_meta:
                    self.env['nexora.plan_dependency'].sudo().create({
                        'task_id': meta['record'].id,
                        'depends_on_task_id': dep_meta['record'].id
                    })

        self.env['nexora.runtime_event'].sudo().create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.PLANNER_PLAN_CREATED,
            'message': 'Execution Plan DAG created and validated.',
        })

        self.env['nexora.runtime_event'].sudo().create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.PLANNER_COMPLETED,
            'message': 'Project Planning Mode Completed Successfully.',
        })

        return GenerationStageResult(GenerationStageResult.SUCCESS, 'Execution plan generated')
    def checkpoint(self, job, stage, context):
        try:
            plan = self.env['nexora.execution_plan'].sudo().search([('builder_session_id', '=', job.builder_session_id.id)], limit=1)
            if plan:
                file_service = self.env['nexora.workspace_file_service']
                plan_json = {
                    'status': plan.status,
                    'stages': []
                }
                for s in plan.stage_ids:
                    stage_dict = {
                        'name': s.name,
                        'sequence': s.sequence,
                        'tasks': []
                    }
                    for t in s.task_ids:
                        deps = self.env['nexora.plan_dependency'].search([('task_id', '=', t.id)])
                        stage_dict['tasks'].append({
                            'name': t.name,
                            'objective': t.objective,
                            'required_capability': t.required_capability,
                            'inputs': json.loads(t.inputs_json) if t.inputs_json else {},
                            'outputs': json.loads(t.outputs_json) if t.outputs_json else {},
                            'depends_on': [d.depends_on_task_id.name for d in deps]
                        })
                    plan_json['stages'].append(stage_dict)
                    
                # Write to disk
                file_service.save_file(job.builder_session_id.id, 'execution_plan.json', json.dumps(plan_json, indent=2))
                
                # Commit
                git_service = self.env['nexora.git_service']
                repo_path = git_service._get_session_repo_path(job.builder_session_id.id)
                import os
                if not os.path.exists(os.path.join(repo_path, '.git')):
                    git_service.init_session_repo(job.builder_session_id.id)
                git_service.commit_session(job.builder_session_id.id, "Plan generated", files_to_stage=['execution_plan.json'])
        except Exception as e:
            import logging
            import traceback
            print(f"Failed to create Git checkpoint for execution plan: {e}")
            print(traceback.format_exc())
            logging.getLogger(__name__).warning(f"Failed to create Git checkpoint for execution plan: {e}")
