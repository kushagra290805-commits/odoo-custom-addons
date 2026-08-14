# -*- coding: utf-8 -*-
"""
Stage 11: AI Quality Pass Ã¢â‚¬â€ improves code quality, readability,
performance, and adherence to best practices.
"""
from odoo import models
import logging
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore
from odoo.addons.nexora_studio.models.runtime_event_constants import RuntimeEvents  # type: ignore

_logger = logging.getLogger(__name__)


class AIQualityPassStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.quality_pass'
    _inherit = 'nexora.ai_generation_stage'
    _description = 'Stage 11: AI Code Quality Pass'

    def get_stage_name(self):
        return self._name

    def validate(self, context):
        if not context.builder_session:
            raise ValueError(f'{self._description} requires a valid Builder Session.')

    def execute(self, context):
        session = context.builder_session
        workspace_path = context.workspace_path

        context_builder = self.env['nexora.context_builder']
        ai_ctx = context_builder.build(session)
        context_text = context_builder.to_prompt_text(ai_ctx)
        generated_files = context.get('ai_generated_files', [])

        prompt = self._build_prompt(context_text, generated_files)

        provider_manager = self.env['nexora.ai_provider_manager']
        response = provider_manager.route_request(
            'quality_pass', prompt,
            parameters={'json_mode': True, 'temperature': 0.2, 'max_tokens': 4096}
        )

        provider_manager.log_audit(
            session_id=session.id, stage=self._description,
            provider=response['provider'], model=response['model'],
            prompt=prompt, response=response.get('response', ''),
            parameters={'json_mode': True}, diff=response.get('patch_diff', ''),
            files=', '.join(generated_files),
            execution_time=response.get('execution_time', 0),
            token_usage=response.get('token_usage', 0),
            error=response.get('error'),
        )

        if response.get('error'):
            return GenerationStageResult(
                GenerationStageResult.FAILURE,
                f'AI Quality Pass error: {response["error"]}'
            )

        patch_result = {'applied_files': [], 'git_commit': None}
        if response.get('response'):
            patch_engine = self.env['nexora.patch_engine']
            patch_result = patch_engine.apply(
                workspace_path, response['response'],
                session_id=session.id, stage_name=self._description,
            )

        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'generation',
            'event_type': RuntimeEvents.GENERATION_STAGE_COMPLETED,
            'message': (
                f'{self._description} completed in '
                f'{response["execution_time"]:.2f}s. '
                f'{len(patch_result["applied_files"])} improvements applied.'
            ),
        })

        return GenerationStageResult(
            GenerationStageResult.SUCCESS,
            f'{self._description} completed.',
            data={
                'quality_report': response.get('response', ''),
                'applied_files': patch_result.get('applied_files', []),
                'git_commit': patch_result.get('git_commit'),
            }
        )

    def rollback(self, context, execution_data):
        commit = execution_data.get('git_commit') if execution_data else None
        if commit and context.workspace_path:
            self.env['nexora.patch_engine'].rollback(context.workspace_path, commit)

    def _build_prompt(self, context_text, files):
        parts = [
            'Perform a code quality review on the following project.',
            'Focus on: readability, performance, accessibility, '
            'naming conventions, code duplication, and best practices.',
            '',
            context_text,
            '',
        ]
        if files:
            parts.append(f'Changed Files: {", ".join(files[:30])}')
        parts.extend([
            '',
            'Return a JSON object:',
            '{"score": 0-100, "improvements": [{"file": "...", '
            '"description": "...", "severity": "high|medium|low"}], '
            '"patches": [{"file": "...", "content": "...", "action": "write"}]}',
        ])
        return '\n'.join(parts)
