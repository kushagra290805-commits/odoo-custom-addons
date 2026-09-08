# -*- coding: utf-8 -*-
"""Phase 47.36 — generated client frontend ↔ Client API binding tests.

Covers the canonical-layer contract of the frontend binding:

  * capability transport (DesignOrchestrationEngine.client_api_binding)
  * provider scaffold: the ONE canonical src/lib/clientApi.js module
    (exact Phase 47.35 endpoints, field whitelist, same-origin relative
    URLs, sanitized errors, NO credentials in browser code)
  * provider scaffold: vite.config.js same-origin Client API proxy with
    SERVER-side token injection (process.env, never browser-readable)
  * capability gating: binding emitted only for backend-capable projects
  * ProductGrid binding (MenuHighlights): API data, explicit projection,
    deterministic loading/empty/error states, static path unchanged
  * ContactForm binding (leads): allowlisted fields only, real submit
    mode, duplicate-submit protection, sanitized errors, legacy mode
    preserved
  * ArchitectureEngine contact-page ContactForm composition (leads)
  * security: no nex_cli_/credential markers, no db/model/method
    selectors, no absolute/hardcoded hosts in browser-delivered code
  * fresh-generation determinism (two identical runs)

NOT registered in tests/__init__.py on purpose: like the 47.27-47.29
standalone suites, this module re-parses the Odoo config at import time
(standalone-script convention) which is incompatible with in-process
odoo-bin test discovery. Run via scripts/run_4736_tests.py or the
touched-suites runner.
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\ODOO\community\odoo')

from odoo.tools import config
import odoo.modules.module as m

config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import odoo  # noqa: E402

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    ArchitectureModel, ComponentTree, Content, RequirementModel, Theme,
    WebsiteGenerationArtifact, Assets)
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine)
from odoo.addons.nexora_studio.services.generation.engines.architecture_engine import (
    ArchitectureEngine)
from odoo.addons.nexora_studio.services.generation.engines.design_orchestration_engine import (
    client_api_binding)
from odoo.addons.nexora_studio.services.design.providers.react_provider import (
    ReactRenderingProvider)
from odoo.addons.nexora_studio.services.design.providers.rendering_provider import (
    RenderingContext)
from odoo.addons.nexora_studio.services.design.react_component_library import (
    ReactComponentLibrary)
from odoo.addons.nexora_studio.services.design.render_domain import RenderProject


# ---------------------------------------------------------------------------
# Harness (same precedent as test_phase47_29_client_quality)
# ---------------------------------------------------------------------------

class _ScaffoldWorkspace:
    """In-memory workspace: native library scaffold + optional clientApi."""

    def __init__(self, include_client_api=False):
        self.files = dict(ReactComponentLibrary().synthesize_all())
        if include_client_api:
            self.files['src/lib/clientApi.js'] = (
                ReactRenderingProvider()._generate_client_api_js())

    def write_file(self, path, content):
        self.files[path] = content

    def write_binary(self, path, data):
        self.files[path] = b'<binary>'

    def read_file(self, path):
        return self.files.get(path, '')

    def exists(self, path):
        return path in self.files


def _artifact(domain, business, sections_home, content_pages, **kwargs):
    return WebsiteGenerationArtifact(
        requirements=RequirementModel(
            domain=domain, business_name=business,
            business_category=kwargs.get(
                'business_category', '%s business' % domain),
            capabilities=kwargs.get('capabilities') or [],
            backend_required=bool(kwargs.get('capabilities')),
            branding=kwargs.get('branding') or {
                'business_name': business,
                'services': kwargs.get('services') or ['service one',
                                                       'service two']}),
        architecture=ArchitectureModel(component_hierarchy={
            'home': {'type': 'page', 'path': '/', 'sections': sections_home},
            'contact': {'type': 'page', 'path': '/contact',
                        'sections': ['Hero', 'Content']},
        }),
        component_tree=ComponentTree(nodes=[], dependencies=['react']),
        theme=Theme(colors={'background': '#f8fafc', 'foreground': '#0f172a',
                            'primary': '#3f5c76', 'primary_foreground': '#ffffff',
                            'secondary': '#475569', 'accent': '#0e7490',
                            'border': '#e2e8f0', 'muted': '#5f6b7a',
                            'card': '#ffffff'}),
        content=Content(pages=content_pages),
        assets=Assets(images=[], icons=[], fonts=[]),
        generation_metadata={'page_pattern': {
            'id': 'test', 'home_sections': sections_home,
            'secondary_sections': ['Hero', 'Content']}})


def _menu_content_pages():
    return {
        '/': {
            'sections': [{
                'type': 'MenuHighlights',
                'semantic_heading': 'Our menu',
                'body': 'Fresh dishes daily.',
                'items': [
                    {'title': 'Bruschetta', 'price': '8.50',
                     'body': 'Tomato, basil, olive oil'},
                    {'title': 'Ravioli', 'price': '14.00',
                     'body': 'Handmade pasta'},
                ],
            }],
        },
        '/contact': {
            'sections': [
                {'type': 'Hero', 'semantic_heading': 'Contact',
                 'body': 'We would love to hear from you.'},
                {'type': 'Content', 'semantic_heading': 'Find us',
                 'body': 'Come visit.'},
            ],
        },
    }


def _run_codegen(artifact, include_client_api=False):
    engine = CodeGenerationEngine(MagicMock())
    workspace = _ScaffoldWorkspace(include_client_api=include_client_api)

    def gen(op, payload):
        return {'full_content': 'function X() { return <section /> }'}

    runtime = SimpleNamespace(ai=SimpleNamespace(generate=gen),
                              workspace=workspace)
    result = engine.execute(artifact, runtime)
    return result, workspace


def _ctx(output_config=None):
    return SimpleNamespace(output_config=output_config or {})


# ---------------------------------------------------------------------------
# 1. Capability transport (DesignOrchestrationEngine)
# ---------------------------------------------------------------------------

class TestCapabilityTransport(unittest.TestCase):

    def test_binding_disabled_without_capabilities(self):
        binding = client_api_binding(_artifact('Agency', 'Static Co',
                                               ['Hero', 'ContactCTA'], []))
        self.assertEqual(binding,
                         {'enabled': False, 'products': False,
                          'leads': False})

    def test_products_capability_enables_products_binding(self):
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights', 'ContactCTA'],
                             _menu_content_pages(),
                             capabilities=['products', 'bookings'])
        binding = client_api_binding(artifact)
        self.assertTrue(binding['enabled'])
        self.assertTrue(binding['products'])
        self.assertFalse(binding['leads'])

    def test_leads_capability_enables_leads_binding(self):
        artifact = _artifact('Agency', 'Lead Co', ['Hero', 'ContactCTA'],
                             [], capabilities=['leads', 'contacts'])
        binding = client_api_binding(artifact)
        self.assertTrue(binding['enabled'])
        self.assertTrue(binding['leads'])
        self.assertFalse(binding['products'])

    def test_unsupported_capabilities_produce_no_binding(self):
        # Only capabilities with an existing Phase 47.35 Client API
        # operation can bind — unsupported ones must not emit API code.
        artifact = _artifact('Healthcare', 'Clinic', ['Hero', 'ContactCTA'],
                             [], capabilities=['appointments', 'payments'])
        binding = client_api_binding(artifact)
        self.assertFalse(binding['enabled'])
        self.assertFalse(binding['products'])
        self.assertFalse(binding['leads'])


# ---------------------------------------------------------------------------
# 2. Provider scaffold: the ONE canonical clientApi module
# ---------------------------------------------------------------------------

class TestClientApiModule(unittest.TestCase):

    def setUp(self):
        self.provider = ReactRenderingProvider()
        self.code = self.provider._generate_client_api_js()

    def test_module_uses_exact_phase4735_contract(self):
        self.assertIn("'/api/v1/client'", self.code)
        self.assertIn("'/products?limit='", self.code)
        self.assertIn("'/leads'", self.code)
        self.assertIn("'POST'", self.code)
        # ONE canonical client — no alternative endpoint vocabulary.
        self.assertNotIn('/frontend/', self.code)
        self.assertNotIn('/website/', self.code)
        self.assertNotIn('/public/', self.code)

    def test_module_same_origin_only_no_hardcoded_hosts(self):
        # Relative base only: no absolute URLs / hosts in browser code.
        self.assertNotIn('http://', self.code)
        self.assertNotIn('https://', self.code)
        self.assertNotIn('localhost', self.code)
        self.assertNotIn('127.0.0.1', self.code)
        self.assertNotIn(':8069', self.code)
        self.assertNotIn(':8000', self.code)

    def test_module_holds_no_credentials(self):
        # The browser module must never contain or read a credential.
        self.assertNotIn('nex_cli_', self.code)
        self.assertNotIn('Bearer', self.code)
        self.assertNotIn('Authorization', self.code)
        self.assertNotIn('localStorage', self.code)
        self.assertNotIn('sessionStorage', self.code)
        self.assertNotIn('VITE_', self.code)
        self.assertNotIn('process.env', self.code)

    def test_module_has_no_backend_selectors(self):
        # Strip JS comments first (the security-contract banner names the
        # forbidden concepts by design); selectors must not exist in code.
        code_only = '\n'.join(
            line for line in self.code.split('\n')
            if not line.strip().startswith('//'))
        for forbidden in ('db_name', 'environment_id', 'execute_kw',
                          'call_kw', 'kwargs', 'model:'):
            self.assertNotIn(forbidden, code_only)
        # 'method' appears only as the fetch HTTP option (POST) — never
        # as a payload selector.
        self.assertEqual(code_only.count('method:'), 1)
        self.assertIn("method: 'POST'", code_only)

    def test_products_projection_is_explicit(self):
        # Only the Phase 47.35 product projection is mapped.
        for field in ('name', 'price', 'sku', 'id'):
            self.assertIn('%s:' % field, self.code)
        self.assertNotIn('description', self.code.split('export const clientApi')[1])

    def test_lead_payload_is_narrower_than_odoo_schema(self):
        lead_section = self.code.split('createLead')[1][:900]
        self.assertIn('name', lead_section)
        self.assertIn('email', lead_section)
        self.assertIn('message', lead_section)
        # No Odoo-internal lead fields are forwarded.
        for forbidden in ('partner_id', 'stage_id', 'user_id', 'company_id',
                          'team_id', 'crm.lead'):
            self.assertNotIn(forbidden, lead_section)

    def test_hook_has_deterministic_states_and_single_fetch(self):
        self.assertIn('useClientProducts', self.code)
        self.assertIn('loading: true', self.code)
        self.assertIn('error:', self.code)
        # single fetch per mount (empty dependency array, cancellation flag)
        self.assertIn('}, []);', self.code)
        self.assertIn('cancelled', self.code)

    def test_error_contract_is_sanitized(self):
        self.assertIn('CLIENT_NETWORK_ERROR', self.code)
        # raw transport error text is never surfaced
        self.assertNotIn('err.message', self.code)
        self.assertNotIn('String(err)', self.code)

    def test_scaffold_emission_is_capability_gated(self):
        project = RenderProject(name='Bound App')
        disabled = RenderingContext.from_project(
            project, output_config={'client_api': {
                'enabled': False, 'products': False, 'leads': False}})
        enabled = RenderingContext.from_project(
            project, output_config={'client_api': {
                'enabled': True, 'products': True, 'leads': True}})
        result_off = self.provider.generate_project(disabled)
        result_on = self.provider.generate_project(enabled)
        self.assertEqual(result_off['status'], 'success')
        self.assertEqual(result_on['status'], 'success')
        self.assertNotIn('src/lib/clientApi.js',
                         result_off['project_structure'])
        self.assertIn('src/lib/clientApi.js', result_on['project_structure'])
        self.assertEqual(
            result_on['project_structure']['src/lib/clientApi.js'], self.code)


# ---------------------------------------------------------------------------
# 3. Provider scaffold: vite proxy (server-side token boundary)
# ---------------------------------------------------------------------------

class TestViteProxy(unittest.TestCase):

    def setUp(self):
        self.provider = ReactRenderingProvider()

    def _config(self, enabled):
        project = RenderProject(name='Proxy App')
        ctx = RenderingContext.from_project(project, output_config={
            'client_api': {'enabled': enabled, 'products': enabled,
                           'leads': enabled}})
        return self.provider._generate_vite_config(ctx)

    def test_proxy_emitted_when_binding_enabled(self):
        cfg = self._config(True)
        self.assertIn("'/api/v1/client'", cfg)
        self.assertIn('NEXORA_CLIENT_API_URL', cfg)
        self.assertIn('NEXORA_CLIENT_API_TOKEN', cfg)
        self.assertIn('proxyReq', cfg)
        self.assertIn("Bearer ' + token", cfg)

    def test_proxy_absent_when_binding_disabled(self):
        cfg = self._config(False)
        self.assertNotIn('/api/v1/client', cfg)
        self.assertNotIn('NEXORA_CLIENT_API_TOKEN', cfg)
        self.assertNotIn('proxy', cfg)

    def test_token_lives_only_in_server_process_env(self):
        cfg = self._config(True)
        # vite only exposes VITE_*-prefixed vars to browser code; the
        # credential must be read exclusively via process.env in the
        # Node-side config, never via import.meta.env.
        self.assertNotIn('import.meta.env', cfg)
        self.assertNotIn('VITE_', cfg)
        self.assertNotIn('nex_cli_', cfg)

    def test_base_config_shape_preserved(self):
        cfg = self._config(False)
        self.assertIn("plugins: [react()]", cfg)
        cfg_on = self._config(True)
        self.assertIn("plugins: [react()]", cfg_on)
        self.assertIn('defineConfig', cfg_on)


# ---------------------------------------------------------------------------
# 4. ProductGrid binding (MenuHighlights)
# ---------------------------------------------------------------------------

class TestProductGridBinding(unittest.TestCase):

    def _bound_section(self):
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights', 'ContactCTA'],
                             _menu_content_pages(),
                             capabilities=['products', 'leads'])
        result, workspace = _run_codegen(artifact, include_client_api=True)
        self.assertTrue(result.success, result.error)
        home = workspace.read_file('src/pages/index.tsx')
        return home, workspace

    def test_api_bound_menuhighlights_generated(self):
        home, workspace = self._bound_section()
        self.assertIn('useClientProducts(6)', home)
        self.assertIn("import { useClientProducts } from '../lib/clientApi.js'",
                      home)
        self.assertIn('<ProductGrid data-nexora-source="native/ProductGrid"',
                      home)
        self.assertIn('products={products}', home)

    def test_explicit_projection_only(self):
        home, _ = self._bound_section()
        # API projection -> ProductGrid props: name/price/sku only.
        self.assertIn('title: p.name', home)
        self.assertIn('String(p.price)', home)
        self.assertIn("p.sku", home)
        for forbidden in ('p.description', 'p.list_price', 'p.default_code',
                          'qty_available', 'categ_id'):
            self.assertNotIn(forbidden, home)

    def test_deterministic_loading_empty_error_states(self):
        home, _ = self._bound_section()
        self.assertIn('productsState.loading', home)
        self.assertIn('productsState.error', home)
        self.assertIn('products.length === 0', home)
        self.assertIn('role="status"', home)
        self.assertIn('role="alert"', home)

    def test_single_source_no_static_products_array(self):
        # The static products const must NOT coexist with the live binding.
        home, _ = self._bound_section()
        bound_part = home.split('useClientProducts')[1]
        self.assertNotIn("'Bruschetta'", bound_part)
        self.assertNotIn('const products = [', bound_part.split('map')[0])

    def test_section_passes_static_validation(self):
        # The API-bound section must satisfy the assembler's own
        # deterministic validation (known identifiers incl. clientApi).
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights', 'ContactCTA'],
                             _menu_content_pages(),
                             capabilities=['products'])
        engine = CodeGenerationEngine(MagicMock())
        code, imports = engine._menuhighlights_api_bound(
            'MenuHighlightsSection2', 'Our menu')
        issues = CodeGenerationEngine._section_module_issues(
            'MenuHighlightsSection2', code,
            known_identifiers={'ProductGrid', 'useClientProducts'})
        self.assertEqual(issues, [])
        self.assertIn("import ProductGrid from '../components/ProductGrid.jsx'",
                      imports)
        self.assertIn("import { useClientProducts } from '../lib/clientApi.js'",
                      imports)

    def test_static_path_unchanged_without_capability(self):
        # Regression guard: no products capability -> the exact Phase
        # 47.27/47.29 static ProductGrid composition (structured items).
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights', 'ContactCTA'],
                             _menu_content_pages())
        result, workspace = _run_codegen(artifact)
        self.assertTrue(result.success, result.error)
        home = workspace.read_file('src/pages/index.tsx')
        self.assertIn("'Bruschetta'", home)
        self.assertNotIn('useClientProducts', home)
        self.assertNotIn("clientApi.js", home)

    def test_products_request_not_emitted_for_leads_only_project(self):
        artifact = _artifact('Restaurant', 'Trattoria',
                             ['Hero', 'MenuHighlights', 'ContactCTA'],
                             _menu_content_pages(),
                             capabilities=['leads'])
        result, workspace = _run_codegen(artifact, include_client_api=True)
        self.assertTrue(result.success, result.error)
        home = workspace.read_file('src/pages/index.tsx')
        self.assertNotIn('useClientProducts', home)
        # static items still render (MenuHighlights unchanged)
        self.assertIn("'Bruschetta'", home)


# ---------------------------------------------------------------------------
# 5. ContactForm binding (leads)
# ---------------------------------------------------------------------------

class TestContactFormLeadBinding(unittest.TestCase):

    def setUp(self):
        lib = ReactComponentLibrary().synthesize_all()
        self.component = lib['src/components/ContactForm.jsx']

    def test_real_submit_mode_contract(self):
        self.assertIn('onSubmitLead', self.component)
        self.assertIn('async (e)', self.component)
        self.assertIn('await onSubmitLead', self.component)
        self.assertIn("e.preventDefault()", self.component)

    def test_duplicate_submit_protection(self):
        self.assertIn('if (submitting)', self.component)
        self.assertIn('disabled={submitting}', self.component)
        self.assertIn("aria-busy", self.component)

    def test_allowlisted_fields_only(self):
        self.assertIn("{ name: name, email: email, message: message }",
                      self.component)
        for forbidden in ('phone:', 'stage_id', 'partner_id', 'model',
                          'method', 'db_name'):
            self.assertNotIn(forbidden, self.component)

    def test_sanitized_error_surface(self):
        # Deterministic friendly messages keyed on the stable Phase 47.35
        # error codes; raw error objects never rendered.
        self.assertIn('CLIENT_CAPABILITY_UNAVAILABLE', self.component)
        self.assertIn('CLIENT_REQUEST_INVALID', self.component)
        self.assertIn('CLIENT_NETWORK_ERROR', self.component)
        self.assertNotIn('{err}', self.component)
        self.assertNotIn('JSON.stringify(err)', self.component)

    def test_client_side_limits_mirror_server_contract(self):
        self.assertIn('maxLength={200}', self.component)
        self.assertIn('maxLength={4000}', self.component)

    def test_legacy_mode_preserved(self):
        # Without onSubmitLead the original demo behavior remains.
        self.assertIn("setStatus('success')", self.component)
        self.assertIn('if (onSubmit) onSubmit(e)', self.component)
        self.assertIn('isLeadBound', self.component)

    def test_codegen_contactform_section(self):
        engine = CodeGenerationEngine(MagicMock())
        artifact = _artifact('Agency', 'Lead Co', ['Hero', 'ContactCTA'], [],
                             capabilities=['leads'])
        code, imports = engine._pattern_contactform(
            'ContactFormSection2', artifact, 'Contact us', '', None, {}, [],
            1, [])
        self.assertIn('clientApi.createLead', code)
        self.assertIn('onSubmitLead={submitLead}', code)
        self.assertIn('<ContactForm data-nexora-source="native/ContactForm"',
                      code)
        self.assertIn("import ContactForm from '../components/ContactForm.jsx'",
                      imports)
        self.assertIn("import { clientApi } from '../lib/clientApi.js'",
                      imports)
        issues = CodeGenerationEngine._section_module_issues(
            'ContactFormSection2', code,
            known_identifiers={'ContactForm', 'clientApi'})
        self.assertEqual(issues, [])

    def test_codegen_contactform_skipped_without_capability(self):
        # Without the leads capability the section is truthfully skipped
        # (never silently rendered as an API-bound form).
        engine = CodeGenerationEngine(MagicMock())
        artifact = _artifact('Agency', 'Static Co', ['Hero', 'ContactCTA'],
                             [])
        result = engine._pattern_contactform(
            'ContactFormSection2', artifact, 'Contact us', '', None, {}, [],
            1, [])
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 6. ArchitectureEngine contact-page composition (leads capability)
# ---------------------------------------------------------------------------

class TestArchitectureLeadComposition(unittest.TestCase):

    def _run(self, capabilities, hierarchy=('/', '/contact')):
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(
                domain='Agency', business_name='Lead Co',
                capabilities=capabilities,
                backend_required=bool(capabilities)),
            generation_metadata={
                'modular_blueprint': {
                    'layout': {'hierarchy': list(hierarchy),
                               'strategy': 'grid'}},
                'page_pattern': {
                    'id': 'agency',
                    'home_sections': ['Hero', 'ServicesGrid', 'ContactCTA'],
                    'secondary_sections': ['Hero', 'Content'],
                }})
        result = ArchitectureEngine(MagicMock()).execute(artifact, MagicMock())
        self.assertTrue(result.success, result.error)
        return result.artifact.architecture.component_hierarchy

    def test_leads_capability_appends_contactform_on_contact_page(self):
        hierarchy = self._run(['leads'])
        contact = hierarchy['page_contact']
        self.assertEqual(contact['sections'][-1], 'ContactForm')

    def test_no_capability_no_contactform(self):
        hierarchy = self._run([])
        self.assertNotIn('ContactForm', hierarchy['page_contact']['sections'])

    def test_non_contact_pages_unchanged(self):
        hierarchy = self._run(['leads'])
        self.assertNotIn('ContactForm', hierarchy['page_home']['sections'])

    def test_products_only_project_gets_no_contactform(self):
        hierarchy = self._run(['products'])
        self.assertNotIn('ContactForm', hierarchy['page_contact']['sections'])


# ---------------------------------------------------------------------------
# 7. Full codegen capability gating + security scan
# ---------------------------------------------------------------------------

class TestCapabilityGatingAndSecurity(unittest.TestCase):

    def _generate_all(self, capabilities, include_client_api=None,
                      domain='Restaurant'):
        # Restaurant pattern composes MenuHighlights (the ProductGrid
        # section vocabulary); the contact page hosts the lead form.
        sections_contact = ['Hero', 'Content']
        if 'leads' in (capabilities or []):
            sections_contact = sections_contact + ['ContactForm']
        artifact = _artifact(domain, 'Bound Co',
                             ['Hero', 'MenuHighlights', 'ContactCTA'],
                             _menu_content_pages(),
                             capabilities=capabilities)
        artifact = artifact.evolve(architecture=ArchitectureModel(
            component_hierarchy={
                'home': {'type': 'page', 'path': '/',
                         'sections': ['Hero', 'MenuHighlights',
                                      'ContactCTA']},
                'contact': {'type': 'page', 'path': '/contact',
                            'sections': sections_contact},
            }))
        if include_client_api is None:
            include_client_api = bool(capabilities)
        result, workspace = _run_codegen(
            artifact, include_client_api=include_client_api)
        self.assertTrue(result.success, result.error)
        return workspace

    def test_leads_bound_contact_page(self):
        workspace = self._generate_all(['leads'])
        contact = workspace.read_file('src/pages/contact.tsx')
        self.assertIn('clientApi.createLead', contact)
        self.assertIn("import { clientApi } from '../lib/clientApi.js'",
                      contact)
        self.assertIn('ContactForm data-nexora-source="native/ContactForm"',
                      contact)

    def test_static_project_has_no_api_surface(self):
        workspace = self._generate_all([])
        for path in ('src/pages/index.tsx', 'src/pages/contact.tsx',
                     'src/App.jsx'):
            code = workspace.read_file(path)
            self.assertNotIn('clientApi', code, path)
            self.assertNotIn('useClientProducts', code, path)
            self.assertNotIn('onSubmitLead', code, path)

    def test_no_credentials_or_selectors_in_generated_output(self):
        for capabilities in ([], ['products'], ['leads'],
                             ['products', 'leads']):
            workspace = self._generate_all(capabilities)
            for path, code in workspace.files.items():
                if isinstance(code, bytes):
                    continue
                lowered = str(path).lower()
                self.assertNotIn('nex_cli_', code, path)
                self.assertNotIn('ODOO_PASSWORD', code, path)
                self.assertNotIn('ODOO_USERNAME', code, path)
                self.assertNotIn('fernet', lowered, path)
                # no hardcoded backend hosts in browser-delivered files
                if str(path).endswith(('.jsx', '.js', '.tsx')):
                    self.assertNotIn('127.0.0.1', code, path)
                    self.assertNotIn('localhost', code, path)
                    self.assertNotIn(':8069', code, path)
                    self.assertNotIn(':8000', code, path)

    def test_no_generic_rpc_surface_in_binding(self):
        workspace = self._generate_all(['products', 'leads'])
        client_api = workspace.read_file('src/lib/clientApi.js')
        for forbidden in ('execute', 'rpc', 'call_kw', 'search_read',
                          'ir.', 'res.', 'product.product', 'crm.lead',
                          'db_name', 'environment_id'):
            self.assertNotIn(forbidden, client_api)

    def test_fresh_generation_determinism(self):
        # Two independent fresh generations produce identical binding
        # output (source-of-truth proof). The products binding lives on
        # the MenuHighlights/ProductGrid section; the leads binding on
        # the contact-page ContactForm.
        runs = []
        for _ in range(2):
            workspace = self._generate_all(['products', 'leads'])
            runs.append({
                'index': workspace.read_file('src/pages/index.tsx'),
                'contact': workspace.read_file('src/pages/contact.tsx'),
                'clientApi': workspace.read_file('src/lib/clientApi.js'),
            })
        self.assertEqual(runs[0]['index'], runs[1]['index'])
        self.assertEqual(runs[0]['contact'], runs[1]['contact'])
        self.assertEqual(runs[0]['clientApi'], runs[1]['clientApi'])
        self.assertIn('useClientProducts', runs[0]['index'])
        self.assertIn('clientApi.createLead', runs[0]['contact'])


if __name__ == '__main__':
    unittest.main()
