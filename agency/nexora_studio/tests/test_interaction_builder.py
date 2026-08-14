# -*- coding: utf-8 -*-
"""
Test Suite for Interaction Builder & Domain Models (Phase 12D Task 6).
Verifies provider-neutral inference across 17 component categories, state machines, event bus,
policy objects, and 0% rendering framework keyword leakage.
"""
import unittest
import sys
import os
import json

sys.path.append("D:\\ODOO\\community\\odoo")
try:
    import odoo
    import odoo.addons
    odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from odoo.addons.nexora_studio.services.design.interaction_model import (
        InteractionModel, InteractionDefinition, BehaviorDefinition,
        InteractionTrigger, InteractionAction, InteractionState, ValidationRule,
        NavigationAction, InteractionEvent, StateTransition, StateMachineDefinition,
        ValidationPolicy, NavigationPolicy, AccessibilityPolicy, AnimationPolicy, FocusPolicy, ToastPolicy
    )
    from odoo.addons.nexora_studio.services.design.interaction_builder import InteractionBuilder
    from odoo.addons.nexora_studio.services.design.component_manifest import ComponentManifest
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from nexora_studio.services.design.interaction_model import (
        InteractionModel, InteractionDefinition, BehaviorDefinition,
        InteractionTrigger, InteractionAction, InteractionState, ValidationRule,
        NavigationAction, InteractionEvent, StateTransition, StateMachineDefinition,
        ValidationPolicy, NavigationPolicy, AccessibilityPolicy, AnimationPolicy, FocusPolicy, ToastPolicy
    )
    from nexora_studio.services.design.interaction_builder import InteractionBuilder
    from nexora_studio.services.design.component_manifest import ComponentManifest



class MockSection:
    def __init__(self, sid, cat, name="Section"):
        self.id = sid
        self.category = cat
        self.name = name


class MockPage:
    def __init__(self, sections):
        self.sections = sections


class MockProject:
    def __init__(self, name="TestProject", pages=None):
        self.project_id = "proj-12d-test"
        self.name = name
        self.pages = pages or []
        self.tokens = []
        self.global_assets = []


class TestInteractionBuilder(unittest.TestCase):

    def setUp(self):
        sections = [
            MockSection("btn-1", "hero", "Hero CTA Button"),
            MockSection("form-1", "contact", "Contact Form Section"),
            MockSection("nav-1", "navbar", "Main Navigation"),
            MockSection("side-1", "sidebar", "Dashboard Sidebar"),
            MockSection("acc-1", "accordion", "Feature Accordion"),
            MockSection("faq-1", "faq", "FAQ Section"),
            MockSection("tab-1", "tabs", "Exploration Tabs"),
            MockSection("drop-1", "dropdown", "Version Dropdown"),
            MockSection("mod-1", "modal", "Dialog Modal"),
            MockSection("page-1", "pagination", "Table Pagination"),
            MockSection("auth-1", "auth", "User Authentication"),
            MockSection("tbl-1", "table", "User Table Grid"),
            MockSection("prod-1", "product", "Product Card Grid"),
            MockSection("blog-1", "blog", "Blog Card List"),
        ]
        self.project = MockProject(pages=[MockPage(sections)])
        self.manifest = ComponentManifest.from_render_project(self.project)
        self.model = InteractionBuilder.build(self.project, self.manifest)

    def test_canonical_event_bus_registration(self):
        """Verify all 17 canonical event bus schemas are registered."""
        events = self.model.events
        expected_events = [
            "ButtonClicked", "ModalOpened", "ModalClosed", "ValidationFailed",
            "FormSubmitted", "RouteChanged", "TabChanged", "AccordionToggled",
            "DropdownOpened", "DropdownClosed", "ToastShown", "ToastHidden",
            "PageChanged", "SortChanged", "RowSelected", "CardClicked", "HeroCtaClicked"
        ]
        for name in expected_events:
            self.assertIn(name, events)
            self.assertIsInstance(events[name].payload_schema, dict)

    def test_canonical_state_machines(self):
        """Verify explicit state machines for modal, dropdown, accordion, tabs, pagination, forms, navigation."""
        sms = self.model.state_machines
        expected_sms = ["modal_sm", "dropdown_sm", "accordion_sm", "tabs_sm", "pagination_sm", "forms_sm", "navigation_sm"]
        for sm_id in expected_sms:
            self.assertIn(sm_id, sms)
        self.assertEqual(sms["modal_sm"].initial_state, "closed")
        self.assertEqual(sms["forms_sm"].initial_state, "pristine")

    def test_17_component_categories_inference(self):
        """Verify interactions and behaviors are inferred across all 17 target categories."""
        definitions = self.model.interactions
        behaviors = self.model.behaviors
        self.assertGreaterEqual(len(definitions), 17)
        self.assertGreaterEqual(len(behaviors), 17)

        # Check mapping of components to events
        events_emitted = {d.emitted_event for d in definitions}
        self.assertIn("ButtonClicked", events_emitted)
        self.assertIn("FormSubmitted", events_emitted)
        self.assertIn("RouteChanged", events_emitted)
        self.assertIn("AccordionToggled", events_emitted)
        self.assertIn("TabChanged", events_emitted)
        self.assertIn("DropdownOpened", events_emitted)
        self.assertIn("ModalOpened", events_emitted)
        self.assertIn("PageChanged", events_emitted)
        self.assertIn("SortChanged", events_emitted)
        self.assertIn("CardClicked", events_emitted)
        self.assertIn("HeroCtaClicked", events_emitted)

    def test_policies_serialization(self):
        """Verify structured policy objects serialize and deserialize cleanly."""
        policies = self.model.policies
        self.assertIn("validation", policies)
        self.assertIn("navigation", policies)
        self.assertIn("accessibility", policies)
        self.assertIn("animation", policies)
        self.assertIn("focus", policies)
        self.assertIn("toast", policies)

        model_dict = self.model.to_dict()
        model_json = json.dumps(model_dict)
        restored = InteractionModel.from_dict(json.loads(model_json))
        self.assertEqual(restored.project_id, self.model.project_id)
        self.assertEqual(len(restored.events), len(self.model.events))

    def test_zero_framework_keyword_leakage(self):
        """
        Enforce 0% rendering framework keyword leakage.
        No React, JSX, DOM, Flutter, Angular, Vue, or HTML concepts may appear inside domain models.
        """
        forbidden_keywords = [
            "react", "jsx", "dom", "flutter", "angular", "vue",
            "document.", "window.", "useeffect", "usestate", "useref", "innerhtml"
        ]
        model_json = json.dumps(self.model.to_dict()).lower()
        for kw in forbidden_keywords:
            self.assertNotIn(kw, model_json, f"Forbidden framework keyword '{kw}' found in provider-neutral InteractionModel!")


if __name__ == "__main__":
    unittest.main()
