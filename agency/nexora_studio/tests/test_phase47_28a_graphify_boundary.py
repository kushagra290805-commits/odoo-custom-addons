# -*- coding: utf-8 -*-
"""Phase 47.28A — Graphify integration boundary lock (audit conclusion).

The 47.28A audit established, from executable code and runtime evidence:
  * Graphify + services/graph_enrichment are DEV-TIME architectural
    governance tooling, invoked only through the manual CLI script
    run_graphify.py.
  * Nothing in the production generation path (Odoo loading, pipeline,
    engines, AI boundary) imports or invokes them.
  * The Graphify extraction in run_graphify.py skips semantic (LLM)
    extraction entirely — 0 AI tokens.
  * Consequently Graphify cannot contribute to any AI request token
    count, including the 921,292-token admission failure (the largest
    real generation request is ~516 input tokens).

These tests LOCK that boundary so a future change cannot silently wire
Graphify into the production generation path (which would reintroduce an
un-audited orchestration/context path) without this suite failing.
"""
import os
import re
import sys
import unittest

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo  # noqa: F401

# Production-reachable code: everything EXCEPT the dev-time scripts and the
# graph_enrichment package itself.
_DEV_ONLY_PREFIXES = (
    os.path.join('services', 'graph_enrichment') + os.sep,
    'scratch' + os.sep,
)
_DEV_ONLY_FILES = {
    'run_graphify.py',           # manual CLI entrypoint (dev tool)
    'restore_enrichers.py',      # dev-time file restoration script
    'audit_architecture.py', 'audit_builder.py', 'audit_callers.py',
    'audit_cycles.py', 'verify_phase1.py', 'verify_phase2_3.py',
    'verify_phase7.py', 'verify_queries.py',
    # Phase 47.28B: dev-tool tests exercise the dev tooling directly.
    os.path.join('tests', 'test_phase47_28b_graphify_query.py'),
}

_GRAPHIFY_RE = re.compile(r'graphify|graph_enrichment', re.I)


def _iter_production_files():
    for root, dirs, files in os.walk(ADDON_ROOT):
        dirs[:] = [d for d in dirs if d not in (
            '__pycache__', 'node_modules', 'dist', '.git', 'graphify-out')]
        rel_root = os.path.relpath(root, ADDON_ROOT)
        if rel_root == '.':
            pass
        else:
            rel_root += os.sep
        for f in files:
            rel = rel_root + f if rel_root != '.' else f
            if rel.replace('/', os.sep) in _DEV_ONLY_FILES:
                continue
            if any(rel.replace('/', os.sep).startswith(p)
                   for p in _DEV_ONLY_PREFIXES):
                continue
            if f.endswith('.py'):
                yield os.path.join(root, f), rel


class TestGraphifyProductionBoundary(unittest.TestCase):
    """No production-reachable module may reference Graphify."""

    def test_01_no_production_import_of_graphify(self):
        offenders = []
        for path, rel in _iter_production_files():
            src = open(path, encoding='utf-8', errors='ignore').read()
            for match in _GRAPHIFY_RE.finditer(src):
                # Only import/reference statements count — a comment
                # mentioning the audit is fine.
                line_start = src.rfind('\n', 0, match.start()) + 1
                line = src[line_start:src.find('\n', match.start())]
                if re.match(r'\s*(from|import)\s', line):
                    offenders.append('%s: %s' % (rel, line.strip()[:80]))
        self.assertEqual(
            offenders, [],
            'production code must not import Graphify (dev-time tool): %s'
            % offenders)

    def test_02_services_init_does_not_load_graph_enrichment(self):
        init = open(os.path.join(ADDON_ROOT, 'services', '__init__.py'),
                    encoding='utf-8').read()
        self.assertNotRegex(
            init, r'graph_enrichment',
            'services/__init__.py must not load the dev-time graph package')

    def test_03_manifest_has_no_graphify_entry(self):
        man = open(os.path.join(ADDON_ROOT, '__manifest__.py'),
                   encoding='utf-8').read()
        self.assertNotRegex(man, r'graphify',
                            'the Odoo manifest must not reference Graphify')

    def test_04_no_odoo_xml_data_integration(self):
        offenders = []
        for root, dirs, files in os.walk(ADDON_ROOT):
            dirs[:] = [d for d in dirs if d not in (
                '__pycache__', 'node_modules', 'graphify-out', 'dist')]
            for f in files:
                if f.endswith(('.xml', '.csv')):
                    p = os.path.join(root, f)
                    src = open(p, encoding='utf-8', errors='ignore').read()
                    if _GRAPHIFY_RE.search(src):
                        offenders.append(os.path.relpath(p, ADDON_ROOT))
        self.assertEqual(
            offenders, [],
            'no Odoo view/menu/cron/data record may reference Graphify: %s'
            % offenders)

    def test_05_generation_path_is_clean(self):
        """The canonical generation chain imports no graph framework."""
        gen_dir = os.path.join(ADDON_ROOT, 'services', 'generation')
        offenders = []
        for root, dirs, files in os.walk(gen_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    p = os.path.join(root, f)
                    src = open(p, encoding='utf-8', errors='ignore').read()
                    if re.search(r'^\s*(from|import)\s+.*graphify', src,
                                 re.M | re.I):
                        offenders.append(os.path.relpath(p, ADDON_ROOT))
        self.assertEqual(
            offenders, [],
            'the generation pipeline must not import Graphify: %s'
            % offenders)

    def test_06_run_graphify_is_dev_only(self):
        """The CLI entrypoint exists but references no AI provider path."""
        script = os.path.join(ADDON_ROOT, 'run_graphify.py')
        src = open(script, encoding='utf-8').read()
        # The script must keep skipping semantic (LLM) extraction.
        self.assertIn('Skipping Semantic Extraction', src)
        self.assertNotRegex(src, r'ai_provider_manager|AIProviderManager')
        # And nothing production-side imports the script itself.
        importers = []
        for path, rel in _iter_production_files():
            s = open(path, encoding='utf-8', errors='ignore').read()
            if re.search(r'^\s*(from|import)\s+.*run_graphify', s, re.M):
                importers.append(rel)
        self.assertEqual(importers, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
