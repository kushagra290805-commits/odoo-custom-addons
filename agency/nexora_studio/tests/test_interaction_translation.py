# -*- coding: utf-8 -*-
"""
Test Suite for Interaction Translation & React Provider Integration (Phase 12D Task 6).
Verifies isolated translation of provider-neutral BehaviorDefinitions, StateMachines,
and EventBus into framework-specific React hooks, event handler snippets, and ARIA attributes.
"""
import unittest
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
try:
    import odoo
    import odoo.addons
    odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from odoo.addons.nexora_studio.services.design.interaction_model import (
        InteractionModel, BehaviorDefinition, InteractionAction, NavigationAction,
        StateMachineDefinition, StateTransition, AccessibilityPolicy, FocusPolicy
    )
    from odoo.addons.nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
    from odoo.addons.nexora_studio.services.design.react_component_library import ReactComponentLibrary
    from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from nexora_studio.services.design.interaction_model import (
        InteractionModel, BehaviorDefinition, InteractionAction, NavigationAction,
        StateMachineDefinition, StateTransition, AccessibilityPolicy, FocusPolicy
    )
    from nexora_studio.services.design.providers.react_provider import ReactRenderingProvider
    from nexora_studio.services.design.react_component_library import ReactComponentLibrary
    from nexora_studio.services.design.component_manifest import ComponentManifest


class TestInteractionTranslation(unittest.TestCase):

    def setUp(self):
        self.provider = ReactRenderingProvider()
        self.sm = StateMachineDefinition(
            machine_id="modal_sm",
            initial_state="closed",
            states=["closed", "open"],
            transitions=[StateTransition("closed", "OpenModal", "open")]
        )
        self.behavior = BehaviorDefinition(
            component_id="mod-1",
            component_type="Modal",
            trigger_event="ModalOpened",
            actions=[
                InteractionAction("show_modal", target_state="isOpen"),
                InteractionAction("navigate", navigation=NavigationAction(target="#success")),
                InteractionAction("validate"),
                InteractionAction("submit_form"),
                InteractionAction("show_toast"),
                InteractionAction("update_state", target_state="activeTab")
            ],
            state_machine_ref="modal_sm",
            accessibility_attributes={"role": "dialog", "aria_modal": "true", "focus_trap": "true"}
        )

    def test_translate_interaction_behavior_hooks(self):
        """Verify state machine definitions translate into React useState hooks."""
        res = self.provider.translate_interaction_behavior(self.behavior, self.sm)
        self.assertIn("const [modal_sm, set_modal_sm] = useState('closed');", res["hooks"])

    def test_translate_interaction_behavior_handlers(self):
        """Verify abstract actions translate into React event handlers without leaking into domain model."""
        res = self.provider.translate_interaction_behavior(self.behavior, self.sm)
        handlers = res["handlers"]
        self.assertIn("const handleModalToggle = () => { setIsModalOpen((prev) => !prev); };", handlers)
        self.assertIn("const handleNavigate = () => { window.location.href = '#success'; };", handlers)
        self.assertIn("const handleValidate = (data) => { /* Execute validation rules */ return true; };", handlers)
        self.assertIn("const handleSubmitForm = (e) => { e.preventDefault(); /* Process form submission */ };", handlers)
        self.assertIn("const handleShowToast = (msg, type) => { /* Trigger notification toast */ };", handlers)
        self.assertIn("const handleUpdate_activeTab = (val) => { /* Update state activeTab */ };", handlers)

    def test_translate_interaction_behavior_aria(self):
        """Verify WAI-ARIA attributes are preserved in translation output."""
        res = self.provider.translate_interaction_behavior(self.behavior, self.sm)
        aria = res["aria"]
        self.assertEqual(aria.get("role"), "dialog")
        self.assertEqual(aria.get("aria_modal"), "true")
        self.assertEqual(aria.get("focus_trap"), "true")

    def test_react_component_library_interaction_integration(self):
        """Verify ReactComponentLibrary synthesizes accessible interactive components when given InteractionModel."""
        model = InteractionModel(project_id="test-proj")
        manifest = ComponentManifest()
        lib = ReactComponentLibrary(manifest, interaction_model=model)
        files = lib.synthesize_all()

        # Check Modal accessibility integration
        modal_jsx = files.get("src/components/Modal.jsx", "")
        self.assertIn("role=\"dialog\"", modal_jsx)
        self.assertIn("aria-modal=\"true\"", modal_jsx)
        self.assertIn("modalRef", modal_jsx)
        self.assertIn("e.key === 'Escape'", modal_jsx)
        self.assertIn("previousFocusRef.current.focus()", modal_jsx)

        # Check Accordion accessibility integration
        acc_jsx = files.get("src/components/Accordion.jsx", "")
        self.assertIn("role=\"region\"", acc_jsx)
        self.assertIn("aria-expanded=", acc_jsx)
        self.assertIn("e.key === 'Enter' || e.key === ' '", acc_jsx)

        # Check Tabs accessibility integration
        tabs_jsx = files.get("src/components/Tabs.jsx", "")
        self.assertIn("role=\"tablist\"", tabs_jsx)
        self.assertIn("role=\"tab\"", tabs_jsx)
        self.assertIn("role=\"tabpanel\"", tabs_jsx)
        self.assertIn("e.key === 'ArrowRight'", tabs_jsx)
        self.assertIn("e.key === 'ArrowLeft'", tabs_jsx)


if __name__ == "__main__":
    unittest.main()
