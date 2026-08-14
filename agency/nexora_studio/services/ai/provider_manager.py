# -*- coding: utf-8 -*-
"""
Provider Manager — single entry point for all AI operations.

Replaces the legacy nexora.ai_provider_manager with a modular
adapter-based architecture while preserving backward compatibility.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import time
import json
import os
import uuid
from datetime import datetime

from .ai_execution_context import AIExecutionContext
from .provider_execution_policy import RateLimitException

_logger = logging.getLogger(__name__)

_ADAPTER_MODELS = {
    'ollama_native': 'nexora.ai_adapter.ollama',
    'openai_compatible': 'nexora.ai_adapter.generic_openai',
    'nvidia_nim': 'nexora.ai_adapter.nvidia',
    'anthropic_native': 'nexora.ai_adapter.claude',
    'gemini_native': 'nexora.ai_adapter.gemini',
    'custom': 'nexora.ai_adapter.test',
}

_PROVIDER_ADAPTER_OVERRIDE = {
    'openrouter': 'nexora.ai_adapter.openrouter',
}


class AIProviderManager(models.AbstractModel):
    _name = 'nexora.ai_provider_manager'
    _description = 'AI Provider Manager — modular adapter architecture'

    # ── Adapter Registry ───────────────────────────────────────────

    @api.model
    def _get_adapters(self):
        """Return dict {provider_key: adapter_instance} dynamically based on registry."""
        adapters = {}
        # Ensure 'test' is always available if needed
        adapters['test'] = self.env['nexora.ai_adapter.test']
        
        registries = self.env['nexora.provider.registry'].search([('category', '=', 'ai')])
        for reg in registries:
            if reg.provider_id in _PROVIDER_ADAPTER_OVERRIDE:
                model_name = _PROVIDER_ADAPTER_OVERRIDE[reg.provider_id]
            else:
                model_name = _ADAPTER_MODELS.get(reg.compatibility_profile, 'nexora.ai_adapter.generic_openai')
            try:
                adapters[reg.provider_id] = self.env[model_name]
            except KeyError:
                pass
        return adapters

    @api.model
    def get_all_provider_metadata(self):
        """Return a list of metadata dicts for all available adapters."""
        metadata = []
        for key, adapter in self._get_adapters().items():
            try:
                if hasattr(adapter, 'get_provider_metadata'):
                    metadata.append(adapter.get_provider_metadata())
            except Exception as e:
                _logger.warning("Failed to get metadata for adapter %s: %s", key, e)
        return metadata

    @api.model
    def get_available_providers(self):
        """Return list of provider info dicts that are currently reachable."""
        result = []
        ai_service = self.env['nexora.ai_configuration_service']
        for key, adapter in self._get_adapters().items():
            available = False
            try:
                credentials = ai_service.get_provider_credentials(key)
                available = adapter.is_available(credentials=credentials)
            except Exception:
                pass
            result.append({
                'key': key,
                'name': adapter.get_display_name(),
                'available': available,
            })
        return result

    @api.model
    def get_adapter(self, provider_key):
        """Return a specific adapter by key, or raise."""
        adapters = self._get_adapters()
        adapter = adapters.get(provider_key)
        if adapter is None:
            raise UserError(f'Unknown AI provider: {provider_key}')
        return adapter

    # ── Routing ────────────────────────────────────────────────────

    @api.model
    def route_request(self, task_type, prompt, parameters=None, ctx: AIExecutionContext = None):
        """
        Backward-compatible entry point.
        Selects a provider via the CostRouter, executes a chat completion,
        and returns the standard result dict.
        """
        if self.env['ir.config_parameter'].sudo().get_param('agency.use_unified_provider_platform', 'False') == 'True':
            # Phase 15B.1: Cutover to Unified Provider Platform
            from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
            from odoo.addons.nexora_studio.services.providers.base_provider import (
                ExecutionOrchestrator, ProviderSession, ProviderCategory, ProviderFeatureSet
            )
            
            if GLOBAL_CONTAINER:
                orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)
                
                # Default session
                if parameters is None: parameters = {}
                session = ProviderSession(
                    session_id=str(parameters.get('builder_session_id', 'legacy_ai')),
                    user_id=self.env.user.id,
                    workspace_path='/tmp',
                    provider=None, # Will be resolved by CapabilityResolver
                    auth=None,
                    config={},
                    sandbox=None,
                    quota=None,
                    cost_budget_usd=1.0,
                    metadata={"task_type": task_type}
                )
                
                payload = {
                    "prompt": prompt,
                    "system": parameters.get('system_prompt', ''),
                    "parameters": parameters,
                    "task_type": task_type,
                    "model": parameters.get('model', '')
                }
                
                features = ProviderFeatureSet(
                    supports_streaming=False,
                    supports_tool_calling=False,
                    supports_vision=False
                )
                
                res = orch.execute(ProviderCategory.AI, "chat_completion", payload, features, session)
                
                if not res.success:
                    from odoo.exceptions import UserError
                    raise UserError(f"Unified Platform Execution Failed: {res.error}")
                    
                return res.data
        if parameters is None:
            parameters = {}
            
        if ctx is None:
            ctx = AIExecutionContext(
                job_id=parameters.get('job_id', 0),
                builder_session_id=parameters.get('builder_session_id', 0),
                capability=task_type,
                temperature=parameters.get('temperature', 0.4),
                max_tokens=parameters.get('max_tokens', 4096),
                json_mode=parameters.get('json_mode', False),
                timeout=parameters.get('timeout', 60),
                retries=parameters.get('retries', 2)
            )

        ai_service = self.env['nexora.ai_configuration_service']
        health_service = self.env['nexora.provider_health_service']
        adapters = self._get_adapters()
        cost_router = self.env['nexora.ai_cost_router']
        policy = self.env['nexora.provider_execution_policy']
        # Determine if Test Override
        is_test = os.environ.get('NEXORA_TEST_PROVIDER') == 'test' or self.env.context.get('NEXORA_TEST_PROVIDER') == 'test' or parameters.get('use_test_provider') is True
        req_caps = parameters.get('required_capabilities')
        
        while True:
            # 1. Resolve Provider and Credentials
            if is_test:
                from odoo.addons.nexora_studio.services.ai.ai_execution_context import ProviderResolution
                resolution = ProviderResolution(selected_provider='test', selected_model='test-model')
                _logger.info("Using test adapter due to environment or context override.")
                ctx = ctx.with_resolution(resolution)
                adapter = self.get_adapter('test')
                credentials = {}
            else:
                resolution = cost_router.resolve_provider(ctx, adapters, required_capabilities=req_caps)
                ctx = ctx.with_resolution(resolution)
                adapter = self.get_adapter(resolution.selected_provider)
                
                # Health Check
                if not health_service.is_provider_healthy(resolution.selected_provider):
                    _logger.warning("Provider %s is unhealthy, attempting fallback if possible.", resolution.selected_provider)
                    raise UserError(f"Provider {resolution.selected_provider} is unhealthy.")
                
                # Layer 3 Validation: Ensure model is valid in catalog
                self.validate_model(resolution.selected_provider, resolution.selected_model)
                credentials = ai_service.get_provider_credentials(resolution.selected_provider)
            
            # 2. Build Unified Execution Contract
            system_prompt = parameters.get('system_prompt', (
                'You are a senior full-stack web developer working inside '
                'Nexora Studio, an AI-assisted web development agency platform. '
                'Return only code or structured analysis as requested.'
            ))
            
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt})
            
            # 3. Execute with Unified Parameters
            try:
                start_time = datetime.now()
                result = policy.execute(ctx, lambda timeout: adapter.chat_completion(
                    messages, 
                    credentials=credentials, 
                    model=resolution.selected_model,
                    temperature=ctx.temperature, 
                    max_tokens=ctx.max_tokens,
                    json_mode=ctx.json_mode, 
                    timeout=timeout, 
                    retries=0
                ))
                
                # Record telemetry
                self._record_telemetry(ctx, result, start_time)
                
                # Normalize keys for backward compatibility
                result.setdefault('patch_diff', result.get('response', ''))
                result.setdefault('affected_files', '')
                return result
                
            except RateLimitException:
                if is_test:
                    raise UserError("Test provider hit rate limit unexpectedly.")
                _logger.warning("Rate limit hit for %s. Masking as unavailable and retrying CostRouter...", resolution.selected_provider)
                adapters.pop(resolution.selected_provider, None)
                if not adapters:
                    raise UserError("All available providers hit rate limits.")
                continue
                    
    def _record_telemetry(self, ctx: AIExecutionContext, result: dict, start_time: datetime):
        """Persist execution telemetry via the TelemetryRecorder."""
        try:
            exec_time = result.get('execution_time')
            if not exec_time:
                exec_time = (datetime.now() - start_time).total_seconds()
            
            self.env['nexora.telemetry_recorder'].record(ctx, result, exec_time, start_ts=start_time)
        except Exception as e:
            _logger.error("Failed to persist AI Execution Telemetry: %s", str(e))


    # ── Audit Logging ──────────────────────────────────────────────

    @api.model
    def log_audit(self, session_id, stage, provider, model, prompt,
                  response, parameters, diff, files, execution_time,
                  token_usage, error):
        """Create an AI audit log entry."""
        self.env['nexora.ai_audit_log'].create({
            'builder_session_id': session_id,
            'generation_stage': stage,
            'ai_provider': provider or '',
            'ai_model_name': model or '',
            'prompt_content': prompt or '',
            'response_content': response or '',
            'generation_parameters': str(parameters) if parameters else '',
            'patch_diff': diff or '',
            'affected_files': files or '',
            'execution_duration': execution_time or 0,
            'token_usage': token_usage or 0,
            'failure_reason': error or '',
            'status': 'failed' if error else 'pending',
        })

    # ── Catalog & Validation ───────────────────────────────────────

    @api.model
    def validate_model(self, provider_key, model_id):
        """
        Validates that a model exists and is active in the local catalog.
        Raises UserError if invalid.
        Delegates to AIConfigurationService.
        """
        validation = self.env['nexora.ai_configuration_service'].validate_configuration(provider_key, model_id)
        if not validation['valid']:
            raise UserError(validation['errors'][0]['message'])
        return True

    @api.model
    def list_models(self, provider_key):
        """Return list of active models for a provider from the local catalog."""
        return self.env['nexora.ai_model_catalog'].search_read(
            [('provider', '=', provider_key), ('status', '=', 'active')],
            fields=['model_id', 'name', 'context_length', 'price_prompt', 'price_completion', 'is_free']
        )


    
    @api.model
    def test_connection(self, provider_id):
        """
        Pure Orchestrator:
        Loads Provider Registry record.
        Resolves adapter.
        Executes adapter.health_check().
        Persists returned diagnostic states.
        Triggers catalog synchronization if authentication succeeds.
        """
        reg = self.env['nexora.provider.registry'].search([('provider_id', '=', provider_id)], limit=1)
        if not reg:
            raise UserError(f"Provider {provider_id} not found in registry.")
            
        adapter = self.get_adapter(provider_id)
        
        # Resolve provider configuration into an immutable dataclass
        provider_input = adapter.resolve_provider_input(reg=reg)
        
        # Execute health check
        diagnostic = adapter.health_check(provider_input)
        
        vals = {
            'connectivity_state': diagnostic.connectivity_state,
            'auth_state': diagnostic.authentication_state,
            'latency_ms': diagnostic.latency_ms,
            'health_status': diagnostic.failure_reason if diagnostic.failure_reason else 'OK',
            'last_checked': fields.Datetime.now()
        }
        
        if diagnostic.authentication_state == 'no_key':
            vals['config_state'] = 'missing_key'
        elif diagnostic.config_valid:
            vals['config_state'] = 'valid'
        else:
            vals['config_state'] = 'invalid'
            
        reg.write(vals)
        
        # If authenticated, trigger sync (if it supports sync, we trigger the catalog_service)
        if diagnostic.authentication_state == 'authenticated' and diagnostic.connectivity_state == 'reachable':
            try:
                self.env['nexora.ai_catalog_service'].sync_catalog(provider_id)
            except Exception as e:
                # catalog_service handles failure
                pass
                
        return {
            'config_valid': diagnostic.config_valid,
            'connectivity_state': diagnostic.connectivity_state,
            'authentication_state': diagnostic.authentication_state,
            'latency_ms': diagnostic.latency_ms,
            'failure_reason': diagnostic.failure_reason
        }
