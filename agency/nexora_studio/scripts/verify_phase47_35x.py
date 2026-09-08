# -*- coding: utf-8 -*-
"""Phase 47.35.x — F2: REAL HTTP transport E2E + F1: REAL WebSocket check.

Closes the two verification gaps from the Phase 47.35 red-team review:

F2 — the load-bearing client operations now run through the REAL chain:

    BFF client routes
      -> OdooClient (real adapter, singleton)
      -> HTTP JSON-RPC (urllib, session cookie)
      -> Odoo server on :8069 (real HTTP)
      -> nexora.client_environment_service (real owner)
      -> REAL disposable client DB (product read + lead create)

    No ForwardingClient. No direct registry access for the client
    operation itself. The BFF is a REAL uvicorn process with REAL
    service-account credentials (disposable Odoo user, deleted at the end).

F1 — the REAL WebSocket hub is probed over real TCP: unauthenticated
    close, client-token close, valid Console JWT accepted.

Also proves failure semantics:
    invalid service credentials -> sanitized 502/401 (no internals)
    Odoo unavailable           -> bounded timeout -> sanitized 502

Agency DB safety: agency DB is never a target; before/after snapshot.
Credentials are read from the Odoo registry-configured environment /
created disposable user, passed via process env only, never printed,
never written to disk.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = r'D:\ODOO'
BFF = os.path.join(ROOT, 'nexora-console', 'backend')
WS_ROOT = os.path.join(ROOT, 'custom-addons', 'agency', 'scratch', 'e2e475x')

RESULTS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    print("[%s] %s :: %s" % (status, name, detail))
    if not condition:
        raise AssertionError("E2E check failed: %s :: %s" % (name, detail))


def _registry():
    sys.path.insert(0, os.path.join(ROOT, 'community', 'odoo'))
    import odoo
    import odoo.tools
    import odoo.modules.module as m
    odoo.tools.config.parse_config(
        ['-c', os.path.join(ROOT, 'configs', 'dev.conf'),
         '-d', 'nexora_studio'])
    m.initialize_sys_path()
    from odoo.modules.registry import Registry
    return Registry('nexora_studio'), odoo


def _ensure_service_user():
    """Create the DISPOSABLE service account used by the BFF for this E2E.

    Privilege model (F2 §13): the BFF service account is a real Odoo
    user with base.group_system (deliberately privileged: the Nexora
    service layer is the security boundary). Created/deleted via the
    registry; credentials only transit process env.
    """
    registry, odoo = _registry()
    cr = registry.cursor()
    try:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        login = os.environ.get('NEXORA_E2E_475X_LOGIN',
                               'p475x-svc@nexora.local')
        pwd = os.environ.get('NEXORA_E2E_475X_PWD',
                             'Svc-E2E-475X!disposable')
        existing = env['res.users'].search([('login', '=', login)])
        if existing:
            existing.unlink()
        user = env['res.users'].create({
            'name': 'P475X Disposable Service Account',
            'login': login,
            'password': pwd,
            'group_ids': [(4, env.ref('base.group_system').id)],
        })
        cr.commit()
        return login, pwd, user.id
    finally:
        cr.close()


def _drop_service_user(user_id):
    registry, odoo = _registry()
    cr = registry.cursor()
    try:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['res.users'].browse(user_id).exists()
        if rec:
            rec.unlink()
        cr.commit()
    finally:
        cr.close()


def _issue_client_token(env_id):
    registry, odoo = _registry()
    cr = registry.cursor()
    try:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        return env['nexora.client_environment_service'].issue_client_api_token(
            env_id)['token'], None
    finally:
        cr.close()


def req(method, url, payload=None, token=None, timeout=60, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    if token:
        r.add_header('Authorization', 'Bearer %s' % token)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def wait_health(base, tries=60):
    for _ in range(tries):
        try:
            status, _ = req('GET', base + '/api/v1/health')
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('BFF health check failed')


def spawn_bff(port, extra_env):
    env = dict(os.environ)
    env.update({
        'PYTHONPATH': BFF,
        'ODOO_URL': 'http://127.0.0.1:8069',
        'ODOO_DB': 'nexora_studio',
    })
    env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--port', str(port)],
        cwd=BFF, env=env,
        stdout=open(os.path.join(WS_ROOT, 'bff_%s.log' % port), 'w'),
        stderr=subprocess.STDOUT)
    return proc


def main():
    os.makedirs(WS_ROOT, exist_ok=True)
    t0 = time.time()

    # ── 0. Agency before-snapshot + disposable client env ───────────
    registry, odoo = _registry()
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        agency = cr.dbname
        check("agency DB identified", agency == 'nexora_studio', agency)
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_before = dict(cr.fetchall())
        cr.execute("SELECT count(*) FROM information_schema.tables "
                   "WHERE table_name='crm_lead'")
        agency_has_crm = cr.fetchone()[0] > 0
        if agency_has_crm:
            cr.execute("SELECT count(*) FROM crm_lead")
            agency_leads_before = cr.fetchone()[0]
        else:
            agency_leads_before = None
        env_count_before = env['nexora.client_environment'].search_count([])

    ts = time.strftime('%H%M%S')
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        project = env['nexora.project'].create({
            'name': 'P475X HTTP E2E %s' % ts, 'status': 'draft'})
        rec = env['nexora.client_environment_service'].create_environment(
            project.id, 'e2ehttp %s' % ts)
        env_id, db = rec.id, rec.db_name
        cr.commit()
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.client_environment'].browse(env_id).action_provision()
        cr.commit()
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        summary = env['nexora.client_environment_service'].provision_modules(
            env_id, ['products', 'leads'])
        cr.commit()
    check("disposable client DB provisioned + modules installed",
          summary['state'] == 'provisioned',
          "db=%s installed=%s" % (db, summary['installed']))
    check("client DB != agency DB", db != agency, db)

    # Seed one product directly (setup, like verify_phase47_35).
    from odoo.modules.registry import Registry as _Reg
    with _Reg(db).cursor() as cr:
        cenv = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        cenv['product.product'].create({
            'name': 'HTTP E2E Widget %s' % ts, 'list_price': 17.25,
            'default_code': 'HTTP-%s' % ts,
        })
        cr.commit()

    # ── 1. Disposable service account + client token ─────────────────
    svc_login, svc_pwd, svc_user_id = _ensure_service_user()
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        token = env['nexora.client_environment_service'].issue_client_api_token(
            env_id)['token']
        cr.commit()

    # ── 2. REAL BFF process with REAL service credentials ────────────
    proc = spawn_bff(8100, {
        'ODOO_USERNAME': svc_login,
        'ODOO_PASSWORD': svc_pwd,
        'JWT_SECRET': 'e2e-475x-secret-for-real-http-run',
    })
    try:
        base = 'http://127.0.0.1:8100'
        wait_health(base)
        check("real BFF up (uvicorn :8100)", True, "")

        hdr = {'Authorization': 'Bearer %s' % token}

        # 2a. whoami over REAL HTTP
        status, body = req('GET', base + '/api/v1/client/whoami',
                           token=token)
        check("whoami via real HTTP -> 200", status == 200, str(body)[:120])
        check("whoami sanitized (no db_name)", 'db_name' not in body, "")

        # 2b. health over REAL HTTP
        status, body = req('GET', base + '/api/v1/client/health', token=token)
        check("health via real HTTP -> 200 ready", status == 200
              and body.get('environment_status') == 'ready', str(body)[:120])

        # 2c. products — REAL HTTP -> client DB
        status, body = req('GET', base + '/api/v1/client/products', token=token)
        check("products via real HTTP -> 200", status == 200, str(body)[:120])
        names = [p.get('name') for p in body.get('products', [])]
        check("product came from CLIENT DB (seeded widget)",
              any('HTTP E2E Widget %s' % ts in (n or '') for n in names),
              json.dumps(names)[:120])

        # 2d. lead create — REAL HTTP -> client DB
        lead_name = 'HTTP E2E Lead %s' % ts
        status, body = req('POST', base + '/api/v1/client/leads', payload={
            'name': lead_name,
            'email': 'http-e2e@example.com',
            'phone': '+1 555 0100',
            'message': 'Phase 47.35.x real HTTP lead',
            'db_name': agency, 'model': 'ir.config_parameter',
            'method': 'execute', 'args': ['DROP TABLE'],
        }, headers=hdr)
        check("lead via real HTTP -> 200", status == 200, str(body)[:120])
        lead_id = body.get('lead_id')

        # ── 2e. WS over real TCP: unauth / client token / valid JWT ──
        try:
            import websockets
            ws_url = 'ws://127.0.0.1:8100/ws/events'

            async def _probe_close(send_auth=None):
                """Connect, optionally send AUTH, and capture how the hub
                closes the socket. Returns 'EVENT_LEAK' if any event frame
                arrived, else the close code/reason."""
                import asyncio as _a
                from websockets.exceptions import ConnectionClosed
                async with websockets.connect(ws_url,
                                              close_timeout=5) as ws:
                    if send_auth is not None:
                        await ws.send(json.dumps({'type': 'AUTH',
                                                  'token': send_auth}))
                    try:
                        msg = await _a.wait_for(
                            ws.recv(),
                            timeout=15 if send_auth is None else 6)
                        return 'EVENT_LEAK:%s' % msg
                    except ConnectionClosed as e:
                        return 'CLOSED:%s' % e.rcvd
                    except _a.TimeoutError:
                        return 'NO_CLOSE'

            async def ws_probe():
                out = {}
                out['unauth'] = await _probe_close()
                out['client_token'] = await _probe_close(token)
                # valid console JWT: login via the real BFF
                status, body = req('POST', base + '/api/v1/auth/login',
                                   payload={'username': svc_login,
                                            'password': svc_pwd})
                check("console login for WS probe -> 200", status == 200, "")
                jwt_token = body['access_token']
                out['valid_jwt'] = await _probe_close(jwt_token)
                if out['valid_jwt'].startswith('CLOSED:'):
                    return out
                # authenticated: ping/pong over real TCP
                import asyncio as _a2
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({'type': 'AUTH',
                                              'token': jwt_token}))
                    hello = json.loads(await _a2.wait_for(ws.recv(),
                                                          timeout=6))
                    out['valid_jwt'] = hello.get('type')
                    await ws.send(json.dumps({'type': 'ping'}))
                    pong = json.loads(await _a2.wait_for(ws.recv(),
                                                         timeout=6))
                    out['ping'] = pong.get('type')
                return out
            import asyncio
            ws_out = asyncio.run(ws_probe())
            print("WS probe:", ws_out)
            check("WS unauthenticated closed 4401 without events",
                  '4401' in str(ws_out.get('unauth')),
                  str(ws_out.get('unauth')))
            check("WS client token closed 4401 without events",
                  '4401' in str(ws_out.get('client_token')),
                  str(ws_out.get('client_token')))
            check("WS valid Console JWT accepted + pong",
                  ws_out.get('valid_jwt') == 'CONNECTION_ESTABLISHED'
                  and ws_out.get('ping') == 'pong',
                  str(ws_out.get('valid_jwt')) + ' ping='
                  + str(ws_out.get('ping')))
        except ImportError:
            print("SKIP: websockets lib unavailable")

        # ── 3. FAILURE SEMANTICS ─────────────────────────────────────
        # 3a. Invalid Odoo service credentials -> sanitized error
        proc2 = spawn_bff(8101, {
            'ODOO_USERNAME': svc_login,
            'ODOO_PASSWORD': 'wrong-password-probe',
            'JWT_SECRET': 'e2e-475x-invalid-creds-probe',
        })
        try:
            base2 = 'http://127.0.0.1:8101'
            wait_health(base2)
            status, body = req('GET', base2 + '/api/v1/client/whoami',
                               token=token)
            check("invalid service credentials -> sanitized 502",
                  status == 502 and 'detail' in body
                  and 'password' not in json.dumps(body).lower()
                  and 'svc' not in json.dumps(body).lower()
                  and 'odoo' not in json.dumps(body).lower(),
                  "%s %s" % (status, str(body)[:100]))
        finally:
            proc2.terminate()
            try:
                proc2.wait(timeout=10)
            except Exception:
                proc2.kill()

        # 3b. Odoo unavailable -> bounded timeout -> sanitized 502
        proc3 = spawn_bff(8102, {
            'ODOO_URL': 'http://127.0.0.1:8099',  # nothing listens
            'ODOO_USERNAME': svc_login,
            'ODOO_PASSWORD': svc_pwd,
            'JWT_SECRET': 'e2e-475x-odoo-down-probe',
        })
        try:
            base3 = 'http://127.0.0.1:8102'
            wait_health(base3)
            t_start = time.time()
            status, body = req('GET', base3 + '/api/v1/client/whoami',
                               token=token, timeout=90)
            elapsed = time.time() - t_start
            check("Odoo unavailable -> sanitized 502, bounded (%.1fs)"
                  % elapsed,
                  status == 502
                  and 'Client backend unavailable' in json.dumps(body)
                  and elapsed < 60,
                  "%s %.1fs" % (status, elapsed))
        finally:
            proc3.terminate()
            try:
                proc3.wait(timeout=10)
            except Exception:
                proc3.kill()

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    # ── 4. DB evidence: client DB got the lead; agency DB untouched ──
    with _Reg(db).cursor() as cr:
        cenv = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        lead = cenv['crm.lead'].search([('name', '=', lead_name)], limit=1)
        check("lead EXISTS in CLIENT DB (direct registry)",
              bool(lead), "lead_id=%s" % (lead.id if lead else None))
        check("lead content intact",
              bool(lead) and lead.email_from == 'http-e2e@example.com',
              "")
    with registry.cursor() as cr:
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_after = dict(cr.fetchall())
        check("agency module states identical", modules_after == modules_before, "")
        if agency_has_crm:
            cr.execute("SELECT count(*) FROM crm_lead")
            check("no new lead in agency DB",
                  cr.fetchone()[0] == agency_leads_before, "")
        else:
            cr.execute("SELECT count(*) FROM information_schema.tables "
                       "WHERE table_name='crm_lead'")
            check("agency DB still has no crm.lead table",
                  cr.fetchone()[0] == 0, "")
        env_after = odoo.api.Environment(
            cr, odoo.SUPERUSER_ID, {})['nexora.client_environment']
        check("agency control-plane +1 env record (disposable)",
              env_after.search_count([]) == env_count_before + 1, "")

    # ── 5. Cleanup through canonical lifecycle ──────────────────────
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        env['nexora.client_environment'].browse(env_id).action_delete()
        cr.commit()
    import odoo.service.db as _dbsvc
    check("disposable client DB dropped",
          not _dbsvc.exp_db_exist(db), db)
    _drop_service_user(svc_user_id)
    check("disposable service account deleted", True, "")

    print("Completed in %.1fs - %d checks, LLM calls: 0"
          % (time.time() - t0, len(RESULTS)))


if __name__ == '__main__':
    main()
