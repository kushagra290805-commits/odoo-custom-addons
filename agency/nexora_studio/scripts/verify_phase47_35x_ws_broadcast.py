# -*- coding: utf-8 -*-
"""Real-TCP broadcast verification (§8/§25): an AUTHENTICATED Console
socket must still receive the periodic agency broadcasts (SYSTEM_HEALTH /
SESSIONS_UPDATE). Uses the running dev BFF pattern from verify_phase47_35x.
Run with the same conditions as the E2E (spawns its own BFF on :8103).
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = r'D:\ODOO'
BFF = os.path.join(ROOT, 'nexora-console', 'backend')
WS_ROOT = os.path.join(ROOT, 'custom-addons', 'agency', 'scratch', 'e2e475x')


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


def _ensure_user():
    registry, odoo = _registry()
    cr = registry.cursor()
    try:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        login = os.environ.get('NEXORA_E2E_475X_LOGIN',
                               'p475x-ws@nexora.local')
        pwd = os.environ.get('NEXORA_E2E_475X_PWD',
                             'Ws-E2E-475X!disposable')
        existing = env['res.users'].search([('login', '=', login)])
        if existing:
            existing.unlink()
        user = env['res.users'].create({
            'name': 'P475X WS Broadcast Probe', 'login': login,
            'password': pwd,
            'group_ids': [(4, env.ref('base.group_system').id)],
        })
        cr.commit()
        return login, pwd, user.id
    finally:
        cr.close()


def req(method, url, payload=None, token=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header('Content-Type', 'application/json')
    if token:
        r.add_header('Authorization', 'Bearer %s' % token)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


async def main():
    login, pwd, user_id = _ensure_user()
    envv = dict(os.environ)
    envv.update({
        'PYTHONPATH': BFF,
        'ODOO_URL': 'http://127.0.0.1:8069',
        'ODOO_DB': 'nexora_studio',
        'ODOO_USERNAME': login,
        'ODOO_PASSWORD': pwd,
        'JWT_SECRET': 'e2e-475x-ws-broadcast-probe',
    })
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--port', '8103'],
        cwd=BFF, env=envv,
        stdout=open(os.path.join(WS_ROOT, 'bff_8103.log'), 'w'),
        stderr=subprocess.STDOUT)
    ok = False
    received = []
    try:
        for _ in range(60):
            try:
                req('GET', 'http://127.0.0.1:8103/api/v1/health')
                ok = True
                break
            except Exception:
                time.sleep(1)
        assert ok, 'BFF did not come up'
        status, body = req('POST', 'http://127.0.0.1:8103/api/v1/auth/login',
                           payload={'username': login, 'password': pwd})
        assert status == 200, body
        jwt_token = body['access_token']

        import websockets
        async with websockets.connect(
                'ws://127.0.0.1:8103/ws/events') as ws:
            await ws.send(json.dumps({'type': 'AUTH', 'token': jwt_token}))
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print('hello:', hello['type'])
            assert hello['type'] == 'CONNECTION_ESTABLISHED'
            # Wait for a real periodic broadcast (<=15s cycle).
            deadline = asyncio.get_event_loop().time() + 20
            while asyncio.get_event_loop().time() < deadline:
                msg = json.loads(await asyncio.wait_for(
                    ws.recv(), timeout=20))
                received.append(msg.get('type'))
                if msg.get('type') in ('SYSTEM_HEALTH', 'SESSIONS_UPDATE'):
                    print('BROADCAST RECEIVED:', msg.get('type'))
                    print('  payload keys:', sorted(
                        (msg.get('payload') or {}).keys())[:8])
                    break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
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
    assert any(t in ('SYSTEM_HEALTH', 'SESSIONS_UPDATE') for t in received), \
        'no broadcast received on authenticated socket'
    print('PASS: authenticated Console socket still receives agency broadcasts')


if __name__ == '__main__':
    asyncio.run(main())
