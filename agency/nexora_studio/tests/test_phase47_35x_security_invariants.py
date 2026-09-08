# -*- coding: utf-8 -*-
"""Phase 47.35.x (F3) — Client API security-invariant regression tests.

Codifies the SUPERUSER CONFINEMENT INVARIANT of the client API as testable
architecture constraints:

  1. Client requests can never select the agency DB: token resolution →
     ClientEnvironment → Phase 47.34.x agency guard → client DB only.
  2. Odoo SUPERUSER context opened by client operations is confined to the
     RESOLVED client DB (registry is constructed from the stored
     environment db_name; no request input participates in DB selection).
  3. The client API surface exposes ONLY explicitly allowlisted business
     operations — no generic model/method/RPC/SQL execution exists.
  4. Credential-class separation: client tokens authenticate ONLY client
     routes; Console JWTs authenticate ONLY Console routes.
  5. Future client_api_* operations cannot bypass the agency guard: every
     client operation goes through the shared prelude that invokes
     _is_agency_database (the canonical Phase 47.34.x owner).

No ACL architecture is added; these are behavior/structure assertions.
"""
import inspect
import json
import re
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

from odoo.addons.nexora_studio.services.client_environment_service import (
    ClientEnvironmentService,
)

CLIENT_API_METHODS = (
    'client_api_whoami',
    'client_api_health',
    'client_api_list_products',
    'client_api_create_lead',
)


