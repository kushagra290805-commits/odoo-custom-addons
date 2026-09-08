# -*- coding: utf-8 -*-
"""Phase 47.34.x — Agency database safety hardening tests.

Proves the fail-closed database-identity semantics of the canonical
safety owner (`nexora.client_environment_service._is_agency_database` /
`_agency_database_names`) under the actual Odoo 19 configuration
representation (`db_name` is a 'comma' option → LIST of strings), and
that every destructive client path blocks the agency database.

Every destructive test patches the Odoo primitive (`exp_drop` /
`exp_create_database`) so the tests themselves can NEVER drop or touch
the real agency database, even if a guard regresses.
"""
from unittest.mock import MagicMock, patch

import odoo
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


def _config_patch(db_name_value):
    """Patch odoo.tools.config so config.get('db_name') returns the value.

    Used to exercise the identity-normalization matrix (string / list /
    malformed) without touching the real runtime configuration.
    """
    mock_config = MagicMock()
    mock_config.get.side_effect = (
        lambda key, default=None: db_name_value if key == 'db_name' else default
    )
    return patch('odoo.tools.config', mock_config)


@tagged('post_install', '-at_install')
class TestAgencyDatabaseIdentity(TransactionCase):
    """_is_agency_database: normalization matrix + fail-closed behavior."""

    def setUp(self):
        super().setUp()
        self.service = self.env['nexora.client_environment_service']
        self.agency = self.env.cr.dbname
        self.client_db = 'nexora_SomeClient'

    def test_agency_as_string_config(self):
        with _config_patch(self.agency):
            self.assertTrue(self.service._is_agency_database(self.agency))
            self.assertFalse(self.service._is_agency_database(self.client_db))

    def test_agency_as_single_item_list_config(self):
        # Odoo 19 canonical runtime form (tools/config.py type='comma'):
        # `-d nexora_studio` → ['nexora_studio'].
        with _config_patch([self.agency]):
            self.assertTrue(self.service._is_agency_database(self.agency))
            self.assertFalse(self.service._is_agency_database(self.client_db))

    def test_agency_in_multi_item_list_config(self):
        with _config_patch(['other_db', self.agency]):
            self.assertTrue(self.service._is_agency_database(self.agency))
            self.assertFalse(self.service._is_agency_database('other_dbx'))

    def test_actual_runtime_configuration_form(self):
        # No patching: the REAL Odoo 19 runtime configuration.
        config_db = odoo.tools.config.get('db_name')
        # Document the actual representation (comma option → list or str).
        self.assertIn(type(config_db).__name__, ('list', 'str'))
        # The cursor's database is always detected as the agency DB.
        self.assertTrue(self.service._is_agency_database(self.agency))

    def test_empty_list_config_cursor_remains_authoritative(self):
        with _config_patch([]):
            self.assertTrue(self.service._is_agency_database(self.agency))
            self.assertFalse(self.service._is_agency_database(self.client_db))

    def test_none_config_cursor_remains_authoritative(self):
        with _config_patch(None):
            self.assertTrue(self.service._is_agency_database(self.agency))
            self.assertFalse(self.service._is_agency_database(self.client_db))

    def test_empty_string_config_cursor_remains_authoritative(self):
        with _config_patch(''):
            self.assertTrue(self.service._is_agency_database(self.agency))
            self.assertFalse(self.service._is_agency_database(self.client_db))

    def test_malformed_config_type_fails_closed(self):
        # Unexpected config types block the operation for ANY target —
        # the identity is undeterminable, so nothing may proceed.
        for bad in (42, {'db': 1}, True):
            with _config_patch(bad):
                with self.assertRaises(ValidationError):
                    self.service._is_agency_database(self.client_db)
                with self.assertRaises(ValidationError):
                    self.service._is_agency_database(self.agency)

    def test_malformed_config_entry_fails_closed(self):
        with _config_patch([self.agency, 7]):
            with self.assertRaises(ValidationError):
                self.service._is_agency_database(self.agency)
        with _config_patch([self.agency, '']):
            with self.assertRaises(ValidationError):
                self.service._is_agency_database(self.agency)

    def test_list_db_name_input_fails_closed(self):
        # The exact incident class: a LIST db_name must never silently
        # compare unequal and let a destructive operation proceed.
        with self.assertRaises(ValidationError):
            self.service._is_agency_database([self.agency])

    def test_none_db_name_input_fails_closed(self):
        with self.assertRaises(ValidationError):
            self.service._is_agency_database(None)

    def test_empty_db_name_input_fails_closed(self):
        with self.assertRaises(ValidationError):
            self.service._is_agency_database('')
        with self.assertRaises(ValidationError):
            self.service._is_agency_database('   ')

    def test_unexpected_type_db_name_input_fails_closed(self):
        for bad in (42, {'a': 1}, ('nexora_studio',)):
            with self.assertRaises(ValidationError):
                self.service._is_agency_database(bad)

    def test_legitimate_client_db_not_agency(self):
        self.assertFalse(self.service._is_agency_database(self.client_db))


