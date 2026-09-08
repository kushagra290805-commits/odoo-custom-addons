# -*- coding: utf-8 -*-
"""Phase 47.35 — Client API + authentication tests (Odoo owner side).

Covers: token lifecycle (hash-at-rest, expiry, revocation, rotation),
authentication matrix, environment-state gating, agency-DB fail-closed
behavior, server-derived capability authorization, sanitized operation
results (via mocked client registries — real client DBs are exercised by
the standalone E2E scripts/verify_phase47_35.py), and the structural
absence of any tenant selector.
"""
import json
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.nexora_studio.services.client_environment_service import (
    ClientEnvironmentService,
)


def _registry_patch(records_by_call):
    """Patch client-DB Registry/Environment with canned model records."""
    def make_env(records):
        env_mock = MagicMock()
        env_mock.__getitem__.return_value = records
        return env_mock

    env_factory = MagicMock(side_effect=[make_env(r) for r in records_by_call])
    registry_cls = MagicMock()
    cursor = MagicMock()
    cursor.__enter__.return_value = MagicMock()
    cursor.__exit__.return_value = False
    registry_cls.return_value.cursor.return_value = cursor
    return (
        patch('odoo.modules.registry.Registry', registry_cls),
        patch('odoo.api.Environment', env_factory),
    )


class FakeProduct:
    def __init__(self, id, name, price, sku):
        self.id, self.display_name, self.list_price, self.default_code = id, name, price, sku


class FakeProductModel:
    def __init__(self, products):
        self._products = products

    def search(self, domain, limit=None, order=None):
        return self._products[:limit if limit else 100]


class FakeLead:
    def __init__(self, id):
        self.id = id


class FakeLeadModel:
    def __init__(self):
        self.created = []

    def create(self, vals):
        self.created.append(vals)
        return FakeLead(42)


def _module_state_patch(installed):
    return patch.object(
        ClientEnvironmentService, '_read_client_module_states',
        return_value={'product': 'installed' if installed else 'uninstalled'},
    )


