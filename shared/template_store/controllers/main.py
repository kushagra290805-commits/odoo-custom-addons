# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class TemplateStoreController(http.Controller):

    @http.route('/api/v1/templates/catalog', type='json', auth='user', methods=['GET'])
    def get_template_catalog(self, **kwargs):
        """
        Returns all active frontend and backend templates in the store catalog.
        """
        frontends = request.env['nexora.template_frontend'].search([('active', '=', True)])
        backends = request.env['nexora.template_backend'].search([('active', '=', True)])
        return {
            'status': 'success',
            'frontend_templates': [{'id': f.id, 'code': f.code, 'name': f.name, 'framework': f.framework} for f in frontends],
            'backend_templates': [{'id': b.id, 'code': b.code, 'name': b.name, 'framework': b.framework} for b in backends],
        }

    @http.route('/api/v1/generator/job/create', type='json', auth='user', methods=['POST'])
    def create_generation_job(self, **payload):
        """
        Webhook/API route to trigger template generation job creation from Builder Session or CI/CD.
        """
        pipeline_code = payload.get('pipeline_code', 'fullstack_standard')
        target_path = payload.get('target_path')
        frontend_ref = payload.get('frontend_ref')
        backend_ref = payload.get('backend_ref')
        variables = payload.get('variables', {})

        if not target_path:
            return {'status': 'error', 'message': 'target_path is required'}

        pipeline = request.env['nexora.generation_pipeline'].search([('code', '=', pipeline_code)], limit=1)
        if not pipeline:
            return {'status': 'error', 'message': f'Pipeline {pipeline_code} not found'}

        try:
            job = request.env['nexora.generation_service'].create_job(
                pipeline.id,
                target_path,
                frontend_ref=frontend_ref,
                backend_ref=backend_ref,
                variables=variables
            )
            return {
                'status': 'success',
                'job_id': job.id,
                'job_uuid': job.job_uuid,
                'job_status': job.status,
            }
        except Exception as e:
            _logger.exception("Failed to create generation job via API endpoint.")
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/v1/generator/job/execute/<int:job_id>', type='json', auth='user', methods=['POST'])
    def execute_generation_job(self, job_id, **kwargs):
        """
        Triggers execution of an existing generation job.
        """
        job = request.env['nexora.generation_job'].browse(job_id)
        if not job.exists():
            return {'status': 'error', 'message': f'Job {job_id} not found'}

        try:
            job.action_start_generation()
            return {
                'status': 'success',
                'job_id': job.id,
                'job_status': job.status,
            }
        except Exception as e:
            _logger.exception(f"Error executing generation job {job_id}")
            return {'status': 'error', 'message': str(e)}
