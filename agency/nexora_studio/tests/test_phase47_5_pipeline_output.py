"""Focused source-contract tests for Phase 47.5 U5."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase475PipelineOutputTests(unittest.TestCase):
    def _source(self, relative_path):
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def test_content_engine_is_one_pipeline_stage(self):
        source = self._source('services/generation/pipeline/website_generation_pipeline.py')
        self.assertEqual(source.count('ContentEngine(orchestrator)'), 1)
        self.assertIn('GenerationState.CONTENT_GENERATED', source)

    def test_requirements_preserve_existing_fields(self):
        source = self._source('services/generation/engines/requirement_engine.py')
        self.assertIn('existing = artifact.requirements', source)
        for field in ('branding', 'seo', 'accessibility', 'goals', 'features'):
            self.assertIn(f'existing.{field}', source)

    def test_workspace_uses_runtime_root(self):
        source = self._source('services/generation/engines/workspace_generator_engine.py')
        self.assertIn('workspace_path = str(runtime.workspace.root)', source)
        self.assertNotIn('/sandboxed/workspace', source)

    def test_generated_app_wires_generated_pages(self):
        source = self._source('services/generation/engines/code_generation_engine.py')
        self.assertIn("self._apply_patch('src/App.jsx'", source)
        self.assertIn("window.location.pathname", source)
        self.assertIn("import {module_name} from './pages/{filename}'", source)

    def test_required_file_write_failures_propagate(self):
        source = self._source('services/generation/engines/code_generation_engine.py')
        self.assertIn('raise RuntimeError(f"Failed to apply required generated file {path}: {e}")', source)
        self.assertNotIn('except Exception as e:\n            _logger.error(f"Failed to apply patch to {path}: {e}")\n\n', source)

    def test_changed_python_files_parse(self):
        for relative_path in (
            'services/generation/core/generation_context.py',
            'services/generation/pipeline/website_generation_pipeline.py',
            'services/generation/engines/requirement_engine.py',
            'services/generation/engines/workspace_generator_engine.py',
            'services/generation/engines/code_generation_engine.py',
        ):
            ast.parse(self._source(relative_path), filename=relative_path)


if __name__ == '__main__':
    unittest.main()
