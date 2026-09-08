# -*- coding: utf-8 -*-
"""Standalone runner for the Phase 47.36 frontend-binding test suite
(plain unittest suite; needs the Odoo addons path initialized).

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
module = __import__(
    'odoo.addons.nexora_studio.tests.test_phase47_36_frontend_binding',
    fromlist=['__name__'])
suite.addTests(loader.loadTestsFromModule(module))
runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)
failed = len(result.failures) + len(result.errors)
print('PHASE 47.36 TEST RESULT: ran=%d failed=%d errors=%d'
      % (result.testsRun, len(result.failures), len(result.errors)))
sys.exit(0 if failed == 0 else 1)
