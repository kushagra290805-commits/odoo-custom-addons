# -*- coding: utf-8 -*-
"""Standalone regression runner for suites touched by Phase 47.36
(component library, rendering provider, codegen quality, capabilities)."""
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
    'test_component_synthesis',
    'test_component_manifest',
    'test_react_provider',
    'test_react_rendering_provider',
    'test_interaction_builder',
    'test_interaction_translation',
    'test_phase47_25_native_activation',
    'test_phase47_27_structured_content',
    'test_phase47_28_client_quality',
    'test_phase47_29_client_quality',
    'test_phase47_32_capability_contract',
    'test_phase47_36_frontend_binding',
]
for mod in MODS:
    module = __import__(
        'odoo.addons.nexora_studio.tests.' + mod, fromlist=['__name__'])
    suite.addTests(loader.loadTestsFromModule(module))
runner = unittest.TextTestRunner(verbosity=0)
result = runner.run(suite)
failed = len(result.failures) + len(result.errors)
print('TOUCHED-SUITES RESULT: ran=%d failed=%d errors=%d'
      % (result.testsRun, len(result.failures), len(result.errors)))
for entry in (result.failures + result.errors):
    print('FAILED: %s :: %s' % (entry[0], str(entry[1]).splitlines()[-1][:160]))
sys.exit(0 if failed == 0 else 1)