@tagged('post_install', '-at_install')
class TestClientApiSuperuserConfinement(TransactionCase):
    """The superuser context is an internal detail behind the Nexora
    authorization boundary, restricted to the resolved client DB."""

    def setUp(self):
        super().setUp()
        self.service = self.env['nexora.client_environment_service']
        project = self.env['nexora.project'].create({
            'name': 'P475X Invariant Project', 'status': 'draft',
        })
        self.env_record = self.service.create_environment(project.id, 'InvEnv')
        self.env_record.status = 'ready'
        self.token = self.service.issue_client_api_token(
            self.env_record.id)['token']

    def _set_plan(self, capabilities):
        self.env_record.module_plan = json.dumps({
            'schema_version': '1.0',
            'capabilities': capabilities,
            'modules': [],
            'unresolved_capabilities': [],
            'supported': True,
        })

    def test_client_request_cannot_select_agency_db(self):
        """No client API argument carries a db_name/environment selector:
        the DB is derived server-side from the token's environment only."""
        sig = inspect.signature(ClientEnvironmentService.client_api_whoami)
        self.assertEqual(list(sig.parameters), ['self', 'token'])
        sig = inspect.signature(ClientEnvironmentService.client_api_list_products)
        self.assertEqual(list(sig.parameters), ['self', 'token', 'limit'])
        sig = inspect.signature(ClientEnvironmentService.client_api_create_lead)
        self.assertEqual(list(sig.parameters), ['self', 'token', 'payload'])

    def test_agency_guard_invoked_on_real_client_path(self):
        """Every client operation goes through the shared prelude which
        invokes the canonical _is_agency_database guard (runtime call,
        not a re-import)."""
        guard_calls = []
        original = ClientEnvironmentService._is_agency_database

        def spy(rec, db_name):
            guard_calls.append(db_name)
            return original(rec, db_name)

        self._set_plan(['products'])
        with patch.object(ClientEnvironmentService,
                          '_is_agency_database', spy), \
             patch.object(ClientEnvironmentService,
                          '_client_module_installed', return_value=False):
            self.service.client_api_list_products(self.token, 5)
        # The guard ran with the STORED environment db_name.
        self.assertEqual(guard_calls, [self.env_record.db_name])
        self.assertNotIn(self.env.cr.dbname, guard_calls)

    def test_agency_pointed_environment_never_opens_agency_db(self):
        """A corrupted (agency-pointed) environment record fails closed
        BEFORE any client registry/superuser cursor is opened."""
        self.env.cr.execute(
            "UPDATE nexora_client_environment SET db_name = %s WHERE id = %s",
            [self.env.cr.dbname, self.env_record.id],
        )
        self.env_record.invalidate_recordset(['db_name'])
        opened = []

        def spy_open(rec, db_name):
            opened.append(db_name)
            raise AssertionError('registry must never be opened')

        with patch.object(ClientEnvironmentService, '_client_registry_env',
                          side_effect=spy_open):
            result = self.service.client_api_list_products(self.token, 5)
        self.assertEqual(result.get('error_code'), 'CLIENT_ENV_NOT_READY')
        self.assertEqual(opened, [])

    def test_superuser_confined_to_resolved_client_db(self):
        """The client registry is constructed ONLY from the stored
        environment db_name (the token-resolved client DB), never from
        request input and never from config defaults."""
        self._set_plan(['products'])
        target = self.env_record.db_name
        opened = []

        class _FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _FakeEnvCls:
            def __call__(self, cr, uid, ctx):
                products = MagicMock()
                products.search.return_value = []
                env = MagicMock()
                env.__getitem__.return_value = products
                return env

        def fake_env(db_name):
            opened.append(db_name)
            registry = MagicMock()
            registry.cursor.return_value = _FakeCursor()
            return registry, _FakeCursor(), _FakeEnvCls()

        with patch.object(ClientEnvironmentService,
                          '_client_module_installed', return_value=True), \
             patch.object(ClientEnvironmentService, '_client_registry_env',
                          side_effect=fake_env):
            result = self.service.client_api_list_products(self.token, 3)
        self.assertTrue(result.get('ok'), result)
        self.assertEqual(opened, [target])
        self.assertNotEqual(target, self.env.cr.dbname)

    def test_no_generic_rpc_surface_exists(self):
        """Structural: the client API owner exposes ONLY the four explicit
        business operations — no generic execute/model/method/SQL path."""
        public = [name for name in dir(ClientEnvironmentService)
                  if name.startswith('client_api_')]
        self.assertEqual(sorted(public), sorted(CLIENT_API_METHODS))
        # The client operations themselves never dispatch on model/method
        # input or run raw SQL (cr.execute is fine elsewhere in the
        # service, but NOT inside a client_api_* body).
        for method in CLIENT_API_METHODS:
            fn_src = inspect.getsource(getattr(ClientEnvironmentService,
                                               method))
            for forbidden in ('execute_kw', 'call_kw',
                              "payload.get('model')",
                              "payload.get('method')", '.execute('):
                self.assertNotIn(forbidden, fn_src,
                                 '%s must not contain %r' % (method,
                                                             forbidden))

    def test_lead_payload_cannot_inject_sql_or_rpc(self):
        """Even a hostile payload only ever produces the whitelisted
        crm.lead vals — no SQL, no model/method dispatch reaches Odoo."""
        self._set_plan(['leads'])
        created = []

        class _FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _FakeEnvCls:
            def __call__(self, cr, uid, ctx):
                lead_model = MagicMock()
                lead_model.create.side_effect = (
                    lambda vals: created.append(dict(vals))
                    or MagicMock(id=77))
                env = MagicMock()
                env.__getitem__.return_value = lead_model
                return env

        def fake_env(db_name):
            registry = MagicMock()
            registry.cursor.return_value = _FakeCursor()
            return registry, _FakeCursor(), _FakeEnvCls()

        hostile = {
            'name': 'Legit Lead',
            'query': 'DROP TABLE crm_lead',
            'sql': "'; UPDATE res_users SET password='x' --",
            'model': 'ir.config_parameter',
            'method': 'execute',
            'args': [' DROP TABLE '],
            'kwargs': {'sudo': True},
            'domain': [(1, '=', 1)],
        }
        with patch.object(ClientEnvironmentService,
                          '_client_module_installed', return_value=True), \
             patch.object(ClientEnvironmentService, '_client_registry_env',
                          side_effect=fake_env):
            result = self.service.client_api_create_lead(self.token, hostile)
        self.assertTrue(result.get('ok'), result)
        self.assertEqual(created[0], {'name': 'Legit Lead'})


