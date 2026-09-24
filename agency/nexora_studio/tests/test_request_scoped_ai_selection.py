"""Request-scoped selection contracts; no database writes or live HTTP calls."""
import sys
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, r'D:\ODOO\community\odoo')
from odoo.tools import config
from odoo.modules import module

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
module.initialize_sys_path()
from odoo.exceptions import UserError
from odoo.addons.nexora_studio.services.ai.ai_execution_context import AIExecutionContext
from odoo.addons.nexora_studio.services.ai.cost_router import CostRouter
from odoo.addons.nexora_studio.services.ai.provider_manager import AIProviderManager
from odoo.addons.nexora_studio.services.ai.provider_execution_policy import (
    ProviderExecutionPolicy, RateLimitException)
from odoo.addons.nexora_studio.services.generation.core.runtime_interfaces import AIRuntimeAdapter


class Env(dict):
    context = {}


class TestRequestScopedSelection(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.params = MagicMock()
        self.params.sudo.return_value.get_param.return_value = 'False'
        self.env['ir.config_parameter'] = self.params
        self.registry = MagicMock()
        self.registry.search.return_value.is_active = True
        self.env['nexora.provider.registry'] = self.registry
        self.config = MagicMock()
        self.config.validate_configuration.return_value = {'valid': True, 'errors': []}
        self.config.get_active_model.return_value = 'default-model'
        self.config.get_provider_credentials.return_value = {'api_key': 'test-only', 'base_url': 'https://example.invalid/v1'}
        self.config.resolve_model_record.return_value.capability_ids.mapped.return_value = ['chat']
        self.env['nexora.ai_configuration_service'] = self.config
        self.env['nexora.provider_health_service'] = MagicMock()
        self.adapters = {key: MagicMock() for key in ('openrouter', 'experiential_labs', 'test')}
        for adapter in self.adapters.values():
            adapter.is_available.return_value = True
            adapter.chat_completion.return_value = {'response': 'OK', 'error': None}
        self.pm = SimpleNamespace(env=self.env)
        self.pm._get_adapters = lambda: dict(self.adapters)
        self.pm.get_adapter = lambda key: self.adapters[key]
        self.pm.get_available_providers = lambda: [{'key': key, 'available': True} for key in self.adapters]
        self.pm.validate_model = MagicMock()
        self.pm._record_telemetry = MagicMock()
        self.pm.route_request = MethodType(AIProviderManager.route_request, self.pm)
        self.env['nexora.ai_provider_manager'] = self.pm
        self.router = SimpleNamespace(env=self.env, classify_task=lambda task: 'medium',
                                      get_fallback_chain=MagicMock(return_value=['openrouter']))
        self.router.resolve_provider = MethodType(CostRouter.resolve_provider, self.router)
        self.env['nexora.ai_cost_router'] = self.router
        self.policy = MagicMock()
        self.policy.execute.side_effect = lambda ctx, fn: fn(ctx.timeout)
        self.env['nexora.provider_execution_policy'] = self.policy
        self.runtime = AIRuntimeAdapter(self.pm)
        self.payload = {'prompt': 'Reply OK.', 'provider': 'experiential_labs',
                        'model': 'glm-5.3-flash', 'max_tokens': 8, 'retries': 0}
        self.override = patch.dict('os.environ', {'NEXORA_TEST_PROVIDER': ''})
        self.override.start()
        self.addCleanup(self.override.stop)

    def test_explicit_chain_uses_only_selected_adapter_and_model(self):
        result = self.runtime.generate('generate_content', self.payload)
        self.assertEqual(result['provider'], 'experiential_labs')
        self.assertEqual(result['model'], 'glm-5.3-flash')
        self.assertFalse(result['fallback_occurred'])
        call = self.adapters['experiential_labs'].chat_completion.call_args
        self.assertEqual(call.kwargs['model'], 'glm-5.3-flash')
        self.assertEqual(call.args[0][-1]['content'], 'Reply OK.')
        self.router.get_fallback_chain.assert_not_called()
        self.adapters['openrouter'].chat_completion.assert_not_called()
        self.adapters['test'].chat_completion.assert_not_called()
        self.config.get_active_model.assert_not_called()
        self.registry.write.assert_not_called()
        self.params.sudo.return_value.set_param.assert_not_called()

    def test_no_selection_preserves_default_and_does_not_persist_pin(self):
        self.runtime.generate('generate_content', self.payload)
        result = self.runtime.generate('generate_content', {'prompt': 'Default'})
        self.assertNotIn('fallback_occurred', result)
        self.assertEqual(self.adapters['openrouter'].chat_completion.call_args.kwargs['model'], 'default-model')
        self.router.get_fallback_chain.assert_called_once()

    def test_partial_or_invalid_selection_rejected(self):
        for provider, model in [('experiential_labs', ''), ('', 'glm-5.3-flash'),
                                (' ', 'glm-5.3-flash'), ([], 'glm-5.3-flash')]:
            with self.subTest(provider=provider, model=model), self.assertRaises(Exception):
                self.runtime.generate('generate_content', dict(self.payload, provider=provider, model=model))
        self.policy.execute.assert_not_called()

    def test_unknown_provider_rejected(self):
        with self.assertRaises(Exception):
            self.runtime.generate('generate_content', dict(self.payload, provider='unknown'))
        self.policy.execute.assert_not_called()

    def test_disabled_provider_rejected(self):
        self.registry.search.return_value.is_active = False
        with self.assertRaises(Exception):
            self.runtime.generate('generate_content', self.payload)
        self.policy.execute.assert_not_called()

    def test_missing_registry_rejected(self):
        self.registry.search.return_value = False
        with self.assertRaises(Exception):
            self.runtime.generate('generate_content', self.payload)
        self.policy.execute.assert_not_called()

    def test_bad_key_unknown_inactive_or_cross_provider_model_rejected(self):
        for message in ('missing key', 'model not in provider catalog', 'inactive model'):
            self.config.validate_configuration.return_value = {'valid': False, 'errors': [{'message': message}]}
            with self.subTest(message=message), self.assertRaises(Exception):
                self.runtime.generate('generate_content', self.payload)
        self.config.validate_configuration.assert_called_with('experiential_labs', 'glm-5.3-flash')
        self.policy.execute.assert_not_called()

    def test_unavailable_provider_rejected(self):
        self.adapters['experiential_labs'].is_available.return_value = False
        with self.assertRaises(Exception):
            self.runtime.generate('generate_content', self.payload)
        self.policy.execute.assert_not_called()

    def test_required_capabilities_apply_to_exact_requested_model(self):
        self.pm.route_request('chat', 'OK', dict(self.payload, required_capabilities=['chat']))
        self.config.resolve_model_record.assert_called_with('experiential_labs', 'glm-5.3-flash')
        with self.assertRaises(UserError):
            self.pm.route_request('chat', 'OK', dict(self.payload, required_capabilities=['vision']))
        self.assertEqual(self.policy.execute.call_count, 1)

    def test_explicit_context_supported(self):
        self.pm.route_request('chat', 'OK', ctx=AIExecutionContext(
            provider='experiential_labs', model='glm-5.3-flash'))
        self.adapters['experiential_labs'].chat_completion.assert_called_once()

    def test_conflicting_context_rejected(self):
        with self.assertRaises(UserError):
            self.pm.route_request('chat', 'OK', self.payload,
                                  ctx=AIExecutionContext(provider='openrouter', model='other'))
        self.policy.execute.assert_not_called()

    def test_test_override_or_test_pin_rejected(self):
        with patch.dict('os.environ', {'NEXORA_TEST_PROVIDER': 'test'}), self.assertRaises(Exception):
            self.runtime.generate('chat', self.payload)
        with self.assertRaises(Exception):
            self.runtime.generate('chat', dict(self.payload, provider='test'))
        self.policy.execute.assert_not_called()

    def test_unified_path_cannot_silently_ignore_pin(self):
        self.params.sudo.return_value.get_param.return_value = 'True'
        with self.assertRaisesRegex(Exception, 'CostRouter'):
            self.runtime.generate('chat', self.payload)
        self.policy.execute.assert_not_called()

    def test_explicit_rate_limit_or_transport_exception_never_falls_back(self):
        for exc in (RateLimitException('limited'), RuntimeError('network failed')):
            self.policy.execute.side_effect = exc
            with self.subTest(exc=type(exc).__name__), self.assertRaises(Exception):
                self.runtime.generate('chat', self.payload)
        self.assertEqual(self.policy.execute.call_count, 2)
        self.adapters['openrouter'].chat_completion.assert_not_called()

    def test_explicit_error_result_preserved_without_fallback(self):
        self.policy.execute.side_effect = None
        self.policy.execute.return_value = {'error': 'request failed', 'http_status': 401}
        result = self.runtime.generate('chat', self.payload)
        self.assertEqual(result['http_status'], 401)
        self.assertTrue(result['error'])
        self.assertFalse(result['fallback_occurred'])
        self.policy.execute.assert_called_once()

    def test_adapter_error_cannot_be_recast_as_success_by_policy(self):
        self.adapters['experiential_labs'].chat_completion.return_value = {'error': 'bad request'}
        with self.assertRaises(Exception):
            self.runtime.generate('chat', self.payload)
        self.adapters['openrouter'].chat_completion.assert_not_called()

    def test_default_rate_limit_fallback_stays_unpinned(self):
        def execute(ctx, fn):
            if ctx.provider == 'openrouter':
                raise RateLimitException('limited')
            return fn(ctx.timeout)
        self.policy.execute.side_effect = execute
        self.runtime.generate('chat', {'prompt': 'Default'})
        self.assertEqual(self.policy.execute.call_count, 2)
        self.assertEqual(self.router.get_fallback_chain.call_count, 2)
        self.adapters['experiential_labs'].chat_completion.assert_called_once()

    def test_real_execution_policy_transport_failure_is_closed(self):
        policy = SimpleNamespace(_is_circuit_open=lambda p: False,
                                 _record_success=lambda p: None,
                                 _record_failure=lambda p: None,
                                 _build_error=ProviderExecutionPolicy._build_error)
        policy._build_error = MethodType(ProviderExecutionPolicy._build_error, policy)
        policy.execute = MethodType(ProviderExecutionPolicy.execute, policy)
        self.env['nexora.provider_execution_policy'] = policy
        self.adapters['experiential_labs'].chat_completion.side_effect = RuntimeError('transport failed')
        result = self.runtime.generate('chat', self.payload)
        self.assertTrue(result['error'])
        self.assertFalse(result['fallback_occurred'])
        self.adapters['experiential_labs'].chat_completion.assert_called_once()
        self.adapters['openrouter'].chat_completion.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
