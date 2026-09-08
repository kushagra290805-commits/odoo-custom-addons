# -*- coding: utf-8 -*-
"""Phase 47.34 — Real-DB E2E: Odoo module provisioning & capability mapping.

Proves, against REAL databases (no mocks for the provisioning path):
    project → capability contract → module policy → approved module plan →
    client environment → real client Odoo DB → real module installation →
    verified module states → agency DB untouched.

Also demonstrates: negative allowlist case (arbitrary capability/module
rejected, no installation), idempotent re-provisioning, and a fail-safe
unavailable-module scenario with recovery — all on a disposable isolated
client database that is dropped at the end.

The capability → module mapping adds ZERO LLM calls (deterministic policy).

Usage:
    python scripts/verify_phase47_34.py
"""
import json
import logging
import sys
import time

sys.path.append(r"D:\ODOO\community\odoo")
import odoo  # noqa: E402
import odoo.tools  # noqa: E402,F401  (bind odoo.tools for namespace layout)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
_logger = logging.getLogger("Phase47.34-E2E")

RESULTS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    _logger.info("[%s] %s :: %s", status, name, detail)
    if not condition:
        raise AssertionError("E2E check failed: %s :: %s" % (name, detail))


def main():
    t0 = time.time()
    odoo.tools.config.parse_config(
        ['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio']
    )
    from odoo.modules.registry import Registry
    from odoo.api import Environment

    agency_registry = Registry('nexora_studio')

    # ── 0. Agency DB snapshot (integrity baseline) ───────────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        agency_dbname = cr.dbname
        config_dbs = odoo.tools.config.get('db_name') or []
        if isinstance(config_dbs, str):
            config_dbs = [config_dbs]
        agency_names = set(config_dbs) | {agency_dbname}
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        agency_modules_before = dict(cr.fetchall())
        agency_env_count_before = env['nexora.client_environment'].search_count([])
    check("agency DB identified", agency_dbname == 'nexora_studio',
          "cr.dbname=%s config db_name=%s" % (agency_dbname, config_dbs))

    # ── 1. Disposable client environment (real DB creation) ─────────────
    ts = time.strftime('%H%M%S')
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        project = env['nexora.project'].create({
            'name': 'Phase 47.34 E2E %s' % ts,
            'status': 'draft',
        })
        env_rec = env['nexora.client_environment_service'].create_environment(
            project.id, 'e2e4734 %s' % ts
        )
        env_id = env_rec.id
        db_name = env_rec.db_name
        cr.commit()

    check("client DB name deterministic + sanitized",
          db_name.startswith('nexora_'), db_name)
    check("agency DB != client DB (explicit proof)",
          db_name not in agency_names,
          "client=%s agency=%s" % (db_name, sorted(agency_names)))

    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        rec.action_provision()
        cr.commit()
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        check("client environment ready (real exp_create_database)",
              rec.status == 'ready', "status=%s" % rec.status)
        check("admin credential encrypted at rest",
              bool(rec.encrypted_admin_password))
    check("client DB exists in PostgreSQL",
          odoo.service.db.exp_db_exist(db_name), db_name)

    # ── 2. Real module provisioning (multiple capabilities) ─────────────
    capabilities = ['products', 'customers', 'contacts', 'orders',
                    'leads', 'subscriptions']
    expected_modules = ['contacts', 'crm', 'product', 'sale_management']

    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        summary = None
        error = None
        try:
            summary = env['nexora.client_environment_service'].provision_modules(
                env_id, capabilities
            )
        except Exception as exc:
            error = exc
        cr.commit()
    check("provision_modules succeeded (real installation)",
          summary is not None, str(error) if error else '')
    check("approved plan modules match allowlist",
          sorted(m['name'] for m in summary['plan']['modules']) == expected_modules,
          json.dumps(sorted(m['name'] for m in summary['plan']['modules'])))
    check("unresolved capability explicit (subscriptions)",
          [u['capability'] for u in summary['plan']['unresolved_capabilities']]
          == ['subscriptions'])
    check("plan explains module selection",
          all(m.get('reason') and m.get('source_capabilities') and m.get('required')
              for m in summary['plan']['modules']))

    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        check("module provisioning state = provisioned",
              rec.module_provisioning_state == 'provisioned',
              rec.module_provisioning_state)
        check("DB lifecycle state untouched (still ready)",
              rec.status == 'ready', rec.status)

    # ── 3. Verify REAL module states in the client DB ───────────────────
    verify_names = expected_modules + ['sale', 'mail', 'sales_team', 'digest', 'uom']
    client_registry = Registry(db_name)
    with client_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        mods = env['ir.module.module'].search([('name', 'in', verify_names)])
        client_states = {m.name: m.state for m in mods}
    for name in expected_modules:
        check("client DB: %s installed (real)" % name,
              client_states.get(name) == 'installed',
              "state=%s" % client_states.get(name))
    for dep in ['sale', 'mail', 'sales_team']:
        check("client DB: dependency %s resolved+installed by Odoo (never requested)"
              % dep, client_states.get(dep) == 'installed',
              "state=%s" % client_states.get(dep))

    # ── 4. Agency DB isolation evidence ─────────────────────────────────
    with agency_registry.cursor() as cr:
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        agency_modules_after = dict(cr.fetchall())
    check("agency DB module states unchanged (untouched)",
          agency_modules_after == agency_modules_before,
          "changed=%s" % sorted(
              k for k in set(agency_modules_before) | set(agency_modules_after)
              if agency_modules_before.get(k) != agency_modules_after.get(k)
          )[:8])
    check("agency DB has no provisioning leftovers",
          all(s not in ('to install', 'to upgrade', 'to remove')
              for s in agency_modules_after.values()))
    for name in expected_modules:
        check("agency DB: %s state unchanged by client provisioning" % name,
              agency_modules_after.get(name) == agency_modules_before.get(name),
              "before=%s after=%s" % (agency_modules_before.get(name),
                                      agency_modules_after.get(name)))

    # ── 5. Idempotency: repeat the same plan ────────────────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        summary2 = env['nexora.client_environment_service'].provision_modules(
            env_id, capabilities
        )
        cr.commit()
    check("repeat provisioning installs nothing new",
          summary2['installed'] == [], json.dumps(summary2['installed']))
    check("repeat provisioning skips all installed modules",
          sorted(summary2['skipped']) == expected_modules,
          json.dumps(sorted(summary2['skipped'])))
    check("repeat provisioning state stays provisioned",
          summary2['state'] == 'provisioned')

    client_registry = Registry(db_name)
    with client_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        mods = env['ir.module.module'].search([('name', 'in', expected_modules)])
        states2 = {m.name: m.state for m in mods}
    check("no duplicate/broken module state after repeat",
          all(s == 'installed' for s in states2.values()), json.dumps(states2))

    # ── 6. Negative: unknown/arbitrary capability rejected ──────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        state_before = rec.module_provisioning_state
        rejected = False
        try:
            env['nexora.client_environment_service'].provision_modules(
                env_id, ['totally_unknown_feature']
            )
        except Exception:
            rejected = True
        cr.commit()
    check("unknown capability rejected (no installation)",
          rejected, "state_before=%s" % state_before)
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        check("provisioning state preserved after rejection",
              rec.module_provisioning_state == state_before,
              rec.module_provisioning_state)

    # ── 7. Negative: arbitrary module name cannot reach the installer ───
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rejected = False
        try:
            env['nexora.client_environment_service']._install_modules_in_client_db(
                db_name, ['some_arbitrary_module']
            )
        except Exception:
            rejected = True
        cr.commit()
    check("arbitrary module name rejected by privileged installer", rejected)

    # ── 8. Fail-safe: supported-but-unavailable module, then recovery ───
    RealEnv = odoo.api.Environment
    ACTIVE = {'hide': set(), 'remaining': 0}

    class ModuleProxy:
        def __init__(self, model):
            self._model = model

        def update_list(self):
            return self._model.update_list()

        def search(self, domain):
            res = self._model.search(domain)
            if ACTIVE['remaining'] > 0:
                ACTIVE['remaining'] -= 1
                res = [r for r in res if r.name not in ACTIVE['hide']]
            return res

    class EnvProxy:
        def __init__(self, env):
            self._env = env

        def __getitem__(self, key):
            model = self._env[key]
            if key == 'ir.module.module':
                return ModuleProxy(model)
            return model

    def fault_injecting_env(cr, uid, ctx):
        real = RealEnv(cr, uid, ctx)
        if cr.dbname == db_name and ACTIVE['hide']:
            return EnvProxy(real)
        return real

    # Hide 'crm' from exactly the first availability search, simulating
    # an addon that is supported by the allowlist but unavailable in the
    # client runtime. The post-failure state read must see reality.
    ACTIVE['hide'] = {'crm'}
    ACTIVE['remaining'] = 1
    with patch_target_env(fault_injecting_env):
        with agency_registry.cursor() as cr:
            env = RealEnv(cr, odoo.SUPERUSER_ID, {})
            failed = False
            try:
                env['nexora.client_environment_service'].provision_modules(
                    env_id, ['leads', 'orders']
                )
            except Exception:
                failed = True
            cr.commit()
    ACTIVE['hide'] = set()
    ACTIVE['remaining'] = 0
    check("unavailable module fails safely (no installation)", failed)

    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        check("fail-safe keeps module state observable (failed)",
              rec.module_provisioning_state == 'failed',
              rec.module_provisioning_state)
        check("fail-safe preserves DB lifecycle (still ready, DB intact)",
              rec.status == 'ready' and odoo.service.db.exp_db_exist(db_name))
        check("fail-safe records diagnostic",
              'crm' in (rec.module_provisioning_error or ''),
              (rec.module_provisioning_error or '')[:120])

    # Retry (recovery): reconcile and continue.
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        summary3 = env['nexora.client_environment_service'].provision_modules(
            env_id, ['leads', 'orders']
        )
        cr.commit()
    check("retry after failure recovers to provisioned",
          summary3['state'] == 'provisioned',
          "installed=%s skipped=%s" % (summary3['installed'], summary3['skipped']))
    check("retry skips already-installed modules (no reinstall)",
          'crm' in summary3['skipped'] and 'sale_management' in summary3['skipped'])

    # ── 9. Cleanup: real DB drop of the disposable client DB ────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        rec.action_delete()
        cr.commit()
    check("disposable client DB dropped (real exp_drop)",
          not odoo.service.db.exp_db_exist(db_name), db_name)
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        check("environment record deleted", rec.status == 'deleted', rec.status)

    # ── 10. Final agency integrity ──────────────────────────────────────
    with agency_registry.cursor() as cr:
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        agency_modules_final = dict(cr.fetchall())
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        final_count = env['nexora.client_environment'].search_count([])
    check("agency DB module states identical to baseline",
          agency_modules_final == agency_modules_before)
    check("agency control-plane consistent (env records +1, deleted)",
          final_count == agency_env_count_before + 1,
          "before=%s after=%s" % (agency_env_count_before, final_count))

    elapsed = time.time() - t0
    _logger.info("LLM calls added by module provisioning: 0 (deterministic policy)")
    _logger.info("E2E completed in %.1fs - %d checks", elapsed, len(RESULTS))
    for name, status, detail in RESULTS:
        print("%s  %s  %s" % (status, name, detail))


def patch_target_env(factory):
    """Patch odoo.api.Environment for the fault-injection step only."""
    from unittest.mock import patch
    return patch('odoo.api.Environment', factory)


if __name__ == '__main__':
    main()
