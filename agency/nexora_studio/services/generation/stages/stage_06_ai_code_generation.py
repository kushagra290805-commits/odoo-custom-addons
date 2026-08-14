# -*- coding: utf-8 -*-
"""
Stage 06: AI Code Generation Ã¢â‚¬â€ dynamic generation driven entirely
by Project Requirements, Builder Configuration, and Template Analysis.

No hardcoded components (Header.js, Navbar, etc.).
"""
from odoo import models
import os
import json
import logging
from odoo.addons.nexora_studio.models.generation_stage_result import GenerationStageResult  # type: ignore
from odoo.addons.nexora_studio.models.runtime_event_constants import RuntimeEvents  # type: ignore

_logger = logging.getLogger(__name__)


class AICodeGenerationStage(models.AbstractModel):
    _name = 'nexora.ai_generation_stage.ai_code_generation'
    _inherit = 'nexora.ai_generation_stage'
    _description = 'Stage 06: AI Code Generation'

    def get_required_capabilities(self):
        return ['code_generation']

    def execute(self, context):
        session = context.builder_session
        workspace_path = context.workspace_path

        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_AI_STARTED,
            'message': 'Initiating AI Code Generation via Provider Manager.',
        })

        # Ã¢â€â‚¬Ã¢â€â‚¬ 1. Build rich context Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        context_builder = self.env['nexora.context_builder']
        ai_context = context_builder.build(session)
        context_text = context_builder.to_prompt_text(ai_context)

        # Ã¢â€â‚¬Ã¢â€â‚¬ 2. Analyse existing template Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        template_analyzer = self.env['nexora.template_analyzer']
        template_manifest = template_analyzer.analyze(workspace_path)
        context.set('template_manifest', template_manifest)

        # Ã¢â€â‚¬Ã¢â€â‚¬ 3. Build generation prompt from requirements Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        prompt = self._build_generation_prompt(ai_context, template_manifest)

        # Ã¢â€â‚¬Ã¢â€â‚¬ 4. Call Provider Manager Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        provider_manager = self.env['nexora.ai_provider_manager']
        response = provider_manager.route_request(
            'code_generation', prompt,
            parameters={'temperature': 0.3, 'max_tokens': 8192}
        )

        if response.get('error'):
            _logger.error('AI Generation failed: %s', response['error'])
            provider_manager.log_audit(
                session_id=session.id, stage=self._description,
                provider=response['provider'], model=response['model'],
                prompt=prompt, response='',
                parameters={'temperature': 0.3}, diff='',
                files='', execution_time=response.get('execution_time', 0),
                token_usage=response.get('token_usage', 0),
                error=response['error'],
            )
            return GenerationStageResult(
                GenerationStageResult.FAILURE,
                f'AI Code Generation failed: {response["error"]}'
            )

        # Ã¢â€â‚¬Ã¢â€â‚¬ 5. Apply patches via Patch Engine Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        patch_engine = self.env['nexora.patch_engine']
        patch_result = patch_engine.apply(
            workspace_path, response['response'],
            session_id=session.id, stage_name=self._description,
        )

        applied = patch_result.get('applied_files', [])
        rejected = patch_result.get('rejected_files', [])

        if not applied and not rejected:
            # AI responded with analysis only Ã¢â‚¬â€ still valid for templates
            # that are already complete.  Write the response as a note.
            _logger.info('AI returned analysis without patches Ã¢â‚¬â€ no files modified.')

        # Ã¢â€â‚¬Ã¢â€â‚¬ 6. Audit log Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        provider_manager.log_audit(
            session_id=session.id, stage=self._description,
            provider=response['provider'], model=response['model'],
            prompt=prompt, response=response['response'],
            parameters={'temperature': 0.3},
            diff=response.get('patch_diff', ''),
            files=', '.join(applied),
            execution_time=response.get('execution_time', 0),
            token_usage=response.get('token_usage', 0),
            error='; '.join(patch_result.get('errors', [])) or None,
        )

        context.set('ai_generated_files', applied)
        context.set('ai_rejected_files', rejected)

        self.env['nexora.runtime_event'].create({
            'builder_session_id': session.id,
            'runtime_type': 'ai',
            'event_type': RuntimeEvents.GENERATION_AI_COMPLETED,
            'message': (
                f'AI Code Generation complete. '
                f'{len(applied)} files applied, {len(rejected)} rejected.'
            ),
        })

        return GenerationStageResult(
            GenerationStageResult.SUCCESS,
            f'AI Code Generation complete. {len(applied)} files created/modified.',
            data={
                'generated_files': applied,
                'rejected_files': rejected,
                'git_commit': patch_result.get('git_commit'),
            }
        )

    def rollback(self, context, execution_data):
        commit_hash = execution_data.get('git_commit') if execution_data else None
        if commit_hash and context.workspace_path:
            self.env['nexora.patch_engine'].rollback(
                context.workspace_path, commit_hash
            )

    def _build_generation_prompt(self, ai_context, template_manifest):
        """
        Construct a generation prompt from business requirements and
        template analysis Ã¢â‚¬â€ no hardcoded files or demo components.
        """
        parts = []
        parts.append('You are generating code for a web project.')

        # Requirements
        reqs = ai_context.get('requirements', {})
        if reqs:
            parts.append('\n## Business Requirements')
            if reqs.get('business_name'):
                parts.append(f"Business: {reqs['business_name']}")
            if reqs.get('industry'):
                parts.append(f"Industry: {reqs['industry']}")
            if reqs.get('company_description'):
                parts.append(f"Description: {reqs['company_description']}")
            if reqs.get('branding'):
                parts.append(f"Branding: {reqs['branding']}")
            if reqs.get('required_pages'):
                parts.append(f"Required Pages: {reqs['required_pages']}")
            if reqs.get('required_features'):
                parts.append(f"Required Features: {reqs['required_features']}")
            if reqs.get('seo'):
                parts.append(f"SEO: {reqs['seo']}")

        # Framework
        fw = template_manifest.get('framework', 'unknown')
        parts.append(f'\n## Framework: {fw}')

        # Existing structure
        if template_manifest.get('pages'):
            parts.append(f"\nExisting Pages: {', '.join(template_manifest['pages'][:20])}")
        if template_manifest.get('components'):
            parts.append(f"Existing Components: {', '.join(template_manifest['components'][:20])}")
        if template_manifest.get('layouts'):
            parts.append(f"Existing Layouts: {', '.join(template_manifest['layouts'][:10])}")

        # Instructions
        parts.append('\n## Instructions')
        parts.append('- Modify existing template files to match the business requirements.')
        parts.append('- Create only necessary new files.')
        parts.append('- Return each file as a fenced code block with the relative file path.')
        parts.append('- Example format:')
        parts.append('```path/to/file.jsx')
        parts.append('// file content here')
        parts.append('```')
        parts.append('- Do NOT create demo components or placeholder files.')
        parts.append('- Ensure all code is production-ready and compiles.')

        return '\n'.join(parts)
