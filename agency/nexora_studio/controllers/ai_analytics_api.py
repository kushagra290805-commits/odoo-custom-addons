# -*- coding: utf-8 -*-
"""
AI Analytics API Controller

Exposes backend telemetry and operational data for the React Console.
"""
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class AIAnalyticsAPI(http.Controller):
    
    @http.route('/api/v1/ai/metrics/dashboard', type='http', auth='user', methods=['GET'], csrf=False)
    def get_dashboard_metrics(self, **kwargs):
        """
        Returns aggregated dashboard metrics via AIDashboardService.
        """
        try:
            days = int(kwargs.get('days', 7))
            dashboard_svc = request.env['nexora.ai_dashboard_service']
            data = dashboard_svc.get_dashboard_metrics(days=days)
            
            return request.make_response(
                json.dumps({'success': True, 'data': data}),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error("Failed to fetch dashboard metrics: %s", str(e))
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/api/v1/ai/metrics/executions', type='http', auth='user', methods=['GET'], csrf=False)
    def get_executions(self, **kwargs):
        """
        Returns a paginated list of AI executions.
        """
        try:
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            provider = kwargs.get('provider')
            status = kwargs.get('status')
            
            domain = []
            if provider:
                domain.append(('provider', '=', provider))
            if status:
                domain.append(('status', '=', status))
                
            history_obj = request.env['nexora.ai_execution_history'].sudo()
            total = history_obj.search_count(domain)
            executions = history_obj.search(domain, limit=limit, offset=offset, order='started_at desc')
            
            results = []
            for ex in executions:
                results.append({
                    'id': ex.id,
                    'provider': ex.provider,
                    'model': ex.model,
                    'status': ex.status,
                    'latency_ms': ex.latency * 1000,
                    'total_tokens': ex.total_tokens,
                    'cost': ex.cost,
                    'error_message': ex.error_message,
                    'started_at': ex.started_at.isoformat() if ex.started_at else None,
                    'job_id': ex.job_id,
                    'workspace_id': ex.workspace_id.id if ex.workspace_id else None,
                })
                
            return request.make_response(
                json.dumps({'success': True, 'data': results, 'total': total, 'limit': limit, 'offset': offset}),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error("Failed to fetch AI executions: %s", str(e))
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
