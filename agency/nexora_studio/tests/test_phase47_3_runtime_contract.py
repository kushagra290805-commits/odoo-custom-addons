"""Focused source-contract tests for Phase 47.3 U3."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase473RuntimeContractTests(unittest.TestCase):
    def _source(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def test_runtime_accepts_explicit_environment_without_http_request(self):
        source = self._source('services/generation/core/generation_runtime.py')
        self.assertIn('env: Any = None', source)
        self.assertIn('self.env = env', source)
        self.assertNotIn('from odoo.http import request', source)
        self.assertNotIn('request.env', source)

    def test_coordinator_injects_environment_explicitly(self):
        source = self._source('services/generation/core/generation_coordinator.py')
        self.assertIn('env=getattr(self.orchestrator, \'env\', None)', source)

    def test_planning_engine_reuses_runtime_router(self):
        source = self._source('services/generation/engines/planning_engine.py')
        self.assertNotIn('UniversalCapabilityRouter(', source)
        self.assertNotIn('LocalToolExecutor(', source)
        self.assertIn('runtime.orchestrator.execute_prepared_plan(plan)', source)
        adapter = self._source('services/generation/core/runtime_interfaces.py')
        self.assertIn('def execute_prepared_plan', adapter)
        self.assertIn('CapabilitySelectionEngine(self._resolver, self._router)', adapter)

    def test_component_discovery_uses_declared_runtime_environment(self):
        source = self._source('services/generation/engines/component_discovery_engine.py')
        self.assertIn('env = runtime.env', source)
        self.assertNotIn('runtime.orchestrator.env', source)
        runtime = self._source('services/generation/core/generation_runtime.py')
        self.assertIn("self._registry.register(ComponentDiscoveryEngine, {'env'})", runtime)

    def test_only_generation_runtime_constructs_router(self):
        runtime = self._source('services/generation/core/generation_runtime.py')
        planning = self._source('services/generation/engines/planning_engine.py')
        self.assertEqual(runtime.count('UniversalCapabilityRouter('), 1)
        self.assertNotIn('UniversalCapabilityRouter(', planning)

    def test_pipeline_engine_scopes_match_runtime_access(self):
        runtime = self._source('services/generation/core/generation_runtime.py')
        expected = (
            "self._registry.register(PlanningEngine, {'orchestrator'})",
            "self._registry.register(ComponentDiscoveryEngine, {'env'})",
            "self._registry.register(TemplateResolutionEngine, {'env'})",
            "self._registry.register(CodeGenerationEngine, {'ai', 'workspace', 'tools'})",
            "self._registry.register(ValidationEngine, {'env', 'orchestrator'})",
        )
        for declaration in expected:
            self.assertIn(declaration, runtime)

        template = self._source('services/generation/engines/template_resolution_engine.py')
        validation = self._source('services/generation/engines/validation_engine.py')
        self.assertIn('env = runtime.env', template)
        self.assertIn("runtime.env['nexora.design_orchestrator']", validation)
        self.assertNotIn('self.orchestrator.env', template)
        self.assertNotIn('self.orchestrator.env', validation)

    def test_changed_python_files_parse(self):
        for relative_path in (
            'services/generation/core/generation_runtime.py',
            'services/generation/core/generation_coordinator.py',
            'services/generation/core/runtime_interfaces.py',
            'services/generation/engines/planning_engine.py',
            'services/generation/engines/component_discovery_engine.py',
            'services/generation/engines/template_resolution_engine.py',
            'services/generation/engines/validation_engine.py',
        ):
            ast.parse(self._source(relative_path), filename=relative_path)


if __name__ == '__main__':
    unittest.main()