@tagged('post_install', '-at_install')
class TestClientApiTokenLifecycle(TransactionCase):

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'P475 Token Project', 'status': 'draft',
        })
        self.service = self.env['nexora.client_environment_service']
        self.env_record = self.service.create_environment(self.project.id, 'TokEnv')
        self.env_record.status = 'ready'

    def test_issue_returns_plaintext_once_and_stores_only_hash(self):
        result = self.service.issue_client_api_token(self.env_record.id)
        token = result['token']
        self.assertTrue(token.startswith('nex_cli_'))
        import hashlib
        self.assertEqual(
            self.env_record.client_api_token_hash,
            hashlib.sha256(token.encode()).hexdigest(),
        )
        # The plaintext token itself is never stored.
        self.assertNotEqual(self.env_record.client_api_token_hash, token)
        self.assertTrue(self.env_record.client_api_token_active)
        self.assertTrue(self.env_record.client_api_token_expires_at)

    def test_issue_requires_privileges(self):
        # A non-system user must NOT be able to issue client API tokens.
        portal_user = self.env['res.users'].create({
            'name': 'P475 Portal User',
            'login': 'p475_portal_user_%s' % self.env_record.id,
            'email': 'p475@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            self.service.with_user(portal_user).issue_client_api_token(
                self.env_record.id)

    def test_rotation_invalidates_previous_token(self):
        first = self.service.issue_client_api_token(self.env_record.id)['token']
        second = self.service.issue_client_api_token(self.env_record.id)['token']
        self.assertNotEqual(first, second)
        rec, err = self.service._resolve_client_token(first)
        self.assertIsNone(rec)
        self.assertEqual(err, 'CLIENT_AUTH_INVALID')
        rec, err = self.service._resolve_client_token(second)
        self.assertIsNotNone(rec)

    def test_revocation_invalidates_token(self):
        token = self.service.issue_client_api_token(self.env_record.id)['token']
        self.service.revoke_client_api_token(self.env_record.id)
        rec, err = self.service._resolve_client_token(token)
        self.assertIsNone(rec)
        self.assertEqual(err, 'CLIENT_AUTH_INVALID')

    def test_expiry_rejected(self):
        token = self.service.issue_client_api_token(self.env_record.id, ttl_days=1)['token']
        # Force expiry.
        from datetime import timedelta
        from odoo import fields as odoo_fields
        self.env_record.client_api_token_expires_at = \
            odoo_fields.Datetime.now() - timedelta(seconds=1)
        rec, err = self.service._resolve_client_token(token)
        self.assertIsNone(rec)
        self.assertEqual(err, 'CLIENT_AUTH_EXPIRED')

    def test_malformed_tokens_fail_closed(self):
        for bad in (None, '', 'nex_cli_', 'garbage', 'x' * 200, 42,
                    ['nex_cli_abc'], {'t': 1}):
            rec, err = self.service._resolve_client_token(bad)
            self.assertIsNone(rec)
            self.assertEqual(err, 'CLIENT_AUTH_INVALID')

    def test_invalid_ttl_rejected(self):
        for bad in (0, -5, 999999, 'abc'):
            with self.assertRaises(ValidationError):
                self.service.issue_client_api_token(self.env_record.id, ttl_days=bad)


@tagged('post_install', '-at_install')
class TestClientApiAuthentication(TransactionCase):
    """client_api_* authentication/authorization matrix."""

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'P475 API Project', 'status': 'draft',
        })
        self.service = self.env['nexora.client_environment_service']
        self.env_record = self.service.create_environment(self.project.id, 'ApiEnv')
        self.env_record.status = 'ready'
        self.token = self.service.issue_client_api_token(self.env_record.id)['token']

    def test_valid_token_whoami(self):
        result = self.service.client_api_whoami(self.token)
        self.assertTrue(result['ok'])
        self.assertEqual(result['project'], 'P475 API Project')
        self.assertEqual(result['environment'], 'ApiEnv')
        self.assertEqual(result['capabilities'], [])
        # Sanitized: no db_name, no ids, no technical module names.
        self.assertNotIn('db_name', result)

    def test_missing_and_invalid_tokens_rejected(self):
        for bad in (None, '', 'not-a-token'):
            result = self.service.client_api_whoami(bad)
            self.assertFalse(result['ok'])
            self.assertEqual(result['error_code'], 'CLIENT_AUTH_INVALID')

    def test_expired_token_rejected(self):
        token = self.service.issue_client_api_token(self.env_record.id)['token']
        from datetime import timedelta
        from odoo import fields as odoo_fields
        self.env_record.client_api_token_expires_at = \
            odoo_fields.Datetime.now() - timedelta(seconds=1)
        result = self.service.client_api_whoami(token)
        self.assertEqual(result['error_code'], 'CLIENT_AUTH_EXPIRED')

    def test_revoked_token_rejected(self):
        token = self.service.issue_client_api_token(self.env_record.id)['token']
        self.service.revoke_client_api_token(self.env_record.id)
        result = self.service.client_api_whoami(token)
        self.assertEqual(result['error_code'], 'CLIENT_AUTH_INVALID')

    def test_deleted_environment_rejected(self):
        self.env_record.status = 'deleted'
        result = self.service.client_api_whoami(self.token)
        self.assertEqual(result['error_code'], 'CLIENT_ENV_DELETED')

    def test_non_ready_environment_rejected(self):
        self.env_record.status = 'draft'
        result = self.service.client_api_whoami(self.token)
        self.assertEqual(result['error_code'], 'CLIENT_ENV_NOT_READY')

    def test_agency_pointed_environment_fails_closed(self):
        # Simulate corrupted data (model constraint prevents this via ORM):
        self.env.cr.execute(
            "UPDATE nexora_client_environment SET db_name = %s WHERE id = %s",
            [self.env.cr.dbname, self.env_record.id],
        )
        self.env_record.invalidate_recordset(['db_name'])
        result = self.service.client_api_whoami(self.token)
        self.assertEqual(result['error_code'], 'CLIENT_ENV_NOT_READY')

    def test_health_sanitized(self):
        with patch('odoo.service.db.exp_db_exist', return_value=True):
            result = self.service.client_api_health(self.token)
        self.assertTrue(result['ok'])
        self.assertEqual(result['environment_status'], 'ready')
        self.assertTrue(result['client_db_available'])
        self.assertNotIn('db_name', result)


