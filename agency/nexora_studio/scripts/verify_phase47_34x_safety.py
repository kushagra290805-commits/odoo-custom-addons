# -*- coding: utf-8 -*-
"""Phase 47.34.x — Real runtime agency-DB safety verification.

Proves, against the LIVE environment (no mocks for the lifecycle):
    1. fail-closed identity checks (real runtime config form)
    2. naming-collision rejection at creation
    3. disposable client DB: create → verify identity → delete → verify
    4. agency DB: exists, accessible, never selected, snapshot unchanged

The disposable client DB is real (exp_create_database / exp_drop) and is
NEVER the agency DB — identity is proven before every operation.

Usage:
    python scripts/verify_phase47_34x_safety.py
"""
import sys
import time

sys.path.append(r"D:\ODOO\community\odoo")
import odoo  # noqa: E402
import odoo.tools  # noqa: E402,F401  (bind odoo.tools for namespace layout)
import odoo.service.db  # noqa: E402,F401

logging_setup_done = False

RESULTS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    print("[%s] %s :: %s" % (status, name, detail))
    if not condition:
        raise AssertionError("Safety check failed: %s :: %s" % (name, detail))


def main():
    t0 = time.time()
    odoo.tools.config.parse_config(
        ['-c', r'D:\ODOO\configs\dev.conf', '-d', 'nexora_studio']
    )
    from odoo.modules.registry import Registry
    from odoo.api import Environment
    from odoo.exceptions import ValidationError

    agency_registry = Registry('nexora_studio')

    # ── 0. Agency identity + before-snapshot ────────────────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        agency = cr.dbname
        config_form = odoo.tools.config.get('db_name')
        service = env['nexora.client_environment_service']
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_before = dict(cr.fetchall())
        env_count_before = env['nexora.client_environment'].search_count([])

    check("agency DB is nexora_studio", agency == 'nexora_studio',
          "cr.dbname=%s" % agency)
    check("Odoo 19 config db_name representation documented",
          isinstance(config_form, (list, str)),
          "type=%s value=%s" % (type(config_form).__name__, config_form))

    # ── 1. Live fail-closed identity checks (real runtime, no mocks) ────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        service = env['nexora.client_environment_service']
        check("agency DB detected as agency (string input)",
              service._is_agency_database(agency) is True, agency)
        check("legitimate client DB not agency",
              service._is_agency_database('nexora_safety_disposable') is False)

        blocked = False
        try:
            service._is_agency_database([agency])
        except ValidationError:
            blocked = True
        check("list db_name input fails closed (incident class)",
              blocked, "input=%r" % [agency])

        blocked = False
        try:
            service._is_agency_database(None)
        except ValidationError:
            blocked = True
        check("None db_name input fails closed", blocked)

    # ── 2. Naming collision rejection at creation (real) ────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        project = env['nexora.project'].create({
            'name': 'Safety Hardening %s' % time.strftime('%H%M%S'),
            'status': 'draft',
        })
        collision_blocked = False
        try:
            env['nexora.client_environment_service'].create_environment(
                project.id, 'studio'
            )
        except ValidationError:
            collision_blocked = True
        cr.commit()
    check("identifier 'studio' (sanitizes to nexora_studio) rejected at creation",
          collision_blocked, "agency=%s" % agency)

    # ── 3. Disposable client DB lifecycle (real, identity proven first) ─
    ts = time.strftime('%H%M%S')
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        env_rec = env['nexora.client_environment_service'].create_environment(
            project.id, 'safety47x %s' % ts
        )
        env_id = env_rec.id
        db_name = env_rec.db_name
        cr.commit()
    check("disposable DB name is not the agency DB",
          db_name != agency,
          "disposable=%s agency=%s" % (db_name, agency))
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        check("disposable DB identity proven not-agency (live guard)",
              env['nexora.client_environment_service']._is_agency_database(db_name) is False,
              db_name)

    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        rec.action_provision()
        cr.commit()
    check("disposable client DB created (real exp_create_database)",
          odoo.service.db.exp_db_exist(db_name), db_name)
    check("agency DB still exists after client DB creation",
          odoo.service.db.exp_db_exist(agency), agency)

    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['nexora.client_environment'].browse(env_id)
        check("disposable environment ready", rec.status == 'ready', rec.status)
        rec.action_delete()
        cr.commit()
    check("disposable client DB deleted (real exp_drop)",
          not odoo.service.db.exp_db_exist(db_name), db_name)

    # ── 4. Agency after-snapshot ────────────────────────────────────────
    with agency_registry.cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_after = dict(cr.fetchall())
        env_count_after = env['nexora.client_environment'].search_count([])
        check("agency DB accessible (queries succeed)", True, agency)
    check("agency DB module states identical before/after",
          modules_after == modules_before, "changed=%s" % sorted(
              k for k in set(modules_before) | set(modules_after)
              if modules_before.get(k) != modules_after.get(k)
          )[:8])
    check("agency control-plane consistent (env records +1, deleted)",
          env_count_after == env_count_before + 1,
          "before=%s after=%s" % (env_count_before, env_count_after))

    print("Completed in %.1fs — %d checks, LLM calls: 0" % (time.time() - t0, len(RESULTS)))


if __name__ == '__main__':
    main()
