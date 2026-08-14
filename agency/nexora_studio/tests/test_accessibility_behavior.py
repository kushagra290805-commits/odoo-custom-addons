# -*- coding: utf-8 -*-
"""
Test Suite for WAI-ARIA & Accessibility Behaviors (Phase 12D Task 6).
Verifies semantic ARIA roles, keyboard shortcuts (Escape, Enter/Space, Arrow keys),
focus trapping within open modals, and focus restoration upon modal dismissal.
"""
import unittest
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
try:
    import odoo
    import odoo.addons
    odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from odoo.addons.nexora_studio.services.design.react_component_library import ReactComponentLibrary
    from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from nexora_studio.services.design.react_component_library import ReactComponentLibrary
    from nexora_studio.services.design.component_manifest import ComponentManifest


class TestAccessibilityBehavior(unittest.TestCase):

    def setUp(self):
        self.library = ReactComponentLibrary()
        self.files = self.library.synthesize_all()

    def test_modal_wcag_focus_trap(self):
        """Verify modal dialog implements WCAG 2.1 focus trapping via querySelectorAll and Tab/Shift+Tab handling."""
        modal_jsx = self.files["src/components/Modal.jsx"]
        self.assertIn("modalRef.current.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])')", modal_jsx)
        self.assertIn("if (e.key === 'Tab'", modal_jsx)
        self.assertIn("if (e.shiftKey)", modal_jsx)
        self.assertIn("last.focus()", modal_jsx)
        self.assertIn("first.focus()", modal_jsx)

    def test_modal_focus_restoration_and_escape(self):
        """Verify modal restores focus to previous document.activeElement on close and handles Escape key."""
        modal_jsx = self.files["src/components/Modal.jsx"]
        self.assertIn("previousFocusRef.current = document.activeElement;", modal_jsx)
        self.assertIn("previousFocusRef.current.focus();", modal_jsx)
        self.assertIn("if (e.key === 'Escape')", modal_jsx)
        self.assertIn("if (onClose) onClose();", modal_jsx)
        self.assertIn("role=\"dialog\"", modal_jsx)
        self.assertIn("aria-modal=\"true\"", modal_jsx)

    def test_accordion_keyboard_and_aria(self):
        """Verify Accordion implements role=region, aria-expanded, and Enter/Space keyboard toggling."""
        acc_jsx = self.files["src/components/Accordion.jsx"]
        self.assertIn("role=\"region\"", acc_jsx)
        self.assertIn("aria-expanded={open ? 'true' : 'false'}", acc_jsx)
        self.assertIn("aria-controls={`accordion-panel-${idx}`}", acc_jsx)
        self.assertIn("if (e.key === 'Enter' || e.key === ' ')", acc_jsx)
        self.assertIn("handleToggle(idx);", acc_jsx)
        self.assertIn("e.key === 'ArrowDown'", acc_jsx)
        self.assertIn("e.key === 'ArrowUp'", acc_jsx)

    def test_tabs_arrow_navigation_and_aria(self):
        """Verify Tabs implements tablist/tab/tabpanel roles and left/right arrow navigation."""
        tabs_jsx = self.files["src/components/Tabs.jsx"]
        self.assertIn("role=\"tablist\"", tabs_jsx)
        self.assertIn("role=\"tab\"", tabs_jsx)
        self.assertIn("role=\"tabpanel\"", tabs_jsx)
        self.assertIn("aria-selected={isSelected ? 'true' : 'false'}", tabs_jsx)
        self.assertIn("if (e.key === 'ArrowRight')", tabs_jsx)
        self.assertIn("if (e.key === 'ArrowLeft')", tabs_jsx)
        self.assertIn("handleSelect(nextIdx);", tabs_jsx)

    def test_dropdown_escape_and_aria(self):
        """Verify Dropdown implements aria-expanded, aria-haspopup, and Escape dismissal."""
        drop_jsx = self.files["src/components/Dropdown.jsx"]
        self.assertIn("aria-expanded={isOpen ? 'true' : 'false'}", drop_jsx)
        self.assertIn("aria-haspopup=\"listbox\"", drop_jsx)
        self.assertIn("role=\"listbox\"", drop_jsx)
        self.assertIn("role=\"option\"", drop_jsx)
        self.assertIn("if (isOpen && e.key === 'Escape')", drop_jsx)


if __name__ == "__main__":
    unittest.main()
