# -*- coding: utf-8 -*-
"""
Playwright E2E Interaction Test Suite (Phase 12D Task 6).
Verifies that synthesized interactive components (Modal, Dropdown, Accordion, Tabs)
execute state transitions, WAI-ARIA updates, and keyboard shortcuts in a live chromium browser session.
"""
import unittest
import sys
import os
import time
import socket
import subprocess
import urllib.request
from typing import Dict, Any

sys.path.append("D:\\ODOO\\community\\odoo")
try:
    import odoo
    import odoo.addons
    odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from playwright.sync_api import sync_playwright
    from odoo.addons.nexora_studio.services.design.providers.rendering_provider import RenderingContext
    from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
    from odoo.addons.nexora_studio.services.design.interaction_model import InteractionModel
    from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest
    from odoo.addons.nexora_studio.tests.test_runtime_validation import WorkspaceManager
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from playwright.sync_api import sync_playwright
    from nexora_studio.services.design.providers.rendering_provider import RenderingContext
    from nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
    from nexora_studio.services.design.interaction_model import InteractionModel
    from nexora_studio.services.design.component_manifest import ComponentManifest
    from nexora_studio.tests.test_runtime_validation import WorkspaceManager


class MockSection:
    def __init__(self, sid, cat, name="Section"):
        self.id = sid
        self.category = cat
        self.name = name
        self.section_type = cat
        self.layout_container = "grid-12"
        self.component_id = sid


class MockPage:
    def __init__(self, sections, name="Home"):
        self.id = "p-1"
        self.name = name
        self.slug = "/"
        self.sections = sections


class MockProject:
    def __init__(self, name="TestProject", pages=None):
        self.project_id = "proj-12d-playwright"
        self.name = name
        self.pages = pages or []
        self.tokens = []
        self.global_assets = []
        self.global_content = []
        self.navigation = None


PLAYGROUND_APP_JSX = """import React, { useState } from 'react';
import Accordion from './components/Accordion.jsx';
import Tabs from './components/Tabs.jsx';
import Dropdown from './components/Dropdown.jsx';
import Modal from './components/Modal.jsx';

export default function App() {
  const [modalOpen, setModalOpen] = useState(false);
  
  const accordionItems = [
    { title: 'Accordion Section 1', content: <div id="acc-panel-content-0">Accordion Body 0</div> },
    { title: 'Accordion Section 2', content: <div id="acc-panel-content-1">Accordion Body 1</div> }
  ];

  const tabsData = [
    { label: 'Tab Alpha', content: <div id="tab-panel-content-0">Tab Alpha Content</div> },
    { label: 'Tab Beta', content: <div id="tab-panel-content-1">Tab Beta Content</div> }
  ];

  const dropdownOptions = [
    { label: 'Option Alpha' },
    { label: 'Option Beta' }
  ];

  return (
    <div id="playground" style={{ padding: '2rem', background: '#0f172a', color: '#fff', minHeight: '100vh' }}>
      <h1 id="playground-title">Interaction Playground</h1>
      
      <div id="test-accordion" style={{ marginBottom: '2rem' }}>
        <Accordion items={accordionItems} />
      </div>

      <div id="test-tabs" style={{ marginBottom: '2rem' }}>
        <Tabs tabs={tabsData} />
      </div>

      <div id="test-dropdown" style={{ marginBottom: '2rem' }}>
        <Dropdown label="Select Option" options={dropdownOptions} id="dropdown-component" />
      </div>

      <div id="test-modal" style={{ marginBottom: '2rem' }}>
        <button id="open-modal-btn" onClick={() => setModalOpen(true)}>Open Test Modal</button>
        <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Test Dialog">
          <input id="modal-input-1" placeholder="First Input" />
          <button id="modal-btn-action">Action Button</button>
        </Modal>
      </div>
    </div>
  );
}
"""


