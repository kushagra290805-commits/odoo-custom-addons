# -*- coding: utf-8 -*-
"""
AI Dashboard Service

Provides aggregated metrics and operational data for the Nexora Console.
Instead of the React frontend calling multiple ORM endpoints and performing
aggregations, this service handles it efficiently on the backend.
"""
from odoo import models, api, fields
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

class AIDashboardService(models.AbstractModel):
    _name = 'nexora.ai_dashboard_service'
    _description = 'AI Operations Dashboard Service'

    @api.model
    def get_dashboard_metrics(self, days=7):
        """
        Fetch aggregated metrics for the AI dashboard over the last N days.
        """
        end_date = fields.Date.context_today(self)
        start_date = end_date - timedelta(days=days - 1)
        
        # 1. Fetch Aggregated Metrics
        metrics = self.env['nexora.provider.metrics_aggregation'].sudo().search([
            ('window_start', '>=', start_date),
            ('window_start', '<=', end_date)
        ])
        
        total_requests = sum(m.request_count for m in metrics)
        total_errors = sum(m.error_count for m in metrics)
        total_tokens = sum(m.total_tokens_consumed for m in metrics)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0
        
        # Calculate overall avg latency
        total_latency = sum(m.avg_latency_ms * m.request_count for m in metrics)
        avg_latency = (total_latency / total_requests) if total_requests > 0 else 0.0
        
        # 2. Fetch Cost Data
        start_datetime = fields.Datetime.to_datetime(start_date)
        cost_ledgers = self.env['nexora.provider.cost_ledger'].sudo().search([
            ('timestamp', '>=', start_datetime)
        ])
        total_cost = sum(c.usd_cost for c in cost_ledgers)
        
        # 3. Provider Breakdown
        provider_breakdown = {}
        for m in metrics:
            p = m.provider_id
            if p not in provider_breakdown:
                provider_breakdown[p] = {
                    'provider': p,
                    'requests': 0,
                    'errors': 0,
                    'tokens': 0,
                    'cost': 0.0,
                    '_total_latency': 0.0
                }
            provider_breakdown[p]['requests'] += m.request_count
            provider_breakdown[p]['errors'] += m.error_count
            provider_breakdown[p]['tokens'] += m.total_tokens_consumed
            provider_breakdown[p]['_total_latency'] += (m.avg_latency_ms * m.request_count)
            
        for c in cost_ledgers:
            p = c.provider_id
            if p in provider_breakdown:
                provider_breakdown[p]['cost'] += c.usd_cost
                
        # Finalize provider breakdown
        breakdown_list = []
        for p, data in provider_breakdown.items():
            reqs = data['requests']
            data['error_rate'] = (data['errors'] / reqs * 100) if reqs > 0 else 0.0
            data['avg_latency_ms'] = (data['_total_latency'] / reqs) if reqs > 0 else 0.0
            del data['_total_latency']
            
            # Enrich with display name if available
            try:
                registry = self.env['nexora.provider.registry'].sudo().search([('provider_id', '=', p)], limit=1)
                data['display_name'] = registry.name if registry else p.capitalize()
            except Exception:
                data['display_name'] = p.capitalize()
                
            breakdown_list.append(data)
            
        # 4. Recent Executions (Last 10)
        recent_executions = self.env['nexora.ai_execution_history'].sudo().search(
            [], order='started_at desc', limit=10
        )
        recent_list = []
        for ex in recent_executions:
            recent_list.append({
                'id': ex.id,
                'provider': ex.provider,
                'model': ex.model,
                'status': ex.status,
                'latency': ex.latency,
                'tokens': ex.token_usage,
                'cost': ex.cost,
                'started_at': ex.started_at.isoformat() if ex.started_at else None,
                'workspace_id': ex.workspace_id.id if ex.workspace_id else None,
                'project_id': ex.project_id.id if ex.project_id else None,
            })
            
        return {
            'overview': {
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'total_cost': total_cost,
                'error_rate': error_rate,
                'avg_latency_ms': avg_latency,
                'period_days': days,
            },
            'provider_breakdown': breakdown_list,
            'recent_executions': recent_list
        }
