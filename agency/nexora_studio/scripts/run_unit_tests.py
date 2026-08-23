# -*- coding: utf-8 -*-
"""
Run the registered UNIT test suites (plain unittest, mocks only, no DB writes)
against a fully loaded Odoo registry.

Usage:
    python scripts/run_unit_tests.py [-c <odoo.conf>] [-d <database>]

The UNIT classification and registration live in tests/__init__.py. Plain
unittest.TestCase classes are invisible to the odoo-bin tag selector, so the
suite is executed with the stdlib runner after the registry has loaded (which
makes `odoo.addons.nexora_studio...` importable), following the pattern of
scripts/test_boot.py.

Exit code 0 = all tests passed.
"""
import argparse
import sys
import unittest

DEFAULT_MODULES = [
    # --- UNIT (tests/__init__.py registration order) ---
    'test_mcp_sse_generic_transport',
    'test_firecrawl_integration',
    'test_encryption_key_config',
    'test_lifecycle_bootstrap',
    'test_routing_isolation',
    'test_auth_service_unit',
    'test_permission_service',
    'test_component_synthesis',
    'test_component_manifest',
    'test_design_system_engine',
    'test_design_token_binding',
    'test_interaction_builder',
    'test_design_blueprint_engine',
    'test_layout_composition',
    'test_asset_content_engine',
    'test_layout_engine',
    'test_accessibility_behavior',
    'test_pipeline_contract_validation',
    'test_props_generation',
    'test_react_provider',
    'test_react_rendering_provider',
    'test_provider_registry',
    'test_provider_interface',
    'test_render_model_validation',
    'test_interaction_translation',
    'test_phase44_2_hardening',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default=r'D:\ODOO\configs\cert.conf')
    parser.add_argument('-d', '--database', default='nexora_cert')
    parser.add_argument('--modules', nargs='*', default=DEFAULT_MODULES)
    args = parser.parse_args()

    sys.path.insert(0, r'D:\ODOO\community\odoo')
    import odoo
    import odoo.tools
    import odoo.modules.registry
    odoo.tools.config.parse_config(['-c', args.config, '-d', args.database])
    # Loading the registry initialises the addons path so that
    # `odoo.addons.nexora_studio` becomes importable.
    odoo.modules.registry.Registry(args.database)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    errors = []
    for module_name in args.modules:
        qualified = f'odoo.addons.nexora_studio.tests.{module_name}'
        try:
            module = __import__(qualified, fromlist=['__name__'])
        except Exception as exc:  # import failure is a suite error, not a skip
            errors.append(f'{module_name}: IMPORT FAILED: {type(exc).__name__}: {exc}')
            continue
        suite.addTests(loader.loadTestsFromModule(module))

    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    for line in errors:
        print('SUITE-ERROR:', line)
    failed = len(result.failures) + len(result.errors) + len(errors)
    print(f'UNIT SUITE RESULT: ran={result.testsRun} failed={len(result.failures)} '
          f'errors={len(result.errors)} import_errors={len(errors)}')
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
