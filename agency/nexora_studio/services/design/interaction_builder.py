# -*- coding: utf-8 -*-
"""
Interaction Builder — Phase 12D Task 2.

Synthesizes a provider-neutral InteractionModel from a RenderProject and ComponentManifest.
Infers declarative interaction definitions, abstract behavior definitions, event bindings, state machines,
and policy objects for 17 target component categories:
    Buttons, Forms, Navigation, Navbar, Sidebar, Accordion, FAQ, Tabs, Dropdown, Modal, Pagination,
    Authentication Forms, Contact Forms, Tables, Product Cards, Blog Cards, Hero CTA.

Strict Architectural Governance (ADR-0035 through ADR-0040):
- Complete provider-neutrality: No React, JSX, DOM, Flutter, Angular, Vue, or HTML concepts.
- Strict separation between Interaction Definitions (triggers/events) and Behavior Definitions (actions/states/policies).
"""
from typing import Any, Dict, List, Optional
from .interaction_model import (
    InteractionModel, InteractionDefinition, BehaviorDefinition,
    InteractionTrigger, InteractionAction, InteractionState, ValidationRule,
    NavigationAction, InteractionEvent, StateTransition, StateMachineDefinition,
    ValidationPolicy, NavigationPolicy, AccessibilityPolicy, AnimationPolicy, FocusPolicy, ToastPolicy
)


