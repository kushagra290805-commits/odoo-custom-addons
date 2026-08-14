# -*- coding: utf-8 -*-
from odoo import models
import json
import logging
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore
from odoo.addons.nexora_studio.models.runtime_event_constants import RuntimeEvents  # type: ignore

_logger = logging.getLogger(__name__)

class StagePlannerBlueprint(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.planner_blueprint'
    _inherit = 'nexora.ai_generation_stage'
    _stage_type = 'planner_blueprint'
    _description = 'Stage: Generate Project Blueprint'

    def get_required_capabilities(self):
        return ['reasoning', 'structured_output']

    def execute(self, job, stage, context):
        metadata = {}
        if job.metadata_json:
            try:
                metadata = json.loads(job.metadata_json)
            except:
                pass
        session_id = metadata.get('session_id')
        session = self.env['nexora.builder_session'].browse(session_id)
        requirements = metadata.get('requirements', {})



        prompt = (
            "You are an expert software architect. Analyze the following requirements and "
            "generate a comprehensive Project Blueprint in JSON format.\n"
            f"Requirements: {json.dumps(requirements)}\n"
            "Return ONLY valid JSON matching this schema:\n"
            "{\n"
            "  \"information_architecture\": \"string\",\n"
            "  \"navigation_structure\": \"string\",\n"
            "  \"pages_json\": [{\"name\": \"...\", \"path\": \"...\", \"description\": \"...\"}],\n"
            "  \"component_hierarchy_json\": [{\"name\": \"...\", \"type\": \"...\"}],\n"
            "  \"design_system_json\": {\"colors\": {}, \"typography\": {}},\n"
            "  \"integrations_json\": [\"...\"],\n"
            "  \"seo_requirements\": \"string\",\n"
            "  \"performance_goals\": \"string\"\n"
            "}"
        )

        provider_manager = self.env['nexora.ai_provider_manager']
        response = provider_manager.route_request(
            'planner_blueprint', prompt,
            parameters={'temperature': 0.2, 'json_mode': True}
        )

        if response.get('error'):
            self.env['nexora.runtime_event'].sudo().create({
                'builder_session_id': session.id,
                'runtime_type': 'ai',
                'event_type': RuntimeEvents.PLANNER_FAILED,
                'message': f"Blueprint generation failed: {response['error']}",
            })
            return GenerationStageResult(GenerationStageResult.FAILURE, response['error'])

        try:
            raw_response = response['response']
            # Clean up markdown code blocks if any
            if raw_response.startswith('```json'):
                raw_response = raw_response[7:-3]
            elif raw_response.startswith('```'):
                raw_response = raw_response[3:-3]
            
            blueprint_data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            return GenerationStageResult(GenerationStageResult.FAILURE, f"Invalid JSON returned: {str(e)}")

        # Ensure we don't duplicate blueprints for the same session
        blueprint = self.env['nexora.project_blueprint'].sudo().search([('builder_session_id', '=', session.id)], limit=1)
        if not blueprint:
            blueprint = self.env['nexora.project_blueprint'].sudo().create({'builder_session_id': session.id})
            
        blueprint.write({
            'status': 'generated',
            'information_architecture': blueprint_data.get('information_architecture', ''),
            'navigation_structure': blueprint_data.get('navigation_structure', ''),
            'pages_json': json.dumps(blueprint_data.get('pages_json', [])),
            'component_hierarchy_json': json.dumps(blueprint_data.get('component_hierarchy_json', [])),
            'design_system_json': json.dumps(blueprint_data.get('design_system_json', {})),
            'integrations_json': json.dumps(blueprint_data.get('integrations_json', [])),
            'seo_requirements': blueprint_data.get('seo_requirements', ''),
            'performance_goals': blueprint_data.get('performance_goals', ''),
        })

        context.stage_data['blueprint_id'] = blueprint.id

        self.env['nexora.runtime_event'].sudo().create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.PLANNER_BLUEPRINT_GENERATED,
            'message': 'Project Blueprint generated successfully.',
        })

        return GenerationStageResult(GenerationStageResult.SUCCESS, 'Blueprint generated', data={'blueprint_id': blueprint.id})
    def checkpoint(self, job, stage, context):
        try:
            blueprint = self.env['nexora.project_blueprint'].search([('builder_session_id', '=', job.builder_session_id.id)], limit=1)
            if blueprint:
                file_service = self.env['nexora.workspace_file_service']
                blueprint_json = {
                    'information_architecture': blueprint.information_architecture,
                    'navigation_structure': blueprint.navigation_structure,
                    'pages_json': json.loads(blueprint.pages_json) if blueprint.pages_json else [],
                    'component_hierarchy_json': json.loads(blueprint.component_hierarchy_json) if blueprint.component_hierarchy_json else [],
                    'design_system_json': json.loads(blueprint.design_system_json) if blueprint.design_system_json else {},
                    'integrations_json': json.loads(blueprint.integrations_json) if blueprint.integrations_json else [],
                    'seo_requirements': blueprint.seo_requirements,
                    'performance_goals': blueprint.performance_goals,
                }
                # Write to disk
                file_service.save_file(job.builder_session_id.id, 'blueprint.json', json.dumps(blueprint_json, indent=2))
                
                # Commit
                git_service = self.env['nexora.git_service']
                repo_path = git_service._get_session_repo_path(job.builder_session_id.id)
                import os
                if not os.path.exists(os.path.join(repo_path, '.git')):
                    git_service.init_session_repo(job.builder_session_id.id)
                git_service.commit_session(job.builder_session_id.id, "Blueprint generated", files_to_stage=['blueprint.json'])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to create Git checkpoint for blueprint: {e}")