@tagged('post_install', '-at_install')
class TestClientApiCredentialSeparation(TransactionCase):
    """Client and Console credential classes must not cross."""

    def setUp(self):
        super().setUp()
        self.service = self.env['nexora.client_environment_service']
        project = self.env['nexora.project'].create({
            'name': 'P475X CredSep Project', 'status': 'draft',
        })
        self.env_record = self.service.create_environment(project.id, 'CredEnv')
        self.env_record.status = 'ready'

    def test_console_jwt_shape_rejected_as_client_token(self):
        # A Console JWT is not a nex_cli_ token: rejected by the client
        # owner (prefix check) — proves the classes are distinct.
        console_jwt_like = ('eyJhbGciOiJIUzI1NiJ9.'
                            'eyJzdWIiOiJhZG1pbiIsInVpZjoyfQ.'
                            'signature-signature-signature')
        result = self.service.client_api_whoami(console_jwt_like)
        self.assertEqual(result['error_code'], 'CLIENT_AUTH_INVALID')

    def test_client_token_never_validates_as_console_jwt(self):
        # The BFF Console decoder rejects non-JWT strings — structural
        # separation is proven by the decoder's strict format check.
        client_token = 'nex_cli_' + 'a' * 40
        import jwt as pyjwt
        try:
            pyjwt.decode(client_token, 'any-secret', algorithms=['HS256'])
            self.fail('a client token must not decode as a JWT')
        except pyjwt.InvalidTokenError:
            pass

    def test_token_lookup_cannot_target_other_tenant(self):
        # Token resolution has no environment selector: modifying any part
        # of a token yields CLIENT_AUTH_INVALID (forgery impossible).
        token = self.service.issue_client_api_token(
            self.env_record.id)['token']
        for tampered in (token[:-1] + ('X' if token[-1] != 'X' else 'Y'),
                         token[:10] + 'z' + token[11:],
                         token.replace('nex_cli_', 'nex_cli_X', 1)):
            result = self.service.client_api_whoami(tampered)
            self.assertEqual(result['error_code'], 'CLIENT_AUTH_INVALID')


@tagged('post_install', '-at_install')
class TestClientApiFutureOperationInvariant(TransactionCase):
    """Hard rule for FUTURE client_api_* operations: the shared prelude
    (auth → env state → agency guard → capability) is not optional."""

    def setUp(self):
        super().setUp()
        self.service = self.env['nexora.client_environment_service']

    def test_every_client_api_method_uses_the_prelude(self):
        src = inspect.getsource(ClientEnvironmentService)
        for method in CLIENT_API_METHODS:
            fn = getattr(ClientEnvironmentService, method)
            fn_src = inspect.getsource(fn)
            self.assertIn('_client_api_prelude', fn_src,
                          '%s must authenticate via the shared prelude' % method)

    def test_prelude_invokes_canonical_agency_guard(self):
        prelude_src = inspect.getsource(
            ClientEnvironmentService._client_api_prelude)
        self.assertIn('_is_agency_database', prelude_src)
        # And the guard itself is the canonical fail-closed owner:
        guard_src = inspect.getsource(ClientEnvironmentService._is_agency_database)
        self.assertIn('isinstance(db_name, str)', guard_src)

    def test_prelude_order_auth_before_db_before_capability(self):
        prelude_src = inspect.getsource(
            ClientEnvironmentService._client_api_prelude)
        auth_pos = prelude_src.index('_resolve_client_token')
        state_pos = prelude_src.index("status == 'deleted'")
        guard_pos = prelude_src.index('_is_agency_database')
        cap_pos = prelude_src.index('_client_authorized_capabilities')
        self.assertLess(auth_pos, state_pos)
        self.assertLess(state_pos, guard_pos)
        self.assertLess(guard_pos, cap_pos)