@tagged('post_install', '-at_install')
class TestDestructivePathHardening(TransactionCase):
    """Every destructive client path blocks the agency database."""

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'Phase 47.34.x Safety Project',
            'status': 'draft',
        })
        self.service = self.env['nexora.client_environment_service']
        self.agency = self.env.cr.dbname

    def _bypass_to_agency(self, env_record):
        """Simulate legacy/corrupted data: re-point db_name via SQL.

        The model constraint blocks ORM writes of the agency name, so SQL
        is the only way to produce this state — exactly the scenario the
        service guard exists for (last line of defense).
        """
        self.env.cr.execute(
            "UPDATE nexora_client_environment SET db_name = %s WHERE id = %s",
            [self.agency, env_record.id],
        )
        env_record.invalidate_recordset(['db_name'])

    def test_agency_db_deletion_blocked_exp_drop_never_called(self):
        env_record = self.service.create_environment(self.project.id, 'DelGuard')
        self._bypass_to_agency(env_record)
        with patch('odoo.service.db.exp_drop') as mock_drop:
            # Manual try/except: assertRaises' savepoint rollback would
            # erase the observable failure state.
            error = None
            try:
                env_record.action_delete()
            except Exception as exc:
                error = exc
            self.assertIsNotNone(error)
            mock_drop.assert_not_called()
        self.assertEqual(env_record.status, 'failed')
        self.assertIn('agency', (env_record.error_message or '').lower())

    def test_agency_db_drop_blocked_via_service_delete(self):
        env_record = self.service.create_environment(self.project.id, 'SvcGuard')
        self._bypass_to_agency(env_record)
        with patch('odoo.service.db.exp_drop') as mock_drop:
            with self.assertRaises(ValidationError):
                self.service.delete(env_record.id)
            mock_drop.assert_not_called()

    def test_client_db_deletion_allowed(self):
        env_record = self.service.create_environment(self.project.id, 'Allowed')
        env_record.status = 'ready'
        with patch('odoo.service.db.exp_drop') as mock_drop:
            mock_drop.return_value = True
            env_record.action_delete()
            mock_drop.assert_called_once_with(env_record.db_name)
        self.assertEqual(env_record.status, 'deleted')

    def test_failed_provisioning_cannot_target_agency_db(self):
        env_record = self.service.create_environment(self.project.id, 'ProvGuard')
        self._bypass_to_agency(env_record)
        with patch('odoo.service.db.exp_create_database') as mock_create:
            error = None
            try:
                env_record.action_provision()
            except Exception as exc:
                error = exc
            self.assertIsNotNone(error)
            mock_create.assert_not_called()
        self.assertEqual(env_record.status, 'failed')

    def test_disposable_cleanup_cannot_delete_agency_db(self):
        # Disposable/teardown cleanup reuses the same guarded
        # action_delete path — blocked for the agency DB.
        env_record = self.service.create_environment(self.project.id, 'TearGuard')
        self._bypass_to_agency(env_record)
        env_record.status = 'ready'
        with patch('odoo.service.db.exp_drop') as mock_drop:
            with self.assertRaises(ValidationError):
                env_record.action_delete()
            mock_drop.assert_not_called()


@tagged('post_install', '-at_install')
class TestClientNamingCollisionProtection(TransactionCase):
    """Deterministic client naming can never produce the agency DB name."""

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'Naming Collision Project',
            'status': 'draft',
        })
        self.service = self.env['nexora.client_environment_service']
        self.agency = self.env.cr.dbname

    def test_agency_shaped_identifier_rejected(self):
        # The sanitization scheme is `nexora_` + identifier; an agency DB
        # named `nexora_<x>` is collidable via identifier `<x>` (e.g.
        # "studio" → "nexora_studio"). Creation must fail closed.
        prefix = 'nexora_'
        if not self.agency.startswith(prefix):
            self.skipTest('agency DB name has no nexora_ prefix')
        colliding = self.agency[len(prefix):]
        self.assertEqual(self.service._sanitize_db_name(colliding), self.agency)
        with self.assertRaises(ValidationError):
            self.service.create_environment(self.project.id, colliding)

    def test_project_identifier_collision_rejected(self):
        prefix = 'nexora_'
        if not self.agency.startswith(prefix):
            self.skipTest('agency DB name has no nexora_ prefix')
        project = self.env['nexora.project'].create({
            'name': self.agency[len(prefix):],
            'status': 'draft',
        })
        with self.assertRaises(ValidationError):
            self.service.create_environment(project.id, None)

    def test_full_agency_name_as_identifier_is_not_a_false_collision(self):
        # "nexora_studio" as an identifier sanitizes to
        # "nexora_nexora_studio" — a distinct client name; must not be
        # falsely rejected.
        env_record = self.service.create_environment(self.project.id, self.agency)
        self.assertNotEqual(env_record.db_name, self.agency)
        self.assertFalse(self.service._is_agency_database(env_record.db_name))

    def test_model_constraint_blocks_agency_db_name_write(self):
        env_record = self.service.create_environment(self.project.id, 'ModelGuard')
        # A client environment can never be re-pointed at the agency DB.
        with self.assertRaises(ValidationError):
            env_record.db_name = self.agency
        self.assertNotEqual(env_record.db_name, self.agency)

    def test_non_colliding_names_still_work(self):
        env_record = self.service.create_environment(self.project.id, 'Regular Client')
        self.assertNotEqual(env_record.db_name, self.agency)
        self.assertFalse(self.service._is_agency_database(env_record.db_name))
