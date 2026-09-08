# -*- coding: utf-8 -*-
"""Phase 47.28B — Graphify query-interface tests (ADR-0026 role extension).

Covers the OpenCode repository-intelligence boundary contract:
  * bounded results (limit + max-chars — never a graph/context dump)
  * deterministic, correct queries against the real AST graph
  * staleness detection + honest not-in-index reporting
  * no file contents / secrets in output (structure only)
  * the extraction sanity floor guarding run_graphify.py partial runs
  * the production-boundary lock from 47.28A still holds (Graphify stays
    out of the Odoo generation path; the only integration surface is the
    developer invoking the CLI through the existing bash tool)
"""
import os
import subprocess
import sys
import unittest

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config  # noqa: E402
import odoo.modules.module as m  # noqa: E402

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo  # noqa: F402,E402

QUERY = os.path.join(ADDON_ROOT, 'graphify_query.py')
GRAPH = os.path.join(ADDON_ROOT, 'graphify-out', 'graph.json')


def _run(*args):
    r = subprocess.run(
        [sys.executable, QUERY] + list(args),
        capture_output=True, text=True, timeout=120,
        cwd=ADDON_ROOT,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    return r.returncode, (r.stdout or '') + (r.stderr or '')


class TestBoundedQueries(unittest.TestCase):

    def test_01_symbol_exact_location(self):
        code, out = _run('symbol', 'ContentEngine')
        self.assertEqual(code, 0)
        self.assertIn('services/generation/engines/content_engine.py', out)
        self.assertIn('ContentEngine', out)

    def test_02_callers_bounded(self):
        code, out = _run('callers', 'ContentEngine', '--limit', '5')
        self.assertEqual(code, 0)
        self.assertIn('website_generation_pipeline.py', out,
                      'the pipeline call site is found')
        self.assertIn('[5/', out, 'bounded result count reported')
        # Result lines carry the 'caller -> Symbol' shape; warning/note
        # lines (staleness etc.) are not results.
        results = [l for l in out.splitlines() if ' -> ' in l]
        self.assertLessEqual(len(results), 5, 'limit respected')
        self.assertGreaterEqual(len(results), 1)

    def test_03_output_char_cap(self):
        code, out = _run('callers', 'ContentEngine',
                         '--limit', '1000', '--max-chars', '300')
        self.assertEqual(code, 0)
        results = '\n'.join(l for l in out.splitlines() if ' -> ' in l)
        self.assertIn('char cap', out)
        self.assertLessEqual(len(results), 400,
                             'max-chars caps the result payload')

    def test_04_importers_and_deps(self):
        code, out = _run('importers', 'content_engine')
        self.assertEqual(code, 0)
        self.assertIn('services/generation/engines/__init__.py', out)

    def test_05_file_listing_bounded(self):
        code, out = _run('file', 'code_generation_engine', '--limit', '4')
        self.assertEqual(code, 0)
        self.assertIn('code_generation_engine.py', out)
        self.assertIn('[4/', out)

    def test_06_path_resolution(self):
        code, out = _run('path', 'builder_session', 'ai_provider_manager')
        self.assertEqual(code, 0)
        self.assertIn('->', out)
        self.assertIn('ai_provider_manager.py', out)

    def test_07_no_whole_graph_injection(self):
        """The graph is ~1MB+; a query must never dump it."""
        graph_size = os.path.getsize(GRAPH)
        code, out = _run('callers', 'ContentEngine', '--limit', '1000')
        self.assertEqual(code, 0)
        self.assertLess(len(out), graph_size // 50,
                        'query output must be a tiny slice, not the graph')

    def test_08_deterministic_output(self):
        _, out1 = _run('callers', 'ContentEngine', '--limit', '20')
        _, out2 = _run('callers', 'ContentEngine', '--limit', '20')
        self.assertEqual(out1, out2, 'identical query → identical result')

    def test_09_unknown_symbol_exits_nonzero(self):
        code, out = _run('symbol', 'NoSuchSymbolXYZ')
        self.assertNotEqual(code, 0)
        self.assertIn('no symbol', out)

    def test_10_output_is_structure_only(self):
        """Queries return labels/paths/lines — never file contents."""
        _, out = _run('symbol', 'ContentEngine')
        with open(os.path.join(ADDON_ROOT, 'services', 'generation',
                               'engines', 'content_engine.py'),
                  encoding='utf-8') as fh:
            source = fh.read()
        # No full source line (beyond the class statement) may leak.
        for line in source.splitlines()[70:120]:
            stripped = line.strip()
            if len(stripped) > 40:
                self.assertNotIn(stripped, out)


class TestStalenessAndCoverage(unittest.TestCase):

    def test_11_status_reports_staleness_fields(self):
        code, out = _run('status')
        self.assertEqual(code, 0)
        self.assertIn('staleness:', out)
        self.assertIn('coverage:', out)
        self.assertIn('known limits:', out)

    def test_12_not_in_index_reports_refresh(self):
        code, out = _run('file', 'no_such_file_xyz')
        self.assertNotEqual(code, 0)
        self.assertIn('no file matching', out)

    def test_13_stale_graph_warns_loudly(self):
        """A graph older than the newest source change must warn."""
        sys.path.insert(0, ADDON_ROOT)
        import graphify_query as gq
        import time
        g = gq.Graph()
        g.built_at = time.time() - 3600  # simulate a 1h-old graph
        stale, detail = gq.staleness(g)
        self.assertTrue(stale)
        self.assertIn('min older', detail)


class TestRunnerHardening(unittest.TestCase):

    def test_14_sanity_floor_present(self):
        src = open(os.path.join(ADDON_ROOT, 'run_graphify.py'),
                   encoding='utf-8').read()
        self.assertIn('FLOOR', src, 'extraction sanity floor guards partial runs')
        self.assertIn('force=True', src,
                      'full rebuild writes through the shrink-refusal guard')

    def test_15_no_llm_semantic_extraction(self):
        src = open(os.path.join(ADDON_ROOT, 'run_graphify.py'),
                   encoding='utf-8').read()
        self.assertIn('Skipping Semantic Extraction', src)
        self.assertNotIn('ai_provider_manager', src)


class TestProductionBoundaryHolds(unittest.TestCase):
    """47.28A lock: the query tool is dev-only; the generation path stays
    clean. The CLI must not import anything from the Odoo generation
    stack, and the generation stack must not import it."""

    def test_16_query_tool_has_no_odoo_generation_imports(self):
        import re
        src = open(QUERY, encoding='utf-8').read()
        # Strip comments/docstrings: only IMPORT statements count (the
        # docstring legitimately mentions example query targets).
        code_only = re.sub(r'"""(?:.|\n)*?"""', '', src)
        code_only = re.sub(r'#.*', '', code_only)
        for banned in ('odoo', 'generation_coordinator',
                       'ai_provider_manager', 'content_engine',
                       'code_generation_engine'):
            self.assertFalse(
                re.search(r'^\s*(from|import)\s+\S*%s' % banned,
                          code_only, re.M),
                'query tool must stay independent of the generation stack '
                '(%s)' % banned)

    def test_17_generation_stack_does_not_import_query_tool(self):
        import re
        gen_dir = os.path.join(ADDON_ROOT, 'services', 'generation')
        offenders = []
        for root, dirs, files in os.walk(gen_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    p = os.path.join(root, f)
                    s = open(p, encoding='utf-8', errors='ignore').read()
                    if re.search(r'graphify', s, re.I):
                        offenders.append(os.path.relpath(p, ADDON_ROOT))
        self.assertEqual(offenders, [],
                         'generation path must not reference graphify')


if __name__ == '__main__':
    unittest.main(verbosity=2)
