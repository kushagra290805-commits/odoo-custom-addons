"""Focused source-contract tests for Phase 47.2 U1/U2 closure."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase472WorkflowClosureTests(unittest.TestCase):
    def _source(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def test_production_entry_calls_builder_generation_service(self):
        source = self._source('controllers/ai_api.py')
        self.assertIn("request.env['nexora.builder_session_service']", source)
        self.assertIn('.run_generation(', source)
        self.assertNotIn("project_planner_service'].with_context", source)

    def test_generation_accepts_request_requirements(self):
        source = self._source('controllers/ai_api.py')
        service = self._source('services/builder_session_service.py')
        self.assertIn("payload.get('requirements')", source)
        self.assertIn('requirements=None', service)
        self.assertIn('raw_requirements = requirements', service)

    def test_fresh_session_uses_preparing_before_generating(self):
        source = self._source('services/builder_session_service.py')
        preparing = source.index("self.transition_state(session, 'preparing'")
        generating = source.index("self.transition_state(session, 'generating'")
        self.assertLess(preparing, generating)
        self.assertIn("if session.status == 'draft':", source)

    def test_workspace_fallback_is_removed(self):
        coordinator = self._source('services/generation/core/generation_coordinator.py')
        service = self._source('services/builder_session_service.py')
        self.assertNotIn('/tmp/fallback', coordinator)
        self.assertIn('_ensure_generation_workspace', service)
        self.assertIn('workspace.action_initialize_workspace()', service)
        self.assertIn('nexora_builder_session WHERE id = %s FOR UPDATE NOWAIT', service)

    def test_changed_python_files_parse(self):
        for relative_path in (
            'controllers/ai_api.py',
            'services/builder_session_service.py',
            'services/generation/core/generation_coordinator.py',
        ):
            ast.parse(self._source(relative_path), filename=relative_path)


if __name__ == '__main__':
    unittest.main()
