# -*- coding: utf-8 -*-
"""Phase 47.36 — REAL generated-client-frontend binding E2E.

Proves on FRESH generated applications (no manual artifact patching):

    Real brief
      -> RequirementEngine (real, deterministic — capabilities inferred)
      -> PlanningEngine / ArchitectureEngine (real — pattern + sections,
         capability-gated ContactForm composition on the contact page)
      -> DesignOrchestrationEngine (real, real Odoo env — capability
         contract transported to the provider)
      -> ReactRenderingProvider (real — src/lib/clientApi.js + same-origin
         vite proxy scaffold, capability-gated)
      -> WorkspaceGeneratorEngine (real — materialized workspace)
      -> CodeGenerationEngine (real; AI mocked for hero/content copy only —
         LLM calls: 0)
      -> npm install + vite build (canonical build)
      -> REAL vite dev server (the canonical generated-app runtime) with
         the per-environment nex_cli_* token in the SERVER process env
      -> REAL uvicorn BFF (real disposable service account)
      -> REAL Odoo service -> REAL disposable client Odoo DB
      -> real browser (Playwright) — products from the client DB render
         in ProductGrid; ContactForm submission creates a real crm.lead
         in the client DB; agency DB untouched.

Security proofs:
  * token NEVER in generated source, built output, or browser-delivered
    content (scanned, not printed)
  * browser requests are same-origin /api/v1/client/* only (no :8069,
    no direct :8000-class BFF origin from the page)
  * no-token runtime -> deterministic error state (never fake data)
  * empty-catalog environment -> deterministic empty state
  * tenant isolation: same app + tenant B token -> tenant B data only
  * static (no-capability) project -> no API surface at all

Runs with the GLOBAL python (Odoo runtime + playwright + fastapi).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = r'D:\ODOO'
BFF = os.path.join(ROOT, 'nexora-console', 'backend')
ADDON = os.path.join(ROOT, 'custom-addons', 'agency', 'nexora_studio')
WS_ROOT = os.path.join(ADDON, 'scratch', 'e2e4736')

BFF_PORT = 8136
VITE_PORT_LIVE = 5171      # app A1 variants (credential under test)
VITE_PORT_LEADS = 5172     # app B  + tenant A token (lead form)

RESULTS = []
PROCS = []


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


# ---------------------------------------------------------------------------
# Real generation harness (REAL engines; AI mocked for hero/content copy)
# ---------------------------------------------------------------------------

RESTAURANT_BRIEF = (
    "Restaurant website for Trattoria Verde. Show our menu products with "
    "prices. Takeout ordering and reservation bookings by phone."
)
AGENCY_BRIEF = (
    "Marketing agency website for Studio Nord. Include a contact form so "
    "visitors can send inquiries that capture leads for our CRM."
)
STATIC_BRIEF = (
    "Portfolio website for a landscape photographer. Purely visual gallery "
    "showcase."
)


class _E2EAI:
    """Deterministic AI stand-in for the copy-only LLM boundary
    (generate_content + ai_code_patch). Zero real LLM calls."""

    def generate(self, operation, payload):
        if operation == 'ai_code_patch':
            name = payload['task'].split('named ', 1)[1].split(' ', 1)[0]
            return {'full_content':
                    "function %s() { return <section>%s</section> }"
                    % (name, name)}
        if operation == 'generate_content':
            return {'analysis': {'pages': {
                '/': {
                    'seo': {'title': 'Home', 'description': 'Home'},
                    'metadata': {},
                    'sections': [
                        {'type': 'Hero', 'semantic_heading': 'Welcome',
                         'body': 'Welcome to our restaurant.'},
                        {'type': 'About', 'semantic_heading': 'About',
                         'body': 'Our story.'},
                        {'type': 'MenuHighlights',
                         'semantic_heading': 'Our Menu',
                         'body': 'Fresh dishes daily.'},
                        {'type': 'Testimonial',
                         'semantic_heading': 'Kind words',
                         'body': 'Great food.'},
                        {'type': 'ContactCTA', 'semantic_heading': 'Visit',
                         'body': 'Come see us.'},
                    ],
                },
                '/menu': {
                    'seo': {'title': 'Menu', 'description': 'Menu'},
                    'metadata': {},
                    'sections': [
                        {'type': 'Hero', 'semantic_heading': 'Menu',
                         'body': 'Our full menu.'},
                        {'type': 'Content', 'semantic_heading': 'Dishes',
                         'body': 'Seasonal dishes.'},
                    ],
                },
                '/reservations': {
                    'seo': {'title': 'Reservations',
                            'description': 'Reservations'},
                    'metadata': {},
                    'sections': [
                        {'type': 'Hero', 'semantic_heading': 'Reservations',
                         'body': 'Book a table.'},
                        {'type': 'Content', 'semantic_heading': 'Booking',
                         'body': 'Call us.'},
                    ],
                },
                '/contact': {
                    'seo': {'title': 'Contact', 'description': 'Contact'},
                    'metadata': {},
                    'sections': [
                        {'type': 'Hero', 'semantic_heading': 'Contact',
                         'body': 'We would love to hear from you.'},
                        {'type': 'Content', 'semantic_heading': 'Find us',
                         'body': 'Send us a message.'},
                        {'type': 'ContactForm',
                         'semantic_heading': 'Get in touch',
                         'body': 'Send us a message.'},
                    ],
                },
                '/services': {
                    'seo': {'title': 'Services', 'description': 'Services'},
                    'metadata': {},
                    'sections': [
                        {'type': 'Hero', 'semantic_heading': 'Services',
                         'body': 'What we do.'},
                        {'type': 'Content', 'semantic_heading': 'Detail',
                         'body': 'More detail.'},
                    ],
                },
            }}}
        return {'full_content': ''}


class _E2ERuntime:
    """Runtime façade for the REAL engines (workspace/ai/env/metadata)."""

    def __init__(self, workspace_path, odoo_env):
        from odoo.addons.nexora_studio.services.generation.core.workspace_adapter import (
            WorkspaceAdapter)
        from unittest.mock import MagicMock
        self.workspace = WorkspaceAdapter(workspace_path)
        self.ai = _E2EAI()
        self.tools = MagicMock()
        self.orchestrator = MagicMock()
        self.env = odoo_env
        self.metadata = MagicMock(session_id='e2e-4736-session')
        self.hooks = MagicMock()


def generate_app(odoo_env, brief, workspace_path):
    """Run the REAL engine chain for one fresh generated application."""
    from unittest.mock import MagicMock
    from odoo.addons.nexora_studio.services.generation.core.generation_context import (
        WebsiteGenerationArtifact, RequirementModel)
    from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
        RequirementEngine)
    from odoo.addons.nexora_studio.services.generation.engines.planning_engine import (
        PlanningEngine)
    from odoo.addons.nexora_studio.services.generation.engines.architecture_engine import (
        ArchitectureEngine)
    from odoo.addons.nexora_studio.services.generation.engines.design_orchestration_engine import (
        DesignOrchestrationEngine)
    from odoo.addons.nexora_studio.services.generation.engines.template_resolution_engine import (
        TemplateResolutionEngine)
    from odoo.addons.nexora_studio.services.generation.engines.content_engine import (
        ContentEngine)
    from odoo.addons.nexora_studio.services.generation.engines.workspace_generator_engine import (
        WorkspaceGeneratorEngine)
    from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
        CodeGenerationEngine)

    os.makedirs(workspace_path, exist_ok=True)
    runtime = _E2ERuntime(workspace_path, odoo_env)
    artifact = WebsiteGenerationArtifact(
        requirements=RequirementModel(raw_input=brief))

    for engine in (RequirementEngine(MagicMock()),
                   PlanningEngine(MagicMock()),
                   ArchitectureEngine(MagicMock()),
                   DesignOrchestrationEngine(MagicMock()),
                   TemplateResolutionEngine(MagicMock()),
                   ContentEngine(MagicMock()),
                   WorkspaceGeneratorEngine(MagicMock()),
                   CodeGenerationEngine(MagicMock())):
        result = engine.execute(artifact, runtime)
        if not result.success:
            raise RuntimeError('%s failed: %s'
                               % (engine.__class__.__name__, result.error))
        artifact = result.artifact
    return artifact, runtime


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def wait_http(url, tries=90, interval=1.0):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    raise RuntimeError('HTTP wait failed: %s' % url)


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
        stdout=open(os.path.join(WS_ROOT, 'bff.log'), 'w'),
        stderr=subprocess.STDOUT)
    PROCS.append(proc)
    return proc


def spawn_vite(workspace_path, port, token=None, api_url=None):
    """Start the canonical generated-app runtime (the exact ViteLauncher
    command: npm run dev -- --port N --host 127.0.0.1) with the
    per-environment client token in the SERVER process environment."""
    env = dict(os.environ)
    if token is not None:
        env['NEXORA_CLIENT_API_TOKEN'] = token
    else:
        env.pop('NEXORA_CLIENT_API_TOKEN', None)
    env['NEXORA_CLIENT_API_URL'] = api_url or (
        'http://127.0.0.1:%d' % BFF_PORT)
    proc = subprocess.Popen(
        ['npm.cmd', 'run', 'dev', '--', '--port', str(port),
         '--host', '127.0.0.1', '--strictPort'],
        cwd=workspace_path, env=env,
        stdout=open(os.path.join(WS_ROOT, 'vite_%d.log' % port), 'a'),
        stderr=subprocess.STDOUT)
    PROCS.append(proc)
    return proc


def _kill_orphan_esbuild():
    """Kill orphaned esbuild service processes spawned under the E2E
    workspace root (vite children that outlive their parent and lock
    node_modules files, breaking the next npm install). Best effort."""
    if os.name != 'nt':
        return
    try:
        out = subprocess.run(
            ['wmic', 'process', 'where', "name='esbuild.exe'",
             'get', 'processid,executablepath'],
            capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return
    for line in out.splitlines():
        line = line.strip()
        if not line or WS_ROOT.lower() not in line.lower():
            continue
        pid = line.split()[-1]
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', pid],
                           capture_output=True)
        except Exception:
            pass


def kill_proc(proc, timeout=15):
    """Kill the process AND its children (npm.cmd -> node/vite tree —
    terminating only the wrapper leaves the vite child holding the port).
    The tree kill MUST run while the parent is still alive (taskkill /T
    enumerates children through it)."""
    if proc is None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                           capture_output=True)
        except Exception:
            pass
    else:
        try:
            import psutil
            parent = psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=timeout)
    except Exception:
        pass


def _free_port(port):
    """Kill whatever still LISTENS on the port (orphaned vite child) and
    wait for the socket release. Best effort; Windows-only."""
    if os.name != 'nt':
        return
    for _ in range(10):
        try:
            out = subprocess.run(['netstat', '-ano', '-p', 'TCP'],
                                 capture_output=True, text=True).stdout
        except Exception:
            return
        pids = []
        for line in out.splitlines():
            parts = line.split()
            if (len(parts) >= 5 and parts[0] == 'TCP'
                    and 'LISTENING' in line
                    and parts[1].endswith(':%d' % port)):
                pids.append(parts[-1])
        if not pids:
            return
        for pid in dict.fromkeys(pids):
            try:
                subprocess.run(['taskkill', '/F', '/T', '/PID', pid],
                               capture_output=True)
            except Exception:
                pass
        time.sleep(1)


def scan_tree_for_markers(root, markers):
    """Scan every text file under root for secret markers.

    Returns {marker: [relative paths]} — marker VALUES are never printed.
    """
    hits = {m: [] for m in markers}
    for dirpath, _dirs, files in os.walk(root):
        if 'node_modules' in dirpath:
            continue
        for fname in files:
            path = os.path.join(dirpath, fname)
            rel = os.path.relpath(path, root)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            except Exception:
                continue
            for marker in markers:
                if marker in content:
                    hits[marker].append(rel)
    return hits


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _free_e2e_ports():
    """Defensive port hygiene: kill any zombie process still listening on
    the E2E ports (a previously aborted run leaves its vite/BFF children
    behind; a stale BFF with invalidated credentials would poison this
    run). Windows-only; best effort."""
    if os.name != 'nt':
        return
    import subprocess as _sp
    for port in (BFF_PORT, VITE_PORT_LIVE, VITE_PORT_LEADS):
        try:
            out = _sp.run(
                ['netstat', '-ano', '-p', 'TCP'],
                capture_output=True, text=True).stdout
        except Exception:
            continue
        for line in out.splitlines():
            parts = line.split()
            if (len(parts) >= 5 and parts[0] == 'TCP'
                    and 'LISTENING' in line
                    and (':%d ' % port) in ('%s ' % parts[1])):
                try:
                    _sp.run(['taskkill', '/F', '/T', '/PID', parts[-1]],
                            capture_output=True)
                except Exception:
                    pass
    time.sleep(2)


def main():
    os.makedirs(WS_ROOT, exist_ok=True)
    _free_e2e_ports()
    t0 = time.time()
    registry, odoo = _registry()

    # ── 0. Agency before-snapshot ─────────────────────────────────────
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        agency = cr.dbname
        check("agency DB identified", agency == 'nexora_studio', agency)
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_before = dict(cr.fetchall())
        env_count_before = env['nexora.client_environment'].search_count([])
        agency_leads_before = 0
        try:
            cr.execute("SELECT count(*) FROM crm_lead")
            agency_leads_before = cr.fetchone()[0]
        except Exception:
            pass

    ts = time.strftime('%H%M%S')

    # ── 1. Disposable client environments A (data), B (tenant), C (empty)
    def _make_env(label, seed_product_name):
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            project = env['nexora.project'].create({
                'name': 'P4736 E2E %s %s' % (label, ts),
                'status': 'draft'})
            rec = env['nexora.client_environment_service'].create_environment(
                project.id, 'e2e4736%s %s' % (label.lower(), ts))
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
        check("client env %s provisioned (product+crm installed)" % label,
              summary['state'] == 'provisioned', "db=%s" % db)
        if seed_product_name:
            from odoo.modules.registry import Registry as _Reg
            with _Reg(db).cursor() as cr:
                cenv = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                cenv['product.product'].create({
                    'name': seed_product_name, 'list_price': 19.5,
                    'default_code': 'E2E-%s-%s' % (label, ts)})
                cr.commit()
        with registry.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            token = env['nexora.client_environment_service'] \
                .issue_client_api_token(env_id)['token']
            cr.commit()
        return env_id, db, token

    product_a = 'Trattoria Special %s' % ts
    product_b = 'Bistro Classic %s' % ts
    env_a_id, db_a, token_a = _make_env('A', product_a)
    env_b_id, db_b, token_b = _make_env('B', product_b)
    env_c_id, db_c, token_c = _make_env('C', None)  # empty catalog
    check("three distinct client DBs",
          len({db_a, db_b, db_c, agency}) == 4,
          "A/B/C distinct from agency")

    # ── 2. FRESH generations (real engines, mocked copy AI) ───────────
    ws_a1 = os.path.join(WS_ROOT, 'gen_a1')
    ws_a2 = os.path.join(WS_ROOT, 'gen_a2')
    ws_b = os.path.join(WS_ROOT, 'gen_b')
    ws_s = os.path.join(WS_ROOT, 'gen_static')

    # One long-lived cursor hosts the Odoo env the real
    # DesignOrchestrationEngine routes through (nexora.design_orchestrator).
    gen_cr = registry.cursor()
    odoo_env = odoo.api.Environment(gen_cr, odoo.SUPERUSER_ID, {})

    artifact_a1, _ = generate_app(odoo_env, RESTAURANT_BRIEF, ws_a1)
    check("generation A1: real capability inference (products)",
          'products' in artifact_a1.requirements.capabilities,
          str(artifact_a1.requirements.capabilities))
    check("generation A1: backend_required",
          artifact_a1.requirements.backend_required, "")
    artifact_a2, _ = generate_app(odoo_env, RESTAURANT_BRIEF, ws_a2)
    artifact_b, _ = generate_app(odoo_env, AGENCY_BRIEF, ws_b)
    check("generation B: real capability inference (leads)",
          'leads' in artifact_b.requirements.capabilities,
          str(artifact_b.requirements.capabilities))
    artifact_s, _ = generate_app(odoo_env, STATIC_BRIEF, ws_s)
    check("generation S: static project (no backend capabilities)",
          not artifact_s.requirements.backend_required
          and not artifact_s.requirements.capabilities,
          str(artifact_s.requirements.capabilities))
    gen_cr.close()

    # ── 3. Binding presence (fresh generations, unpatched) ────────────
    def read(ws, rel):
        with open(os.path.join(ws, rel), 'r', encoding='utf-8') as fh:
            return fh.read()

    for ws, label in ((ws_a1, 'A1'), (ws_a2, 'A2')):
        check("gen %s: clientApi module materialized" % label,
              os.path.exists(os.path.join(ws, 'src/lib/clientApi.js')), "")
        check("gen %s: vite proxy scaffold present" % label,
              "'/api/v1/client'" in read(ws, 'vite.config.js')
              and 'NEXORA_CLIENT_API_TOKEN' in read(ws, 'vite.config.js'), "")
        home = read(ws, 'src/pages/index.tsx')
        check("gen %s: ProductGrid bound to Client API" % label,
              'useClientProducts' in home
              and 'clientApi.js' in home
              and 'ProductGrid data-nexora-source="native/ProductGrid"'
              in home, "")
        check("gen %s: deterministic loading/empty/error states" % label,
              'productsState.loading' in home
              and 'productsState.error' in home
              and 'products.length === 0' in home, "")

    # Fresh-generation determinism (source-of-truth): identical binding.
    for rel in ('src/lib/clientApi.js', 'vite.config.js',
                'src/pages/index.tsx', 'src/components/ContactForm.jsx'):
        check("determinism: %s identical across fresh generations" % rel,
              read(ws_a1, rel) == read(ws_a2, rel), "")

    contact_b = read(ws_b, 'src/pages/contact.tsx')
    check("gen B: ContactForm bound to Client API (leads)",
          'clientApi.createLead' in contact_b
          and 'onSubmitLead' in contact_b, "")
    check("gen B: no products binding (no MenuHighlights in pattern)",
          'useClientProducts' not in contact_b, "")

    # Static mode: the binding is the WIRING (clientApi module, proxy,
    # section-level API calls) — the native library always ships its
    # components (ContactForm's optional onSubmitLead prop is inert
    # without a bound section; the component library is byte-identical
    # across projects by design, ADR-0077).
    static_binding_surface = read(ws_s, 'vite.config.js')
    static_binding_surface += read(ws_s, 'src/App.jsx')
    for dirpath, _d, files in os.walk(os.path.join(ws_s, 'src/pages')):
        for f in files:
            with open(os.path.join(dirpath, f), encoding='utf-8') as fh:
                static_binding_surface += fh.read()
    check("gen S (static): no clientApi module / proxy / bound sections",
          not os.path.exists(os.path.join(ws_s, 'src/lib/clientApi.js'))
          and '/api/v1/client' not in static_binding_surface
          and 'clientApi' not in static_binding_surface
          and 'useClientProducts' not in static_binding_surface
          and 'onSubmitLead=' not in static_binding_surface, "")

    # ── 4. Canonical build (npm install + vite build) ─────────────────
    _kill_orphan_esbuild()

    def build(ws, label):
        log = os.path.join(WS_ROOT, 'build_%s.log' % label)
        with open(log, 'w') as lf:
            r = subprocess.run(['npm.cmd', 'install', '--no-audit',
                                '--no-fund'], cwd=ws, stdout=lf,
                               stderr=subprocess.STDOUT, timeout=900)
            if r.returncode != 0:
                return False
            r = subprocess.run(['npm.cmd', 'run', 'build'], cwd=ws,
                               stdout=lf, stderr=subprocess.STDOUT,
                               timeout=600)
            return r.returncode == 0

    check("fresh app A1 builds (npm install + vite build)",
          build(ws_a1, 'a1'), "see build_a1.log")
    check("fresh app B builds (npm install + vite build)",
          build(ws_b, 'b'), "see build_b.log")

    # ── 5. Token/credential exposure scan (source + dist) ────────────
    markers = ['nex_cli_', 'ODOO_PASSWORD', 'ODOO_USERNAME',
               'JWT_SECRET', 'fernet', 'Fernet']
    for ws, label in ((ws_a1, 'A1'), (ws_b, 'B')):
        hits = scan_tree_for_markers(ws, markers)
        leaked = {m: p for m, p in hits.items() if p}
        check("gen %s: no client token/credentials in source+build output"
              % label, not leaked,
              json.dumps({m: len(p) for m, p in leaked.items()}))
    dist_hits = scan_tree_for_markers(os.path.join(ws_a1, 'dist'),
                                      ['nex_cli_'])
    check("gen A1 dist/: no nex_cli_ in built assets",
          not dist_hits['nex_cli_'], "")

    # ── 6. Real BFF + real vite runtime ───────────────────────────────
    svc_login = 'p4736-svc@nexora.local'
    svc_pwd = 'Svc-E2E-4736!disposable'
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        existing = env['res.users'].search([('login', '=', svc_login)])
        if existing:
            existing.unlink()
        user = env['res.users'].create({
            'name': 'P4736 Disposable Service Account',
            'login': svc_login, 'password': svc_pwd,
            'group_ids': [(4, env.ref('base.group_system').id)]})
        svc_user_id = user.id
        cr.commit()

    spawn_bff(BFF_PORT, {
        'ODOO_USERNAME': svc_login,
        'ODOO_PASSWORD': svc_pwd,
        'JWT_SECRET': 'e2e-4736-secret-for-real-http-run',
    })
    wait_http('http://127.0.0.1:%d/api/v1/health' % BFF_PORT)
    check("real BFF up (uvicorn :%d)" % BFF_PORT, True, "")

    # One vite dev server per workspace at a time (vite's dependency cache
    # is per-workspace; concurrent dev servers on one workspace corrupt
    # it). Variant runs are sequential — each is a realistic single
    # deployment of the same generated app with a different runtime
    # credential.
    live_proc = None
    leads_proc = None

    def start_live(token):
        nonlocal live_proc
        if live_proc:
            kill_proc(live_proc)
            PROCS.remove(live_proc)
            live_proc = None
            _free_port(VITE_PORT_LIVE)
        live_proc = spawn_vite(ws_a1, VITE_PORT_LIVE, token=token)
        wait_http('http://127.0.0.1:%d/' % VITE_PORT_LIVE, tries=120)

    # ── 7. Real browser verification (Playwright) ─────────────────────
    from playwright.sync_api import sync_playwright

    console_errors = []
    bad_requests = []
    api_requests = []
    allowed_4xx = []

    start_live(token_a)
    leads_proc = spawn_vite(ws_b, VITE_PORT_LEADS, token=token_a)
    wait_http('http://127.0.0.1:%d/' % VITE_PORT_LEADS, tries=120)
    check("generated-app runtimes up (vite dev servers)", True, "")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        def new_page():
            ctx = browser.new_context()
            page = ctx.new_page()
            page.on('console', lambda msg: (
                console_errors.append(msg.text)
                if msg.type == 'error' else None))
            page.on('pageerror', lambda err: console_errors.append(str(err)))
            page.on('response', lambda resp: (
                bad_requests.append('%s %s' % (resp.status, resp.url))
                if resp.status >= 400 else None))
            page.on('request', lambda req: (
                api_requests.append(req.url)
                if '/api/v1/client/' in req.url else None))
            return ctx, page

        # 7a. LIVE products from the client DB render in ProductGrid.
        ctx, page = new_page()
        page.goto('http://127.0.0.1:%d/' % VITE_PORT_LIVE,
                  wait_until='networkidle')
        body_text = page.inner_text('body')
        check("browser: client-DB product renders in ProductGrid",
              product_a in body_text, product_a)
        check("browser: products request was same-origin client API",
              any('/api/v1/client/products' in u for u in api_requests),
              str([u.split('/')[-2:] for u in api_requests][:3]))
        check("browser: no direct Odoo/BFF origin from the page",
              not any((':8069' in u or ':%d' % BFF_PORT in u)
                      for u in api_requests), "")
        page_content = page.content()
        check("browser: no client token in delivered page",
              'nex_cli_' not in page_content, "")
        ctx.close()

        # 7b. LEAD form -> real crm.lead in the client DB.
        ctx, page = new_page()
        page.goto('http://127.0.0.1:%d/contact' % VITE_PORT_LEADS,
                  wait_until='networkidle')
        lead_name = 'E2E Lead %s' % ts
        page.fill('#contact-name', lead_name)
        page.fill('#contact-email', 'e2e-4736@example.com')
        page.fill('#contact-message',
                  'Phase 47.36 real frontend lead submission')
        page.click('button[type="submit"]')
        page.wait_for_selector('text=Message Sent!', timeout=15000)
        check("browser: lead submission success state", True, "")
        ctx.close()
        browser.close()

    # Variant runs (sequential, same generated app A1 on the same port,
    # different runtime credentials): no-token error state, empty-catalog
    # state, tenant B.
    def run_variant(token):
        allowed_4xx.clear()
        from playwright.sync_api import sync_playwright as _sp
        start_live(token)
        with _sp() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.on('response', lambda resp: (
                allowed_4xx.append('%s %s' % (resp.status, resp.url))
                if resp.status >= 400 else None))
            page.goto('http://127.0.0.1:%d/' % VITE_PORT_LIVE,
                      wait_until='networkidle')
            text = page.inner_text('body')
            html = page.content()
            browser.close()
        return text, html

    # 7c. ERROR state when the runtime holds no credential (401 path).
    body, html = run_variant(None)
    check("browser: deterministic error state without credential",
          'temporarily unavailable' in body and product_a not in body,
          body[:80])
    check("browser: error variant serves no fake data",
          product_a not in html, "")

    # 7d. EMPTY state for an empty catalog.
    body, html = run_variant(token_c)
    check("browser: deterministic empty state (empty catalog)",
          'being updated' in body, body[:80])

    # 7e. TENANT ISOLATION: same app, tenant B credential.
    body, html = run_variant(token_b)
    check("browser: tenant B data via tenant B credential",
          product_b in body, product_b)
    check("browser: tenant A data NOT exposed to tenant B runtime",
          product_a not in body, "")

    check("browser: zero console errors across all runs",
          not [e for e in console_errors
               if 'fonts.googleapis' not in e
               and 'fonts.gstatic' not in e],
          str(console_errors[:3]))
    expected_401 = ('401 http://127.0.0.1:%d/api/v1/client/products'
                    % VITE_PORT_LIVE)
    unexpected_4xx = [r for r in (bad_requests + allowed_4xx)
                      if r != expected_401]
    check("browser: no unexpected failed requests",
          not unexpected_4xx, str(unexpected_4xx[:3]))

    if live_proc:
        kill_proc(live_proc)
    if leads_proc:
        kill_proc(leads_proc)

    # ── 8. Client DB provenance (direct registry verification) ────────
    from odoo.modules.registry import Registry as _Reg
    with _Reg(db_a).cursor() as cr:
        cenv = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        lead = cenv['crm.lead'].search(
            [('name', '=', lead_name)], limit=1)
        check("lead created in CLIENT DB A (direct registry read)",
              bool(lead), lead_name)
        prods = cenv['product.product'].search_count([])
        check("client DB A has real product data", prods >= 1, str(prods))
    with _Reg(db_b).cursor() as cr:
        cenv = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        lead_b = cenv['crm.lead'].search(
            [('name', '=', lead_name)], limit=1)
        check("lead NOT in client DB B (tenant isolation)",
              not lead_b, "")
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        try:
            cr.execute("SELECT count(*) FROM crm_lead")
            agency_leads_after = cr.fetchone()[0]
        except Exception:
            agency_leads_after = agency_leads_before
        check("agency DB: no new leads",
              agency_leads_after == agency_leads_before, "")
        cr.execute("SELECT name, state FROM ir_module_module ORDER BY name")
        modules_after = dict(cr.fetchall())
        check("agency DB: module state unchanged",
              modules_before == modules_after, "")
        env_count_after = env['nexora.client_environment'].search_count([])
        check("agency DB: only the 3 disposable env records added",
              env_count_after - env_count_before == 3, "")

    # ── 9. Network proof summary ──────────────────────────────────────
    check("network: every API request was same-origin /api/v1/client/*",
          api_requests and all(
              u.startswith('http://127.0.0.1:5') and
              '/api/v1/client/' in u for u in api_requests),
          str(api_requests[:2]))

    # ── 10. Cleanup ───────────────────────────────────────────────────
    for proc in list(PROCS):
        kill_proc(proc)
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        for env_id in (env_a_id, env_b_id, env_c_id):
            env['nexora.client_environment'].browse(env_id).action_delete()
        cr.commit()
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        rec = env['res.users'].browse(svc_user_id).exists()
        if rec:
            rec.unlink()
        cr.commit()
    for ws in (ws_a1, ws_a2, ws_b, ws_s):
        shutil.rmtree(ws, ignore_errors=True)
    check("disposable client DBs dropped + service account removed", True, "")

    elapsed = time.time() - t0
    passed = sum(1 for _, s, _ in RESULTS if s == 'PASS')
    print('\nPHASE 47.36 E2E: %d/%d checks PASS in %.1fs (LLM calls: 0)'
          % (passed, len(RESULTS), elapsed))
    for name, status, detail in RESULTS:
        print('  [%s] %s' % (status, name))


def _run_main_with_cleanup():
    """Always kill child processes (vite/BFF/esbuild) even when a check
    fails."""
    try:
        main()
    finally:
        for proc in list(PROCS):
            kill_proc(proc)
        _kill_orphan_esbuild()


if __name__ == '__main__':
    _run_main_with_cleanup()
