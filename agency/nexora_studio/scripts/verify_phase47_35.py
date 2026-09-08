# -*- coding: utf-8 -*-
"""Phase 47.35 — Real client API + authentication E2E.

Proves the full chain against REAL databases (no service mocks):

    disposable client environment (real DB + approved modules)
        -> client API token issued
        -> REAL BFF client routes (fastapi TestClient)
        -> forwarding OdooClient -> real Odoo owner service
        -> authenticated principal -> authorized environment
        -> request reaches the CLIENT Odoo DB (identity-verified)
        -> response returned; agency DB untouched (snapshot-verified)

Also proves the negative matrix: missing/invalid/expired/revoked tokens,
console-JWT != client credential (both directions), tenant isolation
(two environments), capability authorization, hostile db_name payloads
ignored, no generic passthrough routes.

Runs with the GLOBAL python (Odoo runtime + fastapi/httpx both present).
"""
import json
import sys
import time
from unittest.mock import patch

sys.path.append(r"D:\ODOO\community\odoo")
import odoo  # noqa: E402
import odoo.tools  # noqa: E402,F401
import odoo.service.db  # noqa: E402,F401

odoo.tools.config.parse_config(
    ['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio'])
from odoo.modules.registry import Registry  # noqa: E402
from odoo.api import Environment  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    print("[%s] %s :: %s" % (status, name, detail))
    if not condition:
        raise AssertionError("E2E check failed: %s :: %s" % (name, detail))


