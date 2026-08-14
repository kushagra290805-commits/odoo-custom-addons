# -*- coding: utf-8 -*-
"""
Telemetry Recorder

Central event-driven telemetry pipeline for all AI executions.
Handles recording to execution history, cost ledger, provider metrics, and runtime events.
"""
from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class TelemetryRecorder(models.AbstractModel):
    _name = 'nexora.telemetry_recorder'
    _description = 'AI Telemetry & Metrics Recorder'

    @api.model
    def record(self, ctx, result, execution_time, start_ts=None):
        """
        Record all telemetry for an AI execution.
        :param ctx: AIExecutionContext
        :param result: dict containing provider response and token usage
        :param execution_time: duration in seconds
        :param start_ts: optional timestamp of start time
        """
        if not start_ts:
            start_ts = fields.Datetime.now()
        
        end_ts = fields.Datetime.now()
        
        provider = result.get('provider', ctx.provider)
        model = result.get('model', ctx.model)
        
        prompt_tokens = result.get('prompt_tokens', 0)
        completion_tokens = result.get('completion_tokens', 0)
        total_tokens = result.get('total_tokens', result.get('token_usage', 0))
        
        status = 'failed' if result.get('error') else 'success'
        error_msg = result.get('error', '')
        
        # 1. Lookup Cost
        cost = 0.0
        catalog_model = self.env['nexora.ai_model_catalog'].search([
            ('provider', '=', provider),
            ('model_id', '=', model)
        ], limit=1)
        if catalog_model:
            cost = (prompt_tokens / 1000.0 * catalog_model.price_prompt) + \
                   (completion_tokens / 1000.0 * catalog_model.price_completion)

        # 2. Write to Execution History
        history_vals = {
            'execution_id': ctx.execution_id,
            'request_id': ctx.request_id,
            'job_id': ctx.job_id if ctx.job_id else False,
            'workspace_id': ctx.correlation_metadata.get('workspace_id') if ctx.correlation_metadata else False,
            'project_id': ctx.project_id if ctx.project_id else False,
            'builder_session_id': ctx.builder_session_id if ctx.builder_session_id else False,
            'provider': provider,
            'model': model,
            'latency': execution_time,
            'retry_count': ctx.retries,
            'status': status,
            'error_message': error_msg,
            'cost': cost,
            'token_usage': total_tokens,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'execution_type': ctx.correlation_metadata.get('execution_type', 'chat') if ctx.correlation_metadata else 'chat',
            'is_streaming': ctx.correlation_metadata.get('is_streaming', False) if ctx.correlation_metadata else False,
            'cache_hit': ctx.correlation_metadata.get('cache_hit', False) if ctx.correlation_metadata else False,
            'started_at': start_ts,
            'finished_at': end_ts,
        }
        
        if hasattr(ctx, 'resolution_trace') and ctx.resolution_trace:
            import json
            import dataclasses
            history_vals['resolution_trace'] = json.dumps(dataclasses.asdict(ctx.resolution_trace))
            
        history = self.env['nexora.ai_execution_history'].sudo().create(history_vals)
        
        # 3. Write to Cost Ledger
        if cost > 0:
            self.env['nexora.provider.cost_ledger'].sudo().create({
                'session_uuid': str(ctx.builder_session_id) if ctx.builder_session_id else '',
                'provider_id': provider,
                'usd_cost': cost,
                'units_consumed': total_tokens,
                'unit_type': 'tokens',
                'timestamp': end_ts,
            })
            
        # 4. Update Metrics Aggregation
        today = fields.Date.context_today(self)
        from datetime import datetime, time
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)
        
        metric = self.env['nexora.provider.metrics_aggregation'].sudo().search([
            ('provider_id', '=', provider),
            ('window_start', '>=', today_start),
            ('window_end', '<=', today_end)
        ], limit=1)
        
        if not metric:
            metric = self.env['nexora.provider.metrics_aggregation'].sudo().create({
                'provider_id': provider,
                'window_start': today_start,
                'window_end': today_end,
                'request_count': 0,
                'success_count': 0,
                'error_count': 0,
                'avg_latency_ms': 0.0,
                'total_tokens_consumed': 0,
            })
            
        # Compute rolling averages
        new_count = metric.request_count + 1
        new_success = metric.success_count + (1 if status == 'success' else 0)
        new_error = metric.error_count + (1 if status == 'failed' else 0)
        
        exec_ms = execution_time * 1000
        new_avg = ((metric.avg_latency_ms * metric.request_count) + exec_ms) / new_count
        
        metric.sudo().write({
            'request_count': new_count,
            'success_count': new_success,
            'error_count': new_error,
            'avg_latency_ms': new_avg,
            'total_tokens_consumed': metric.total_tokens_consumed + total_tokens,
        })
        
        # 5. Emit Runtime Events
        event_type = 'ai.execution.completed' if status == 'success' else 'ai.execution.failed'
        
        event_vals = {
            'runtime_type': 'ai_provider',
            'event_type': event_type,
            'timestamp': end_ts,
            'message': f"Execution {status} on {provider}/{model}. Tokens: {total_tokens}, Latency: {exec_ms:.0f}ms",
            'generation_job_id': ctx.job_id if ctx.job_id else False,
            'builder_session_id': ctx.builder_session_id if ctx.builder_session_id else False,
        }
        self.env['nexora.runtime_event'].sudo().create(event_vals)
        
        return history
