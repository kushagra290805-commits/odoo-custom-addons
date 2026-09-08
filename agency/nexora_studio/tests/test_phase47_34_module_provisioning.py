# -*- coding: utf-8 -*-
"""Phase 47.34 — Odoo Module Provisioning & Capability Mapping tests.

Covers: capability→module policy determinism, allowlist security, module
plan contract, availability semantics, installation idempotency, partial
failure recovery, agency-DB isolation, and duplicate-request behavior.

The real Odoo installation primitive (``Registry.new(..., install_modules=...)``)
is mocked in these transactional tests — Odoo forbids module operations inside
tests because they are not transactional. Real installation is proven by the
standalone E2E script ``scripts/verify_phase47_34.py`` against a disposable
client database.
"""
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

from odoo.addons.nexora_studio.controllers.client_provisioning_api import (
    parse_module_provisioning_payload,
)
from odoo.addons.nexora_studio.services.client_environment_service import (
    ClientEnvironmentService,
)
from odoo.addons.nexora_studio.services.design.module_policy import (
    CAPABILITY_MODULE_ALLOWLIST,
    UNMAPPED_CAPABILITY_REASONS,
    ModulePolicyError,
    approved_module_names,
    build_module_plan,
    is_module_allowed,
)


class FakeModuleRecord:
    def __init__(self, name, state):
        self.name = name
        self.state = state


class FakeModuleModel:
    def __init__(self, records):
        self._records = records

    def update_list(self):
        return True

    def search(self, domain):
        names = domain[0][2]
        return [r for r in self._records if r.name in names]


def _installer_patch(**kwargs):
    # Patch the source Python class: the registry-generated model class
    # inherits from it, so every instance sees the patched method.
    return patch.object(ClientEnvironmentService, '_install_modules_in_client_db', **kwargs)


def _reader_patch(**kwargs):
    return patch.object(ClientEnvironmentService, '_read_client_module_states', **kwargs)


@tagged('post_install', '-at_install')
class TestModulePolicy(TransactionCase):
    """Deterministic capability → module policy (platform-owned data)."""

    def test_supported_capability_maps_to_approved_module(self):
        plan = build_module_plan(['orders'])
        self.assertEqual(
            [m['name'] for m in plan['modules']], ['sale_management']
        )
        entry = plan['modules'][0]
        self.assertEqual(entry['source_capabilities'], ['orders'])
        self.assertTrue(entry['required'])
        self.assertTrue(entry['supported'])
        self.assertTrue(entry['reason'])

    def test_unknown_capability_rejected(self):
        with self.assertRaises(ModulePolicyError):
            build_module_plan(['unknown_feature'])

    def test_llm_module_identifier_is_not_a_capability(self):
        # An LLM producing a technical module name as "capability" is rejected.
        with self.assertRaises(ModulePolicyError):
            build_module_plan(['sale_management'])

    def test_arbitrary_module_name_rejected_by_allowlist(self):
        self.assertFalse(is_module_allowed('some_arbitrary_module'))
        self.assertFalse(is_module_allowed('base'))
        self.assertTrue(is_module_allowed('sale_management'))
        self.assertIn('sale_management', approved_module_names())

    def test_mapping_is_deterministic(self):
        first = build_module_plan(['orders', 'products', 'customers'])
        second = build_module_plan(['customers', 'orders', 'products'])
        self.assertEqual(first, second)

    def test_duplicate_capability_normalization(self):
        plan = build_module_plan(['orders', 'orders', 'orders'])
        self.assertEqual(plan['capabilities'], ['orders'])
        self.assertEqual(len(plan['modules']), 1)

    def test_duplicate_module_elimination(self):
        plan = build_module_plan(['customers', 'contacts'])
        names = [m['name'] for m in plan['modules']]
        self.assertEqual(names, ['contacts'])
        # Capabilities are normalized (sorted), then merged into the module.
        self.assertEqual(
            plan['modules'][0]['source_capabilities'], ['contacts', 'customers']
        )

    def test_unmapped_capabilities_explicit(self):
        plan = build_module_plan(['orders', 'subscriptions', 'appointments'])
        self.assertEqual(
            [m['name'] for m in plan['modules']], ['sale_management']
        )
        unresolved = {u['capability'] for u in plan['unresolved_capabilities']}
        self.assertEqual(unresolved, {'subscriptions', 'appointments'})
        for entry in plan['unresolved_capabilities']:
            self.assertIn(entry['capability'], UNMAPPED_CAPABILITY_REASONS)
            self.assertTrue(entry['reason'])
        self.assertTrue(plan['supported'])

    def test_only_unmapped_capabilities_yields_unsupported_plan(self):
        plan = build_module_plan(['bookings'])
        self.assertEqual(plan['modules'], [])
        self.assertFalse(plan['supported'])
        self.assertEqual(
            plan['unresolved_capabilities'][0]['capability'], 'bookings'
        )

    def test_plan_schema_versioned(self):
        plan = build_module_plan(['orders'])
        self.assertTrue(plan['schema_version'])

    def test_allowlist_only_contains_vocabulary_capabilities(self):
        # Every allowlisted capability must be part of the Phase 47.32
        # controlled vocabulary (no arbitrary capabilities accepted).
        from odoo.addons.nexora_studio.services.design.capability_policy import (
            CAPABILITY_VOCABULARY,
        )
        for capability in CAPABILITY_MODULE_ALLOWLIST:
            self.assertIn(capability, CAPABILITY_VOCABULARY)
        for capability in UNMAPPED_CAPABILITY_REASONS:
            self.assertIn(capability, CAPABILITY_VOCABULARY)

    def test_non_string_capability_rejected(self):
        with self.assertRaises(ModulePolicyError):
            build_module_plan([42])
        with self.assertRaises(ModulePolicyError):
            build_module_plan([None])