def main():
    t0 = time.time()
    agency_registry = Registry('nexora_studio')

    # ── 0. Agency before-snapshot ──────────────────────────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        agency = cr.dbname
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_before = dict(cr.fetchall())
        env_count_before = env['nexora.client_environment'].search_count([])
        cr.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='crm_lead'")
        agency_crm_lead_table_before = cr.fetchone()[0]
    check("agency DB identified", agency == 'nexora_studio', agency)

    # ── 1. Disposable client environment A: real DB + approved modules ─
    ts = time.strftime('%H%M%S')
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        project_a = env['nexora.project'].create({
            'name': 'P475 E2E TenantA %s' % ts, 'status': 'draft'})
        rec_a = env['nexora.client_environment_service'].create_environment(
            project_a.id, 'e2e475a %s' % ts)
        env_a_id, db_a = rec_a.id, rec_a.db_name
        cr.commit()
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.client_environment'].browse(env_a_id).action_provision()
        cr.commit()
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        summary = env['nexora.client_environment_service'].provision_modules(
            env_a_id, ['products', 'leads'])
        cr.commit()
    check("environment A provisioned + modules installed",
          summary['state'] == 'provisioned',
          "installed=%s" % summary['installed'])
    check("client DB A != agency DB", db_a != agency, db_a)

    # Seed one product in client DB A (setup, direct registry access).
    with Registry(db_a).cursor() as cr:
        cenv = Environment(cr, odoo.SUPERUSER_ID, {})
        cenv['product.product'].create({
            'name': 'E2E Widget %s' % ts, 'list_price': 42.5,
            'default_code': 'E2E-%s' % ts,
        })
        cr.commit()

    # ── 2. Disposable client environment B: ready, NO modules ─────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        project_b = env['nexora.project'].create({
            'name': 'P475 E2E TenantB %s' % ts, 'status': 'draft'})
        rec_b = env['nexora.client_environment_service'].create_environment(
            project_b.id, 'e2e475b %s' % ts)
        env_b_id, db_b = rec_b.id, rec_b.db_name
        cr.commit()
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.client_environment'].browse(env_b_id).action_provision()
        cr.commit()
    check("environment B provisioned (no modules)",
          db_b != agency and db_b != db_a, db_b)

    # ── 3. Issue client tokens (control plane) ────────────────────────
    # A has one stable valid token. B is used to prove revoked/expired
    # tokens before receiving its final valid token for tenant isolation.
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        svc = env['nexora.client_environment_service']
        token_a = svc.issue_client_api_token(env_a_id)['token']
        token_revoked = svc.issue_client_api_token(env_b_id)['token']
        svc.revoke_client_api_token(env_b_id)
        token_expired = svc.issue_client_api_token(env_b_id)['token']
        from datetime import timedelta
        from odoo import fields as odoo_fields
        svc.env['nexora.client_environment'].browse(env_b_id).sudo().write({
            'client_api_token_expires_at':
                odoo_fields.Datetime.now() - timedelta(seconds=1),
        })
        expired_result = svc.client_api_whoami(token_expired)
        check("expired token rejected by real Odoo owner",
              expired_result.get('error_code') == 'CLIENT_AUTH_EXPIRED',
              json.dumps(expired_result))
        token_b = svc.issue_client_api_token(env_b_id)['token']
        cr.commit()
    check("tokens issued (distinct per tenant)",
          token_a != token_b and token_a.startswith('nex_cli_'), "")

    # ── 4. Real BFF client routes via forwarding OdooClient ───────────
    BACKEND = r"D:\ODOO\nexora-console\backend"
    sys.path.insert(0, BACKEND)
    from adapters import odoo_client as odoo_client_mod
    odoo_client_mod._client_instance = None  # isolate singleton

    class ForwardingClient:
        """Test-double transport: REAL BFF routes -> REAL Odoo service
        (in-process). Only the HTTP JSON-RPC hop is replaced."""

        def call(self, model, method, args, kwargs=None, timeout=None, **kw):
            with agency_registry.cursor() as cr:
                env = Environment(cr, odoo.SUPERUSER_ID, {})
                return getattr(env[model], method)(*args)

        # compatibility no-ops for the singleton protocol
        def is_connected(self):
            return True

    import main as bff_main  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402
    from security.auth import create_access_token  # noqa: E402

    tc = TestClient(bff_main.app)
    fwd = ForwardingClient()
    with patch('api.client_routes.get_odoo_client', return_value=fwd):
        hdr_a = {'Authorization': 'Bearer ' + token_a}
        hdr_b = {'Authorization': 'Bearer ' + token_b}

        # 4a. whoami
        r = tc.get('/api/v1/client/whoami', headers=hdr_a)
        check("whoami 200", r.status_code == 200, r.text[:120])
        body = r.json()
        check("whoami identifies tenant A project",
              body['project'] == 'P475 E2E TenantA %s' % ts, body['project'])
        check("whoami capabilities server-derived",
              sorted(body['capabilities']) == ['leads', 'products'],
              json.dumps(body['capabilities']))
        check("whoami sanitized (no db_name)",
              'db_name' not in body, "")

        # 4b. health
        r = tc.get('/api/v1/client/health', headers=hdr_a)
        check("health 200 + ready + provisioned",
              r.status_code == 200
              and r.json()['environment_status'] == 'ready'
              and r.json()['module_provisioning_state'] == 'provisioned',
              r.text[:120])

        # 4c. products (capability: products) — real client DB read
        r = tc.get('/api/v1/client/products', headers=hdr_a)
        check("products 200", r.status_code == 200, r.text[:120])
        names = [p['name'] for p in r.json()['products']]
        check("seeded product served from CLIENT DB A",
              any('E2E Widget %s' % ts in name for name in names),
              json.dumps(names)[:120])

        # 4d. lead creation (capability: leads) — real client DB write
        r = tc.post('/api/v1/client/leads', headers=hdr_a, json={
            'name': 'E2E Lead %s' % ts,
            'email': 'e2e@example.com',
            'phone': '+1 555 0100',
            'message': 'Phase 47.35 E2E lead',
            # hostile extras must be ignored:
            'db_name': agency,
            'model': 'ir.config_parameter',
            'method': 'execute',
            'args': ['DROP TABLE'],
        })
        check("lead created 200", r.status_code == 200, r.text[:120])
        lead_id = r.json().get('lead_id')

        # 4e. tenant isolation: token B sees tenant B, never A
        r = tc.get('/api/v1/client/whoami', headers=hdr_b)
        check("token B resolves to tenant B project",
              r.json()['project'] == 'P475 E2E TenantB %s' % ts, r.json()['project'])
        r = tc.get('/api/v1/client/products', headers=hdr_b)
        check("token B cannot use products capability (403)",
              r.status_code == 403
              and r.json()['detail'] == 'CLIENT_CAPABILITY_UNAVAILABLE',
              r.text[:120])
        r = tc.post('/api/v1/client/leads', headers=hdr_b, json={'name': 'X'})
        check("token B cannot use leads capability (403)",
              r.status_code == 403, r.text[:120])

        # 4f. authentication matrix
        r = tc.get('/api/v1/client/whoami')
        check("missing token 401", r.status_code == 401, "")
        r = tc.get('/api/v1/client/whoami',
                   headers={'Authorization': 'Bearer forgery'})
        check("invalid token 401", r.status_code == 401, r.text[:80])
        r = tc.get('/api/v1/client/whoami',
                   headers={'Authorization': 'Bearer ' + token_revoked})
        check("revoked token 401", r.status_code == 401, r.text[:80])

        # 4g. credential classes are structurally separate
        console_jwt = create_access_token({'sub': 'admin', 'uid': 2, 'role': 'admin'})
        r = tc.get('/api/v1/client/whoami',
                   headers={'Authorization': 'Bearer ' + console_jwt})
        check("console JWT rejected on client route (401)",
              r.status_code == 401, r.text[:80])
        r = tc.get('/api/v1/auth/me',
                   headers={'Authorization': 'Bearer ' + token_a})
        check("client token rejected on console route (401)",
              r.status_code == 401, "")

        # 4h. no generic passthrough
        r = tc.post('/api/v1/client/execute', headers=hdr_a,
                    json={'model': 'res.partner', 'method': 'create'})
        check("generic execute route does not exist (404)",
              r.status_code == 404, "")
        r = tc.get('/api/v1/client/odoo/sale.order', headers=hdr_a)
        check("model passthrough route does not exist (404)",
              r.status_code == 404, "")

    # ── 5. DB identity evidence ────────────────────────────────────────
    with Registry(db_a).cursor() as cr:
        cenv = Environment(cr, odoo.SUPERUSER_ID, {})
        lead = cenv['crm.lead'].search([('name', '=', 'E2E Lead %s' % ts)], limit=1)
        check("lead EXISTS in CLIENT DB A", bool(lead), "lead_id=%s" % lead.id)
        check("lead content whitelisted",
              lead.email_from == 'e2e@example.com' and lead.phone == '+1 555 0100',
              "email/phone ok")
    with Registry(db_b).cursor() as cr:
        cenv = Environment(cr, odoo.SUPERUSER_ID, {})
        crm_b = cenv['ir.module.module'].search(
            [('name', '=', 'crm'), ('state', '=', 'installed')], limit=1)
        check("lead capability absent from client DB B", not bool(crm_b), "")
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        cr.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='crm_lead'")
        agency_has_crm = cr.fetchone()[0] > 0
        if agency_has_crm:
            cr.execute("SELECT count(*) FROM crm_lead WHERE name = %s", ['E2E Lead %s' % ts])
            check("lead NOT in agency DB", cr.fetchone()[0] == 0, "")
        else:
            check("agency DB has no crm.lead table (module never installed)",
                  True, "")
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_after = dict(cr.fetchall())
        env_count_after = env['nexora.client_environment'].search_count([])
    check("agency module states identical before/after",
          modules_after == modules_before, "")
    check("agency control-plane consistent (+2 env records)",
          env_count_after == env_count_before + 2,
          "before=%s after=%s" % (env_count_before, env_count_after))

    # ── 6. Cleanup: drop both disposable client DBs ────────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        for env_id in (env_a_id, env_b_id):
            env['nexora.client_environment'].browse(env_id).action_delete()
        cr.commit()
    check("disposable client DBs dropped",
          not odoo.service.db.exp_db_exist(db_a)
          and not odoo.service.db.exp_db_exist(db_b),
          "%s, %s" % (db_a, db_b))

    print("Completed in %.1fs - %d checks, LLM calls: 0" % (time.time() - t0, len(RESULTS)))


if __name__ == '__main__':
    main()
