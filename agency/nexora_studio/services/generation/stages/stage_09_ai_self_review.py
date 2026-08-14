# -*- coding: utf-8 -*-
"""
Stage 09: AI Self Review Ã¢â‚¬â€ the AI reviews its own generated code,
produces a structured JSON report, and optionally generates patches.
"""
from odoo import models
import json
import logging
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore
from odoo.addons.nexora_studio.models.runtime_event_constants import RuntimeEvents  # type: ignore

_logger = logging.getLogger(__name__)


class AISelfReviewStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.self_review'
    _inherit = 'nexora.ai_generation_stage'
    _description = 'Stage 09: AI Self Review'

    def get_stage_name(self):
        return self._name

    def validate(self, context):
        if not context.builder_session:
            raise ValueError(f'{self._description} requires a valid Builder Session.')

    def execute(self, context):
        session = context.builder_session
        workspace_path = context.workspace_path

        # Collect workspace context + git diff + previous stage outputs
        context_builder = self.env['nexora.context_builder']
        ai_ctx = context_builder.build(session)
        context_text = context_builder.to_prompt_text(ai_ctx)

        generated_files = context.get('ai_generated_files', [])
        prompt = self._build_review_prompt(context_text, generated_files)

        provider_manager = self.env['nexora.ai_provider_manager']
        response = provider_manager.route_request(
            'review_task', prompt,
            parameters={'json_mode': True, 'temperature': 0.2, 'max_tokens': 4096}
        )

        # Always audit
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
                f'AI Self Review error: {response["error"]}'
            )

        # Apply any patches the review generated
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
                f'{len(patch_result["applied_files"])} files patched.'
            ),
        })

        context.set('self_review_result', response.get('response', ''))

        return GenerationStageResult(
            GenerationStageResult.SUCCESS,
            f'{self._description} completed.',
            data={
                'review': response.get('response', ''),
                'applied_files': patch_result.get('applied_files', []),
                'git_commit': patch_result.get('git_commit'),
            }
        )

    def rollback(self, context, execution_data):
        commit = execution_data.get('git_commit') if execution_data else None
        if commit and context.workspace_path:
            self.env['nexora.patch_engine'].rollback(
                context.workspace_path, commit
            )

    def _build_review_prompt(self, context_text, generated_files):
        parts = [
            'Review the following generated code for correctness, '
            'best practices, and potential issues.',
            '',
            context_text,
            '',
            f'Files to review: {", ".join(generated_files[:30])}' if generated_files else '',
            '',
            'Return a JSON report with structure:',
            '{"issues": [{"file": "...", "line": 0, "severity": "error|warning|info", '
            '"description": "..."}], "patches": [{"file": "...", "content": "...", '
            '"action": "write"}]}',
            '',
            'If no issues are found, return {"issues": [], "patches": []}',
        ]
        return '\n'.join(parts)