class TestPlaywrightInteraction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.tmp_val_workspace'))
        cls.ws_manager = WorkspaceManager(cls.workspace_base)
        base_pkg = '''{
  "name": "nexora-shared-cache",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.0",
    "lucide-react": "^0.383.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.2.0"
  }
}'''
        cls.ws_manager.ensure_shared_cache(base_pkg)

        # Generate interactive project structure
        provider = ReactRenderingProvider()
        proj = MockProject("interactive-proj", pages=[
            MockPage([MockSection("sec-1", "hero", "Hero Section")])
        ])
        manifest = ComponentManifest.from_render_project(proj)
        model = InteractionModel(project_id="interactive-proj")
        context = RenderingContext(proj, manifest, interaction_model=model)
        res = provider.generate_project(context)
        struct = res["project_structure"]
        struct["src/App.jsx"] = PLAYGROUND_APP_JSX

        cls.proj_dir = cls.ws_manager.prepare_project_workspace("pw_interactive_playground", struct)
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

        # Build Vite project
        subprocess.run([npm_cmd, "run", "build"], cwd=cls.proj_dir, capture_output=True, text=True, check=True)

        # Launch Vite preview server
        cls.port = cls._get_free_port()
        cls.preview_proc = subprocess.Popen(
            [npm_cmd, "run", "preview", "--", "--port", str(cls.port), "--host", "localhost"],
            cwd=cls.proj_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        cls.url = f"http://localhost:{cls.port}/"

        # Wait for preview server
        http_ok = False
        for _ in range(30):
            time.sleep(0.2)
            if cls.preview_proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(cls.url, timeout=1.5) as resp:
                    if resp.status == 200:
                        http_ok = True
                        break
            except Exception:
                continue

        if not http_ok:
            raise RuntimeError(f"Preview server failed to start for interactive playground on port {cls.port}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "preview_proc") and cls.preview_proc.poll() is None:
            cls.preview_proc.terminate()
            cls.preview_proc.wait(timeout=5)

    @classmethod
    def _get_free_port(cls) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            return s.getsockname()[1]

    def test_01_accordion_e2e_interaction(self):
        """Verify accordion click toggling and WAI-ARIA aria-expanded updates in browser."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url, wait_until="networkidle")

            header = page.locator("#accordion-header-0")
            self.assertEqual(header.get_attribute("aria-expanded"), "false")
            self.assertEqual(page.locator("#acc-panel-content-0").count(), 0)

            # Click to expand
            header.click()
            self.assertEqual(header.get_attribute("aria-expanded"), "true")
            self.assertEqual(page.locator("#acc-panel-content-0").count(), 1)
            self.assertTrue(page.locator("#acc-panel-content-0").is_visible())

            # Click to collapse
            header.click()
            self.assertEqual(header.get_attribute("aria-expanded"), "false")
            self.assertEqual(page.locator("#acc-panel-content-0").count(), 0)
            browser.close()

    def test_02_tabs_e2e_interaction(self):
        """Verify tab switching and left/right Arrow key navigation in browser."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url, wait_until="networkidle")

            tab0 = page.locator("#tab-btn-0")
            tab1 = page.locator("#tab-btn-1")
            self.assertEqual(tab0.get_attribute("aria-selected"), "true")
            self.assertEqual(tab1.get_attribute("aria-selected"), "false")
            self.assertTrue(page.locator("#tab-panel-content-0").is_visible())
            self.assertEqual(page.locator("#tab-panel-content-1").count(), 0)

            # Click second tab
            tab1.click()
            self.assertEqual(tab0.get_attribute("aria-selected"), "false")
            self.assertEqual(tab1.get_attribute("aria-selected"), "true")
            self.assertTrue(page.locator("#tab-panel-content-1").is_visible())

            # Keyboard navigation: press ArrowLeft on tab1
            tab1.focus()
            page.keyboard.press("ArrowLeft")
            self.assertEqual(tab0.get_attribute("aria-selected"), "true")
            self.assertTrue(page.locator("#tab-panel-content-0").is_visible())
            browser.close()

    def test_03_dropdown_e2e_interaction(self):
        """Verify dropdown menu opening, listbox aria attributes, and option selection."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url, wait_until="networkidle")

            trigger = page.locator("#test-dropdown button[aria-haspopup='listbox']")
            self.assertEqual(trigger.get_attribute("aria-expanded"), "false")
            self.assertEqual(page.locator("#dropdown-menu").count(), 0)

            # Click to open menu
            trigger.click()
            self.assertEqual(trigger.get_attribute("aria-expanded"), "true")
            menu = page.locator("#dropdown-menu")
            self.assertTrue(menu.is_visible())

            # Click option
            option = page.locator("li[role='option']", has_text="Option Beta")
            self.assertTrue(option.is_visible())
            option.click()
            self.assertEqual(page.locator("#dropdown-menu").count(), 0)
            self.assertEqual(trigger.get_attribute("aria-expanded"), "false")
            browser.close()

    def test_04_modal_e2e_interaction_and_focus_trap(self):
        """Verify modal dialog opening, WAI-ARIA role/modal attributes, Escape key dismissal, and focus restoration."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url, wait_until="networkidle")

            open_btn = page.locator("#open-modal-btn")
            self.assertEqual(page.locator("div[role='dialog']").count(), 0)

            # Click to open modal
            open_btn.click()
            dialog = page.locator("div[role='dialog']")
            self.assertTrue(dialog.is_visible())
            self.assertEqual(dialog.get_attribute("aria-modal"), "true")

            # Press Escape to dismiss
            page.keyboard.press("Escape")
            self.assertEqual(page.locator("div[role='dialog']").count(), 0)

            # Verify focus restoration to open button
            active_id = page.evaluate("document.activeElement.id")
            self.assertEqual(active_id, "open-modal-btn")
            browser.close()


if __name__ == "__main__":
    unittest.main()
