# -*- coding: utf-8 -*-
"""Standalone regression runner for the Phase 47.36 regression matrix:
the standalone-script 47.3x suites (boundary, capability, BFF routes, WS
auth) that live outside the Odoo tag-discovery flow, plus the new
Phase 47.36 frontend-binding suite and the generation regressions.

Mirrors scripts/run_4735x_regressions.py.
"""
import sys
import unittest

sys.path.insert(0, r'D:\ODOO\community\odoo')
from odoo.tools import config
import odoo.modules.module as m
config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()
import odoo

loader = unittest.TestLoader()
suite = unittest.TestSuite()
MODS = [
    'test_phase47_31_api_boundary',
    'test_phase47_32_capability_contract',
    'test_phase47_35_bff_client_routes',
    'test_phase47_35x_ws_auth',
    'test_phase47_5_pipeline_behavior',
    'test_phase47_7_artifact_consumers',
    'test_phase47_36_frontend_binding',
]
for mod in MODS:
    module = __import__(
        'odoo.addons.nexora_studio.tests.' + mod, fromlist=['__name__'])
    suite.addTests(loader.loadTestsFromModule(module))
runner = unittest.TextTestRunner(verbosity=0)
result = runner.run(suite)
failed = len(result.failures) + len(result.errors)
print('STANDALONE REGRESSION RESULT: ran=%d failed=%d errors=%d'
      % (result.testsRun, len(result.failures), len(result.errors)))
for entry in (result.failures + result.errors):
    print('FAILED: %s :: %s'
          % (entry[0], str(entry[1]).splitlines()[-1][:160]))
sys.exit(0 if failed == 0 else 1)