@tagged('post_install', '-at_install')
class TestClientApiCapabilityAuthorization(TransactionCase):

    def setUp(self):
        super().setUp()
        self.project = self.env['nexora.project'].create({
            'name': 'P475 Cap Project', 'status': 'draft',
        })
        self.service = self.env['nexora.client_environment_service']
        self.env_record = self.service.create_environment(self.project.id, 'CapEnv')
        self.env_record.status = 'ready'
        self.token = self.service.issue_client_api_token(self.env_record.id)['token']

    def _set_plan(self, capabilities):
        self.env_record.module_plan = json.dumps({
            'schema_version': '1.0',
            'capabilities': capabilities,
            'modules': [],
            'unresolved_capabilities': [],
            'supported': False,
        })

    def test_capability_requires_server_derived_plan(self):
        # No plan -> no capabilities -> 403 even for a valid token.
        result = self.service.client_api_list_products(self.token)
        self.assertEqual(result['error_code'], 'CLIENT_CAPABILITY_UNAVAILABLE')

    def test_capability_client_claims_ignored(self):
        # A plan is server data; the client cannot claim capabilities via
        # the request (no such parameter exists) — proven structurally.
        self._set_plan(['leads'])
        result = self.service.client_api_list_products(self.token)
        self.assertEqual(result['error_code'], 'CLIENT_CAPABILITY_UNAVAILABLE')

    def test_capability_requires_installed_module(self):
        self._set_plan(['products'])
        # Module NOT installed in the client DB -> 403.
        with _module_state_patch(installed=False):
            result = self.service.client_api_list_products(self.token)
        self.assertEqual(result['error_code'], 'CLIENT_CAPABILITY_UNAVAILABLE')

    def test_products_listed_when_authorized(self):
        self._set_plan(['products'])
        products = FakeProductModel([
            FakeProduct(1, 'Widget', 19.99, 'WID-1'),
            FakeProduct(2, 'Gadget', 5.00, ''),
        ])
        reg_patch, env_patch = _registry_patch([products])
        with _module_state_patch(installed=True), reg_patch, env_patch:
            result = self.service.client_api_list_products(self.token)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['products']), 2)
        self.assertEqual(result['products'][0]['name'], 'Widget')
        self.assertEqual(result['products'][0]['price'], 19.99)
        self.assertNotIn('db_name', result)

    def test_products_limit_validated(self):
        self._set_plan(['products'])
        products = FakeProductModel([FakeProduct(1, 'A', 1.0, '')])
        reg_patch, env_patch = _registry_patch([products])
        with _module_state_patch(installed=True), reg_patch, env_patch:
            result = self.service.client_api_list_products(self.token, limit='bogus')
        self.assertEqual(result['error_code'], 'CLIENT_REQUEST_INVALID')

    def test_lead_created_with_whitelist_only(self):
        self._set_plan(['leads'])
        leads = FakeLeadModel()
        reg_patch, env_patch = _registry_patch([leads])
        with patch.object(
            ClientEnvironmentService, '_client_module_installed', return_value=True,
        ), reg_patch, env_patch:
            result = self.service.client_api_create_lead(self.token, {
                'name': 'John Doe',
                'email': 'john@example.com',
                'phone': '+1 555 0100',
                'message': 'Hello from the website',
                # Hostile extras must be IGNORED (no passthrough):
                'model': 'ir.config_parameter',
                'method': 'execute',
                'db_name': 'nexora_studio',
                'partner_id': 999,
            })
        self.assertTrue(result['ok'])
        self.assertEqual(result['lead_id'], 42)
        vals = leads.created[0]
        self.assertEqual(vals['name'], 'John Doe')
        self.assertEqual(vals['email_from'], 'john@example.com')
        self.assertEqual(vals['phone'], '+1 555 0100')
        self.assertEqual(vals['description'], 'Hello from the website')
        # Whitelist proof: nothing else from the payload reached Odoo.
        self.assertNotIn('model', vals)
        self.assertNotIn('db_name', vals)
        self.assertNotIn('partner_id', vals)

    def test_lead_payload_validated(self):
        self._set_plan(['leads'])
        with patch.object(ClientEnvironmentService, '_client_module_installed',
                          return_value=True):
            for bad in ({}, {'name': ''}, {'name': 'x' * 300},
                        {'name': 'ok', 'email': 'not-an-email'},
                        {'name': 'ok', 'phone': 5}, None, 'string'):
                result = self.service.client_api_create_lead(self.token, bad)
                self.assertEqual(result['error_code'], 'CLIENT_REQUEST_INVALID', bad)

    def test_lead_client_db_failure_sanitized(self):
        self._set_plan(['leads'])
        # Registry blows up -> sanitized 503-style code, no internals.
        def boom():
            raise RuntimeError('psycopg2 secret connection string leak')
        with patch.object(ClientEnvironmentService, '_client_module_installed',
                          return_value=True), \
             patch.object(ClientEnvironmentService, '_client_registry_env', side_effect=boom):
            result = self.service.client_api_create_lead(
                self.token, {'name': 'ok'})
        self.assertEqual(result['error_code'], 'CLIENT_DB_UNAVAILABLE')
        self.assertNotIn('psycopg2', json.dumps(result))


