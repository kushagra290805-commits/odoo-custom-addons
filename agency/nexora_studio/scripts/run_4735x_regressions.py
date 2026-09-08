# -*- coding: utf-8 -*-
"""Standalone runner for the Phase 47.35.x regression matrix (plain
unittest suites that need the Odoo addons path initialized).

Mirrors the established preamble of tests/test_phase47_32_capability_contract.py.
"""
import sys
import unittest

sys.path.insert(0, r'D:\ODOO\community\odoo')
from odoo.tools import config
import odoo.modules.module as m
config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()
import odoo
odoo.modules.registry.Registry('nexora_studio')

loader = unittest.TestLoader()
suite = unittest.TestSuite()
MODS = [
    'test_phase47_5_pipeline_behavior',
    'test_phase47_7_artifact_consumers',
]
for mod in MODS:
    module = __import__(
        'odoo.addons.nexora_studio.tests.' + mod, fromlist=['__name__'])
    suite.addTests(loader.loadTestsFromModule(module))
runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)
failed = len(result.failures) + len(result.errors)
print('GENERATION REGRESSION RESULT: ran=%d failed=%d errors=%d'
      % (result.testsRun, len(result.failures), len(result.errors)))
sys.exit(0 if failed == 0 else 1)