@tagged('post_install', '-at_install')
class TestModuleProvisioningFlow(TransactionCase):
    """provision_modules orchestration (installer mocked at the boundary)."""

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'Phase 47.34 Test Project',
            'status': 'draft',
        })
        self.service = self.env['nexora.client_environment_service']
        self.env_record = self.service.create_environment(
            self.project.id, 'ModProv Test'
        )
        self.env_record.status = 'ready'
        # The client DB does not physically exist in unit tests; the
        # canonical existence check is satisfied at the boundary.
        patcher = patch('odoo.service.db.exp_db_exist', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _ok_outcome(self, installed, skipped):
        states = {n: 'installed' for n in installed + skipped}
        return {
            'installed': installed,
            'skipped': skipped,
            'not_installed': [],
            'pre_states': dict(states),
            'post_states': dict(states),
        }

    def test_provision_modules_happy_path(self):
        with _installer_patch(
            return_value=self._ok_outcome(['sale_management'], [])
        ) as mock_install:
            summary = self.service.provision_modules(
                self.env_record.id, ['orders']
            )
            mock_install.assert_called_once_with(
                self.env_record.db_name, ['sale_management']
            )
        self.assertEqual(summary['state'], 'provisioned')
        self.assertEqual(summary['installed'], ['sale_management'])
        self.assertEqual(self.env_record.module_provisioning_state, 'provisioned')
        self.assertFalse(self.env_record.module_provisioning_error)
        # DB lifecycle state must be untouched by module provisioning.
        self.assertEqual(self.env_record.status, 'ready')

    def test_plan_persisted_with_explanation(self):
        import json
        with _installer_patch(
            return_value=self._ok_outcome([], ['contacts'])
        ):
            self.service.provision_modules(self.env_record.id, ['customers'])
        plan = json.loads(self.env_record.module_plan)
        self.assertEqual(plan['schema_version'], '1.0')
        self.assertEqual(plan['modules'][0]['name'], 'contacts')
        self.assertEqual(plan['modules'][0]['source_capabilities'], ['customers'])
        self.assertTrue(plan['modules'][0]['reason'])
        self.assertTrue(plan['modules'][0]['required'])
        result = json.loads(self.env_record.module_provisioning_result)
        self.assertEqual(result['skipped'], ['contacts'])

    def test_idempotent_repeat_is_noop(self):
        with _installer_patch(
            side_effect=[
                self._ok_outcome(['sale_management'], []),
                self._ok_outcome([], ['sale_management']),
            ]
        ) as mock_install:
            first = self.service.provision_modules(self.env_record.id, ['orders'])
            second = self.service.provision_modules(self.env_record.id, ['orders'])
            self.assertEqual(mock_install.call_count, 2)
        self.assertEqual(first['state'], 'provisioned')
        self.assertEqual(second['state'], 'provisioned')
        self.assertEqual(second['installed'], [])
        self.assertEqual(second['skipped'], ['sale_management'])
        self.assertEqual(self.env_record.module_provisioning_state, 'provisioned')

    def test_unknown_capability_rejected_before_any_write(self):
        # Manual try/except: assertRaises' savepoint rollback would mask
        # whether the service itself performed any write.
        error = None
        with _installer_patch() as mock_install:
            try:
                self.service.provision_modules(self.env_record.id, ['unknown_feature'])
            except Exception as exc:
                error = exc
            mock_install.assert_not_called()
        self.assertIsNotNone(error)
        # Previously recorded provisioning state preserved (no write happened).
        self.assertEqual(self.env_record.module_provisioning_state, 'none')

    def test_unresolved_only_capability_is_honest_noop(self):
        with _installer_patch() as mock_install:
            summary = self.service.provision_modules(self.env_record.id, ['subscriptions'])
            mock_install.assert_not_called()
        self.assertEqual(summary['state'], 'provisioned')
        self.assertEqual(summary['installed'], [])
        self.assertEqual(self.env_record.module_provisioning_state, 'provisioned')

    def test_missing_environment_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.provision_modules(999999, ['orders'])

    def test_non_ready_environment_rejected(self):
        self.env_record.status = 'draft'
        with _installer_patch() as mock_install:
            with self.assertRaises(ValidationError):
                self.service.provision_modules(self.env_record.id, ['orders'])
            mock_install.assert_not_called()

    def test_deleted_environment_rejected(self):
        self.env_record.status = 'deleted'
        with self.assertRaises(ValidationError):
            self.service.provision_modules(self.env_record.id, ['orders'])

    def test_agency_db_cannot_be_selected(self):
        # Layer 1 (model constraint): re-pointing at the agency DB is
        # rejected at write time.
        with self.assertRaises(ValidationError):
            self.env_record.db_name = self.env.cr.dbname
        # Layer 2 (service guard): simulate corrupted data via SQL bypass;
        # module provisioning must refuse the agency DB.
        self.env.cr.execute(
            "UPDATE nexora_client_environment SET db_name = %s WHERE id = %s",
            [self.env.cr.dbname, self.env_record.id],
        )
        self.env_record.invalidate_recordset(['db_name'])
        with _installer_patch() as mock_install:
            with self.assertRaises(ValidationError):
                self.service.provision_modules(self.env_record.id, ['orders'])
            mock_install.assert_not_called()

    def test_missing_client_db_rejected(self):
        with patch(
            'odoo.service.db.exp_db_exist', return_value=False
        ), _installer_patch() as mock_install:
            with self.assertRaises(ValidationError):
                self.service.provision_modules(self.env_record.id, ['orders'])
            mock_install.assert_not_called()

    def test_installation_failure_observable_and_recoverable(self):
        # NOTE: manual try/except instead of assertRaises — Odoo's
        # assertRaises rolls back its savepoint on exception by design,
        # which would erase the observable failure state.
        error = None
        with _installer_patch(
            side_effect=ValidationError('Installation failed: sale_management')
        ), _reader_patch(
            return_value={'sale_management': 'uninstalled'}
        ):
            try:
                self.service.provision_modules(self.env_record.id, ['orders'])
            except Exception as exc:
                error = exc
        self.assertIsNotNone(error)
        self.assertEqual(self.env_record.module_provisioning_state, 'failed')
        self.assertIn('sale_management', self.env_record.module_provisioning_error)
        # DB lifecycle state must remain ready — recoverable, DB preserved.
        self.assertEqual(self.env_record.status, 'ready')

    def test_partial_installation_remains_recoverable(self):
        error = None
        with _installer_patch(
            side_effect=ValidationError('Module B failed')
        ), _reader_patch(
            return_value={'product': 'installed', 'sale_management': 'uninstalled'}
        ):
            try:
                self.service.provision_modules(
                    self.env_record.id, ['products', 'orders']
                )
            except Exception as exc:
                error = exc
        self.assertIsNotNone(error)
        self.assertEqual(self.env_record.module_provisioning_state, 'partial')
        self.assertEqual(self.env_record.status, 'ready')
        # Retry reconciles: product skipped, sale_management installed.
        with _installer_patch(
            return_value=self._ok_outcome(['sale_management'], ['product'])
        ):
            summary = self.service.provision_modules(
                self.env_record.id, ['products', 'orders']
            )
        self.assertEqual(summary['state'], 'provisioned')
        self.assertEqual(self.env_record.module_provisioning_state, 'provisioned')

    def test_duplicate_provisioning_request_no_conflicting_state(self):
        # Two sequential identical requests (the row lock serializes real
        # concurrent ones): the second observes installed modules and
        # completes as an idempotent no-op — no duplicate/broken state.
        with _installer_patch(
            side_effect=[
                self._ok_outcome(['crm'], []),
                self._ok_outcome([], ['crm']),
            ]
        ):
            self.service.provision_modules(self.env_record.id, ['leads'])
            summary = self.service.provision_modules(self.env_record.id, ['leads'])
        self.assertEqual(summary['skipped'], ['crm'])
        self.assertEqual(self.env_record.module_provisioning_state, 'provisioned')
        self.assertEqual(self.env_record.status, 'ready')


@tagged('post_install', '-at_install')
class TestPrivilegedInstaller(TransactionCase):
    """_install_modules_in_client_db: availability, idempotency, security.

    Registry/Environment are mocked at the odoo boundary (module operations
    are forbidden inside transactional Odoo tests).
    """

    def setUp(self):
        super().setUp()
        self.service = self.env['nexora.client_environment_service']
        self.client_db = 'nexora_installer_test'

    def _patches(self, pre_records, post_records=None, registry_new=None):
        def make_env(records):
            env_mock = MagicMock()
            env_mock.__getitem__.return_value = FakeModuleModel(records)
            return env_mock

        if post_records is None:
            post_records = pre_records
        env_factory = MagicMock(
            side_effect=[make_env(pre_records), make_env(post_records)]
        )
        registry_cls = MagicMock()
        registry_cls.new = registry_new or MagicMock()
        return (
            patch('odoo.modules.registry.Registry', registry_cls),
            patch('odoo.api.Environment', env_factory),
            registry_cls,
        )

    def test_arbitrary_module_never_reaches_odoo(self):
        records = [FakeModuleRecord('sale_management', 'uninstalled')]
        reg_patch, env_patch, registry_cls = self._patches(records)
        with reg_patch, env_patch:
            with self.assertRaises(ValidationError):
                self.service._install_modules_in_client_db(
                    self.client_db, ['some_arbitrary_module']
                )
            registry_cls.new.assert_not_called()

    def test_llm_module_identifier_never_reaches_odoo(self):
        # 'base' is a real Odoo module but NOT allowlisted — rejected.
        records = [FakeModuleRecord('base', 'installed')]
        reg_patch, env_patch, registry_cls = self._patches(records)
        with reg_patch, env_patch:
            with self.assertRaises(ValidationError):
                self.service._install_modules_in_client_db(self.client_db, ['base'])
            registry_cls.new.assert_not_called()

    def test_agency_db_never_an_installation_target(self):
        agency = self.env.cr.dbname
        with self.assertRaises(ValidationError):
            self.service._install_modules_in_client_db(agency, ['sale_management'])

    def test_supported_but_unavailable_module_fails_safely(self):
        # 'product' is allowlisted but missing from the client runtime list.
        records = [FakeModuleRecord('sale_management', 'uninstalled')]
        reg_patch, env_patch, registry_cls = self._patches(records)
        with reg_patch, env_patch:
            with self.assertRaises(ValidationError) as ctx:
                self.service._install_modules_in_client_db(
                    self.client_db, ['orders', 'products']
                )
            self.assertIn('product', str(ctx.exception))
            registry_cls.new.assert_not_called()

    def test_approved_module_installs_via_canonical_primitive(self):
        pre = [
            FakeModuleRecord('sale_management', 'uninstalled'),
            FakeModuleRecord('contacts', 'installed'),
        ]
        post = [
            FakeModuleRecord('sale_management', 'installed'),
            FakeModuleRecord('contacts', 'installed'),
        ]
        registry_new = MagicMock()
        reg_patch, env_patch, registry_cls = self._patches(
            pre, post_records=post, registry_new=registry_new
        )
        with reg_patch, env_patch:
            outcome = self.service._install_modules_in_client_db(
                self.client_db, ['sale_management', 'contacts']
            )
        registry_new.assert_called_once_with(
            self.client_db,
            update_module=True,
            install_modules=('sale_management',),
        )
        self.assertEqual(outcome['installed'], ['sale_management'])
        self.assertEqual(outcome['skipped'], ['contacts'])
        self.assertEqual(outcome['not_installed'], [])

    def test_already_installed_module_is_idempotent_noop(self):
        records = [FakeModuleRecord('contacts', 'installed')]
        registry_new = MagicMock()
        reg_patch, env_patch, registry_cls = self._patches(
            records, registry_new=registry_new
        )
        with reg_patch, env_patch:
            outcome = self.service._install_modules_in_client_db(
                self.client_db, ['contacts']
            )
        registry_new.assert_not_called()
        self.assertEqual(outcome['installed'], [])
        self.assertEqual(outcome['skipped'], ['contacts'])

    def test_transient_module_state_fails_safely(self):
        records = [FakeModuleRecord('sale_management', 'to install')]
        reg_patch, env_patch, registry_cls = self._patches(records)
        with reg_patch, env_patch:
            with self.assertRaises(ValidationError):
                self.service._install_modules_in_client_db(
                    self.client_db, ['orders']
                )
            registry_cls.new.assert_not_called()

    def test_post_install_verification_detects_failure(self):
        # Install ran but the post-state read shows the module still
        # uninstalled — the outcome is honestly reported as not installed.
        pre = [FakeModuleRecord('sale_management', 'uninstalled')]
        post = [FakeModuleRecord('sale_management', 'uninstalled')]
        registry_new = MagicMock()
        reg_patch, env_patch, registry_cls = self._patches(
            pre, post_records=post, registry_new=registry_new
        )
        with reg_patch, env_patch:
            outcome = self.service._install_modules_in_client_db(
                self.client_db, ['sale_management']
            )
        self.assertEqual(outcome['installed'], ['sale_management'])
        self.assertEqual(outcome['not_installed'], ['sale_management'])


@tagged('post_install', '-at_install')
class TestPayloadSecurity(TransactionCase):
    """API payload boundary: capabilities only, never module names."""

    def test_module_names_in_payload_rejected(self):
        with self.assertRaises(ValueError):
            parse_module_provisioning_payload({'modules': ['sale_management']})

    def test_capabilities_accepted(self):
        caps = parse_module_provisioning_payload({'capabilities': ['orders']})
        self.assertEqual(caps, ['orders'])

    def test_empty_capabilities_rejected(self):
        with self.assertRaises(ValueError):
            parse_module_provisioning_payload({'capabilities': []})

    def test_non_list_capabilities_rejected(self):
        with self.assertRaises(ValueError):
            parse_module_provisioning_payload({'capabilities': 'orders'})

    def test_non_string_entries_rejected(self):
        with self.assertRaises(ValueError):
            parse_module_provisioning_payload({'capabilities': [17]})

    def test_non_object_payload_rejected(self):
        with self.assertRaises(ValueError):
            parse_module_provisioning_payload(['orders'])