@tagged('post_install', '-at_install')
class TestClientApiTenantIsolation(TransactionCase):
    """A token resolves to EXACTLY ONE environment — structurally."""

    def setUp(self):
        super().setUp()
        self.service = self.env['nexora.client_environment_service']
        self.proj_a = self.env['nexora.project'].create({'name': 'TenantA', 'status': 'draft'})
        self.proj_b = self.env['nexora.project'].create({'name': 'TenantB', 'status': 'draft'})
        self.env_a = self.service.create_environment(self.proj_a.id, 'EnvA')
        self.env_b = self.service.create_environment(self.proj_b.id, 'EnvB')
        self.env_a.status = 'ready'
        self.env_b.status = 'ready'
        self.token_a = self.service.issue_client_api_token(self.env_a.id)['token']
        self.token_b = self.service.issue_client_api_token(self.env_b.id)['token']

    def test_token_resolves_only_its_own_environment(self):
        result_a = self.service.client_api_whoami(self.token_a)
        result_b = self.service.client_api_whoami(self.token_b)
        self.assertEqual(result_a['project'], 'TenantA')
        self.assertEqual(result_b['project'], 'TenantB')

    def test_no_environment_selector_exists_in_contract(self):
        # Structural: the client API methods take ONLY the token (+payload);
        # there is no environment_id/db_name parameter to tamper with.
        import inspect
        for method in ('client_api_whoami', 'client_api_health'):
            sig = inspect.signature(getattr(ClientEnvironmentService, method))
            self.assertEqual(list(sig.parameters), ['self', 'token'])
        sig = inspect.signature(ClientEnvironmentService.client_api_list_products)
        self.assertEqual(list(sig.parameters), ['self', 'token', 'limit'])
        sig = inspect.signature(ClientEnvironmentService.client_api_create_lead)
        self.assertEqual(list(sig.parameters), ['self', 'token', 'payload'])

    def test_tampered_token_cannot_target_other_tenant(self):
        # Modifying a valid token (forgery) must not resolve at all.
        tampered = self.token_a[:-4] + 'XXXX'
        result = self.service.client_api_whoami(tampered)
        self.assertEqual(result['error_code'], 'CLIENT_AUTH_INVALID')

    def test_tokens_are_distinct_per_tenant(self):
        self.assertNotEqual(self.token_a, self.token_b)
        hashes = {self.env_a.client_api_token_hash, self.env_b.client_api_token_hash}
        self.assertEqual(len(hashes), 2)