class InteractionBuilder:
    """
    Builder engine responsible for synthesizing an InteractionModel from a project and manifest.
    """

    @classmethod
    def build(cls, render_project: Any, manifest: Any) -> InteractionModel:
        project_id = getattr(render_project, "project_id", "") or getattr(render_project, "name", "project")
        model = InteractionModel(project_id=str(project_id), policies=InteractionModel.create_default_policies())

        # 1. Register Canonical Event Bus Schema
        cls._register_canonical_events(model)

        # 2. Register Canonical State Machines (Improvement 1)
        cls._register_canonical_state_machines(model)

        # 3. Register Global States
        cls._register_global_states(model)

        # 4. Infer interactions and behaviors across all 17 component categories
        cls._infer_for_manifest_entries(model, manifest)
        cls._infer_for_project_sections(model, render_project)

        return model

    @classmethod
    def _register_canonical_events(cls, model: InteractionModel) -> None:
        events = [
            ("ButtonClicked", {"button_id": "string", "target": "string"}, "Button", "Emitted when a button is clicked."),
            ("ModalOpened", {"modal_id": "string"}, "Modal", "Emitted when a modal dialog transitions to open state."),
            ("ModalClosed", {"modal_id": "string"}, "Modal", "Emitted when a modal dialog transitions to closed state."),
            ("ValidationFailed", {"errors": "object"}, "Form", "Emitted when form field validation fails."),
            ("FormSubmitted", {"form_id": "string", "payload": "object"}, "Form", "Emitted upon successful form submission."),
            ("RouteChanged", {"target_path": "string"}, "Navigation", "Emitted when navigation occurs."),
            ("TabChanged", {"tab_index": "number", "tab_id": "string"}, "Tabs", "Emitted when active tab selection changes."),
            ("AccordionToggled", {"item_index": "number", "expanded": "boolean"}, "Accordion", "Emitted when accordion item toggles."),
            ("DropdownOpened", {"dropdown_id": "string"}, "Dropdown", "Emitted when dropdown menu opens."),
            ("DropdownClosed", {"dropdown_id": "string"}, "Dropdown", "Emitted when dropdown menu closes."),
            ("ToastShown", {"message": "string", "type": "string"}, "Toast", "Emitted when notification toast displays."),
            ("ToastHidden", {"toast_id": "string"}, "Toast", "Emitted when notification toast dismisses."),
            ("PageChanged", {"page_number": "number"}, "Pagination", "Emitted when active pagination page changes."),
            ("SortChanged", {"column": "string", "direction": "string"}, "Table", "Emitted when table sorting changes."),
            ("RowSelected", {"row_id": "string", "selected": "boolean"}, "Table", "Emitted when table row selection toggles."),
            ("CardClicked", {"card_id": "string", "target": "string"}, "Card", "Emitted when a product or blog card is clicked."),
            ("HeroCtaClicked", {"cta_id": "string", "target": "string"}, "Hero", "Emitted when a Hero Call-To-Action button is clicked."),
        ]
        for name, schema, src, desc in events:
            model.register_event(InteractionEvent(event_name=name, payload_schema=schema, source_component_type=src, description=desc))

    @classmethod
    def _register_canonical_state_machines(cls, model: InteractionModel) -> None:
        # Modal State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="modal_sm",
            initial_state="closed",
            states=["closed", "open"],
            transitions=[
                StateTransition("closed", "OpenModal", "open", action_to_execute="show_modal"),
                StateTransition("open", "CloseModal", "closed", action_to_execute="hide_modal"),
                StateTransition("open", "EscapePressed", "closed", action_to_execute="hide_modal"),
            ]
        ))
        # Dropdown State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="dropdown_sm",
            initial_state="closed",
            states=["closed", "open"],
            transitions=[
                StateTransition("closed", "ToggleDropdown", "open", action_to_execute="open_dropdown"),
                StateTransition("open", "ToggleDropdown", "closed", action_to_execute="close_dropdown"),
                StateTransition("open", "EscapePressed", "closed", action_to_execute="close_dropdown"),
                StateTransition("open", "OptionSelected", "closed", action_to_execute="close_dropdown"),
            ]
        ))
        # Accordion State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="accordion_sm",
            initial_state="collapsed",
            states=["collapsed", "expanded"],
            transitions=[
                StateTransition("collapsed", "ToggleAccordion", "expanded", action_to_execute="update_state"),
                StateTransition("expanded", "ToggleAccordion", "collapsed", action_to_execute="update_state"),
            ]
        ))
        # Tabs State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="tabs_sm",
            initial_state="tab_0",
            states=["tab_0", "tab_1", "tab_2"],
            transitions=[
                StateTransition("tab_0", "SelectTab", "tab_N", action_to_execute="update_state"),
            ]
        ))
        # Pagination State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="pagination_sm",
            initial_state="page_1",
            states=["page_1", "page_N"],
            transitions=[
                StateTransition("page_1", "NextPage", "page_N", action_to_execute="update_state"),
                StateTransition("page_N", "PrevPage", "page_1", action_to_execute="update_state"),
            ]
        ))
        # Forms State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="forms_sm",
            initial_state="pristine",
            states=["pristine", "dirty", "submitting", "submitted", "invalid"],
            transitions=[
                StateTransition("pristine", "Change", "dirty", action_to_execute="update_state"),
                StateTransition("dirty", "Submit", "submitting", guard_condition="is_valid", action_to_execute="submit_form"),
                StateTransition("dirty", "Submit", "invalid", guard_condition="not_valid", action_to_execute="validate"),
                StateTransition("submitting", "Success", "submitted", action_to_execute="show_toast"),
                StateTransition("submitting", "Error", "dirty", action_to_execute="show_toast"),
            ]
        ))
        # Navigation State Machine
        model.add_state_machine(StateMachineDefinition(
            machine_id="navigation_sm",
            initial_state="idle",
            states=["idle", "navigating"],
            transitions=[
                StateTransition("idle", "Navigate", "navigating", action_to_execute="navigate"),
                StateTransition("navigating", "RouteLoaded", "idle"),
            ]
        ))

    @classmethod
    def _register_global_states(cls, model: InteractionModel) -> None:
        model.global_states.append(InteractionState("isMobileMenuOpen", False, "boolean", "global"))
        model.global_states.append(InteractionState("activeModalId", "", "string", "global"))
        model.global_states.append(InteractionState("toastNotifications", [], "array", "global"))

    @classmethod
    def _infer_for_manifest_entries(cls, model: InteractionModel, manifest: Any) -> None:
        entries = getattr(manifest, "entries", {})
        if isinstance(entries, dict):
            items = entries.values()
        elif isinstance(entries, list):
            items = entries
        else:
            items = []

        for entry in items:
            ctype = getattr(entry, "component_type", "") or getattr(entry, "name", "")
            cid = getattr(entry, "id", ctype)
            cls._infer_component_category(model, cid, ctype)

        # Guarantee canonical entries exist for all 17 target categories even if manifest omitted them
        canonical_targets = [
            ("Button", "Button"), ("Form", "Form"), ("Navigation", "Navigation"),
            ("Navbar", "Navbar"), ("Sidebar", "Sidebar"), ("Accordion", "Accordion"),
            ("FAQ", "FAQ"), ("Tabs", "Tabs"), ("Dropdown", "Dropdown"),
            ("Modal", "Modal"), ("Pagination", "Pagination"), ("AuthForm", "AuthForm"),
            ("ContactForm", "ContactForm"), ("Table", "Table"), ("ProductCard", "ProductCard"),
            ("BlogCard", "BlogCard"), ("Hero", "Hero")
        ]
        existing_types = {getattr(e, "component_type", "") for e in items}
        for cid, ctype in canonical_targets:
            if ctype not in existing_types:
                cls._infer_component_category(model, cid, ctype)

    @classmethod
    def _infer_for_project_sections(cls, model: InteractionModel, render_project: Any) -> None:
        for p in getattr(render_project, "pages", []):
            for s in getattr(p, "sections", []):
                sid = getattr(s, "id", "") or getattr(s, "name", "")
                cat = getattr(s, "category", "")
                cls._infer_component_category(model, sid, cat.capitalize())

    @classmethod
    def _infer_component_category(cls, model: InteractionModel, cid: str, ctype: str) -> None:
        lower_type = ctype.lower()

        # 1. Buttons & Hero CTA
        if "button" in lower_type or "cta" in lower_type or "hero" in lower_type:
            evt = "HeroCtaClicked" if "hero" in lower_type or "cta" in lower_type else "ButtonClicked"
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="trigger",
                triggers=[
                    InteractionTrigger("click"),
                    InteractionTrigger("keyboard", key="Enter"),
                    InteractionTrigger("keyboard", key="Space"),
                ],
                emitted_event=evt,
                description=f"Trigger interaction for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event=evt,
                actions=[InteractionAction("navigate", navigation=NavigationAction(target="#pricing"))],
                state_machine_ref="navigation_sm",
                policies={"navigation": NavigationPolicy().to_dict(), "animation": AnimationPolicy().to_dict()},
                accessibility_attributes={"role": "button", "keyboard_activation": "Enter, Space"}
            ))

        # 2. Forms, AuthForm, ContactForm
        elif "form" in lower_type or "auth" in lower_type or "contact" in lower_type:
            rules = [ValidationRule("email", "email", error_message="Valid email required")]
            if "auth" in lower_type:
                rules.append(ValidationRule("password", "min_length", parameter=8, error_message="Minimum 8 chars required"))
            elif "contact" in lower_type:
                rules.append(ValidationRule("message", "required", error_message="Message cannot be empty"))

            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="container",
                triggers=[InteractionTrigger("submit"), InteractionTrigger("keyboard", key="Enter")],
                emitted_event="FormSubmitted",
                description=f"Submission trigger for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="FormSubmitted",
                actions=[
                    InteractionAction("validate", validation_rules=rules),
                    InteractionAction("submit_form", target_state="formData"),
                    InteractionAction("show_toast", payload={"message": "Submission successful", "type": "success"})
                ],
                state_machine_ref="forms_sm",
                policies={"validation": ValidationPolicy().to_dict(), "toast": ToastPolicy().to_dict()},
                accessibility_attributes={"role": "form", "aria_live": "polite"}
            ))

        # 3. Navigation, Navbar, Sidebar
        elif "nav" in lower_type or "navbar" in lower_type or "sidebar" in lower_type or "menu" in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="navigation_container",
                triggers=[InteractionTrigger("click"), InteractionTrigger("toggle"), InteractionTrigger("keyboard", key="Escape")],
                emitted_event="RouteChanged",
                description=f"Navigation interaction for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="RouteChanged",
                actions=[InteractionAction("navigate"), InteractionAction("update_state", target_state="isMobileMenuOpen", payload=False)],
                state_machine_ref="navigation_sm",
                policies={"navigation": NavigationPolicy().to_dict(), "accessibility": AccessibilityPolicy().to_dict()},
                accessibility_attributes={"role": "navigation", "aria_expanded": "isMobileMenuOpen", "escape_action": "close_menu"}
            ))

        # 4. Accordion, FAQ
        elif "accordion" in lower_type or "faq" in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="accordion_item",
                triggers=[InteractionTrigger("click"), InteractionTrigger("toggle"), InteractionTrigger("keyboard", key="Enter"), InteractionTrigger("keyboard", key="Space")],
                emitted_event="AccordionToggled",
                description=f"Toggle interaction for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="AccordionToggled",
                actions=[InteractionAction("toggle", target_state="isExpanded")],
                state_machine_ref="accordion_sm",
                policies={"animation": AnimationPolicy().to_dict(), "accessibility": AccessibilityPolicy().to_dict()},
                accessibility_attributes={"role": "region", "aria_expanded": "isExpanded", "aria_controls": "content_panel"}
            ))

        # 5. Tabs
        elif "tab" in lower_type and "table" not in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="tab_header",
                triggers=[InteractionTrigger("click"), InteractionTrigger("keyboard", key="ArrowRight"), InteractionTrigger("keyboard", key="ArrowLeft")],
                emitted_event="TabChanged",
                description=f"Tab selection for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="TabChanged",
                actions=[InteractionAction("update_state", target_state="activeTab")],
                state_machine_ref="tabs_sm",
                policies={"focus": FocusPolicy().to_dict(), "accessibility": AccessibilityPolicy().to_dict()},
                accessibility_attributes={"role": "tablist", "item_role": "tab", "panel_role": "tabpanel", "aria_selected": "activeTab"}
            ))

        # 6. Dropdown
        elif "dropdown" in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="dropdown_trigger",
                triggers=[InteractionTrigger("click"), InteractionTrigger("toggle"), InteractionTrigger("keyboard", key="Escape"), InteractionTrigger("keyboard", key="ArrowDown")],
                emitted_event="DropdownOpened",
                description=f"Dropdown interaction for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="DropdownOpened",
                actions=[InteractionAction("open_dropdown", target_state="isOpen")],
                state_machine_ref="dropdown_sm",
                policies={"focus": FocusPolicy().to_dict(), "accessibility": AccessibilityPolicy().to_dict()},
                accessibility_attributes={"aria_expanded": "isOpen", "aria_haspopup": "menu", "escape_action": "close_dropdown"}
            ))

        # 7. Modal
        elif "modal" in lower_type or "dialog" in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="dialog_container",
                triggers=[InteractionTrigger("open"), InteractionTrigger("close"), InteractionTrigger("keyboard", key="Escape")],
                emitted_event="ModalOpened",
                description=f"Modal interaction for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="ModalOpened",
                actions=[InteractionAction("show_modal", target_state="isOpen"), InteractionAction("hide_modal", target_state="isOpen")],
                state_machine_ref="modal_sm",
                policies={"accessibility": AccessibilityPolicy().to_dict(), "focus": FocusPolicy(trap_focus_when_modal=True).to_dict()},
                accessibility_attributes={"role": "dialog", "aria_modal": "true", "focus_trap": "true", "restore_focus": "true", "escape_action": "hide_modal"}
            ))

        # 8. Pagination
        elif "pagination" in lower_type or "page" in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="pagination_control",
                triggers=[InteractionTrigger("click"), InteractionTrigger("keyboard", key="ArrowRight"), InteractionTrigger("keyboard", key="ArrowLeft")],
                emitted_event="PageChanged",
                description=f"Page navigation for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="PageChanged",
                actions=[InteractionAction("update_state", target_state="currentPage")],
                state_machine_ref="pagination_sm",
                policies={"navigation": NavigationPolicy(scroll_to_top=True).to_dict()},
                accessibility_attributes={"role": "navigation", "aria_label": "Pagination"}
            ))

        # 9. Tables
        elif ("table" in lower_type or "grid" in lower_type) and "feature" not in lower_type and "product" not in lower_type and "blog" not in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="table_header",
                triggers=[InteractionTrigger("click"), InteractionTrigger("keyboard", key="Enter")],

                emitted_event="SortChanged",
                description=f"Sort trigger for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="SortChanged",
                actions=[InteractionAction("update_state", target_state="sortColumn")],
                policies={"accessibility": AccessibilityPolicy().to_dict()},
                accessibility_attributes={"role": "table", "sort_attribute": "sortDirection"}
            ))

        # 10. Product Cards & Blog Cards
        elif "card" in lower_type or "product" in lower_type or "blog" in lower_type:
            model.add_interaction(InteractionDefinition(
                component_id=cid, component_type=ctype, element_role="card_container",
                triggers=[InteractionTrigger("click"), InteractionTrigger("keyboard", key="Enter")],
                emitted_event="CardClicked",
                description=f"Card click interaction for {ctype}"
            ))
            model.add_behavior(BehaviorDefinition(
                component_id=cid, component_type=ctype, trigger_event="CardClicked",
                actions=[InteractionAction("navigate")],
                policies={"navigation": NavigationPolicy().to_dict(), "animation": AnimationPolicy().to_dict()},
                accessibility_attributes={"role": "article", "keyboard_activation": "Enter"}
            ))
