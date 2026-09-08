# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from unittest.mock import patch

@tagged('post_install', '-at_install')
class TestClientLifecycle(TransactionCase):

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'Test Project',
            'status': 'draft'
        })
        self.service = self.env['nexora.client_environment_service']

    def test_sanitize_db_name(self):
        self.assertEqual(self.service._sanitize_db_name('Test Project 123!'), 'nexora_Test_Project_123')
        self.assertEqual(self.service._sanitize_db_name(''), 'nexora_client')
        self.assertEqual(self.service._sanitize_db_name('x' * 100), 'nexora_' + 'x' * 20)

    def test_create_environment(self):
        env_record = self.service.create_environment(self.project.id, 'My Env')
        self.assertEqual(env_record.status, 'draft')
        self.assertTrue(env_record.db_name.startswith('nexora_'))
        self.assertEqual(env_record.name, 'My Env')
        with self.assertRaises(ValidationError):
            self.service.create_environment(self.project.id, 'My Env')

    def test_provision_success(self):
        env_record = self.service.create_environment(self.project.id, 'ProvisionTest')
        with patch('odoo.service.db.exp_create_database') as mock_create:
            mock_create.return_value = True
            env_record.action_provision()
            self.assertEqual(env_record.status, 'ready')
            self.assertIsNotNone(env_record.encrypted_admin_password)
            mock_create.assert_called_once_with(env_record.db_name, False, 'en_US', 'admin')

    def test_provision_failure(self):
        env_record = self.service.create_environment(self.project.id, 'FailTest')
        with patch('odoo.service.db.exp_create_database') as mock_create:
            mock_create.side_effect = Exception('DB creation failed')
            # Manual try/except: Odoo's assertRaises rolls back its savepoint
            # on exception by design, which would erase the failure state.
            error = None
            try:
                env_record.action_provision()
            except Exception as exc:
                error = exc
        self.assertIsNotNone(error)
        self.assertEqual(env_record.status, 'failed')
        self.assertIn('DB creation failed', env_record.error_message)

    def test_delete_success(self):
        env_record = self.service.create_environment(self.project.id, 'DeleteTest')
        env_record.status = 'ready'
        with patch('odoo.service.db.exp_drop') as mock_drop:
            mock_drop.return_value = True
            env_record.action_delete()
            self.assertEqual(env_record.status, 'deleted')

    def test_delete_agency_db_fails(self):
        env_record = self.service.create_environment(self.project.id, 'AgencyTest')
        agency = self.env.cr.dbname
        # Layer 1 (model constraint): a client environment can never be
        # re-pointed at the agency database.
        with self.assertRaises(ValidationError):
            env_record.db_name = agency
        # Layer 2 (service guard, last line of defense): simulate legacy/
        # corrupted data by bypassing the ORM constraint via SQL, then the
        # deletion must still be blocked and exp_drop must NEVER run.
        self.env.cr.execute(
            "UPDATE nexora_client_environment SET db_name = %s WHERE id = %s",
            [agency, env_record.id],
        )
        env_record.invalidate_recordset(['db_name'])
        with patch('odoo.service.db.exp_drop') as mock_drop:
            # Manual try/except (see test_provision_failure): assertRaises'
            # savepoint rollback would erase the observable failure state.
            error = None
            try:
                env_record.action_delete()
            except Exception as exc:
                error = exc
            self.assertIsNotNone(error)
            mock_drop.assert_not_called()
        # The rejected attempt is recorded as a failed (recoverable)
        # lifecycle transition; the agency database is untouched.
        self.assertEqual(env_record.status, 'failed')
        self.assertIn('agency', (env_record.error_message or '').lower())

    def test_idempotent_create(self):
        env1 = self.service.create_environment(self.project.id, 'Idempotent')
        with self.assertRaises(ValidationError):
            self.service.create_environment(self.project.id, 'Idempotent')

    def test_encryption(self):
        env_record = self.service.create_environment(self.project.id, 'EncryptTest')
        env_record.status = 'ready'
        env_record.write({
            'encrypted_admin_password': self.service._encrypt_password('secret123')
        })
        decrypted = self.service._decrypt_password(env_record.encrypted_admin_password)
        self.assertEqual(decrypted, 'secret123')