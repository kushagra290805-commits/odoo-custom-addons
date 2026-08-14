# -*- coding: utf-8 -*-
"""
Interaction & Behavior Domain Models — Phase 12D.

This module introduces a provider-neutral Interaction & Behavior modeling layer that sits between
the Component Manifest and downstream rendering synthesizers:
    Render Model -> Component Manifest -> Interaction Model -> Rendering Context -> Rendering Provider

Strict Architectural Governance (ADR-0035 through ADR-0040):
1. Complete Provider-Neutrality: No React, JSX, DOM, Flutter, Angular, Vue, or HTML concepts may appear inside these models.
2. State Machines: Models modal, dropdown, accordion, tabs, pagination, forms, and navigation as explicit state transitions.
3. Event Bus: Interactions emit abstract events (e.g., ButtonClicked, ModalOpened, ValidationFailed, RouteChanged).
4. Separation of Concerns: Separates declarative Interaction Definitions from abstract Behavior Definitions.
5. Interaction Policies: Encapsulates provider-neutral policy objects (ValidationPolicy, NavigationPolicy, AccessibilityPolicy, etc.).
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid


# =========================================================================
# 1. Core Abstract Action & Validation Domain Models
# =========================================================================

@dataclass
class ValidationRule:
    """
    Declarative rule for evaluating field input validity without rendering framework syntax.
    """
    field_name: str
    rule_type: str                      # e.g., 'required', 'email', 'min_length', 'max_length', 'pattern', 'custom'
    parameter: Any = None               # e.g., integer length or regex pattern string
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "rule_type": self.rule_type,
            "parameter": self.parameter,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationRule":
        return cls(
            field_name=data.get("field_name", ""),
            rule_type=data.get("rule_type", "required"),
            parameter=data.get("parameter"),
            error_message=data.get("error_message", ""),
        )


@dataclass
class NavigationAction:
    """
    Abstract navigation instruction specifying destination and routing style.
    """
    target: str                         # e.g., path or anchor URI ('/', '#pricing', '/dashboard')
    navigation_type: str = "link"       # e.g., 'link', 'push', 'replace', 'scroll', 'external'
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "navigation_type": self.navigation_type,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NavigationAction":
        return cls(
            target=data.get("target", "/"),
            navigation_type=data.get("navigation_type", "link"),
            params=data.get("params", {}),
        )


@dataclass
class InteractionState:
    """
    Declarative representation of UI state without framework state hook terminology.
    """
    state_name: str                     # e.g., 'isOpen', 'activeTab', 'isExpanded', 'formData', 'errors'
    initial_value: Any = None
    state_type: str = "boolean"         # e.g., 'boolean', 'string', 'number', 'object', 'array'
    scope: str = "component"            # e.g., 'component', 'page', 'global'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_name": self.state_name,
            "initial_value": self.initial_value,
            "state_type": self.state_type,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionState":
        return cls(
            state_name=data.get("state_name", ""),
            initial_value=data.get("initial_value"),
            state_type=data.get("state_type", "boolean"),
            scope=data.get("scope", "component"),
        )


@dataclass
class InteractionAction:
    """
    Abstract action executed in response to an interaction event or behavior transition.
    Categories: 'navigate', 'update_state', 'show_modal', 'hide_modal', 'validate',
                'submit_form', 'open_dropdown', 'close_dropdown', 'show_toast', 'hide_toast', 'toggle'.
    """
    action_type: str
    target_state: Optional[str] = None  # Name of InteractionState to update
    payload: Any = None                 # State value, form payload, or toast configuration
    navigation: Optional[NavigationAction] = None
    validation_rules: List[ValidationRule] = field(default_factory=list)
    emitted_event: Optional[str] = None # Name of abstract event to trigger upon action completion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_state": self.target_state,
            "payload": self.payload,
            "navigation": self.navigation.to_dict() if self.navigation else None,
            "validation_rules": [r.to_dict() for r in self.validation_rules],
            "emitted_event": self.emitted_event,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionAction":
        nav_data = data.get("navigation")
        return cls(
            action_type=data.get("action_type", ""),
            target_state=data.get("target_state"),
            payload=data.get("payload"),
            navigation=NavigationAction.from_dict(nav_data) if nav_data else None,
            validation_rules=[ValidationRule.from_dict(r) for r in data.get("validation_rules", [])],
            emitted_event=data.get("emitted_event"),
        )


@dataclass
class InteractionTrigger:
    """
    Declarative trigger condition initiating an interaction.
    Categories: 'click', 'submit', 'hover', 'focus', 'blur', 'change', 'keyboard',
                'open', 'close', 'toggle', 'expand', 'collapse'.
    """
    trigger_type: str
    key: Optional[str] = None           # e.g., 'Enter', 'Space', 'Escape', 'ArrowDown', 'Tab'
    modifier_keys: List[str] = field(default_factory=list)  # e.g., ['Shift', 'Ctrl']

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_type": self.trigger_type,
            "key": self.key,
            "modifier_keys": self.modifier_keys,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionTrigger":
        return cls(
            trigger_type=data.get("trigger_type", "click"),
            key=data.get("key"),
            modifier_keys=data.get("modifier_keys", []),
        )


# =========================================================================
# 2. Provider-Neutral Event Bus (Improvement 2)
# =========================================================================

@dataclass
class InteractionEvent:
    """
    Authoritative abstract event emitted by interactions and consumed by behavior definitions.
    """
    event_name: str                     # e.g., 'ButtonClicked', 'ModalOpened', 'ValidationFailed'
    payload_schema: Dict[str, Any] = field(default_factory=dict)
    source_component_type: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_name": self.event_name,
            "payload_schema": self.payload_schema,
            "source_component_type": self.source_component_type,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionEvent":
        return cls(
            event_name=data.get("event_name", ""),
            payload_schema=data.get("payload_schema", {}),
            source_component_type=data.get("source_component_type", ""),
            description=data.get("description", ""),
        )


# =========================================================================
# 3. Provider-Neutral State Machines (Improvement 1)
# =========================================================================

@dataclass
class StateTransition:
    """
    Represents an explicit state transition within a UI component state machine.
    """
    from_state: str
    trigger_event: str
    to_state: str
    guard_condition: Optional[str] = None
    action_to_execute: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_state": self.from_state,
            "trigger_event": self.trigger_event,
            "to_state": self.to_state,
            "guard_condition": self.guard_condition,
            "action_to_execute": self.action_to_execute,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateTransition":
        return cls(
            from_state=data.get("from_state", ""),
            trigger_event=data.get("trigger_event", ""),
            to_state=data.get("to_state", ""),
            guard_condition=data.get("guard_condition"),
            action_to_execute=data.get("action_to_execute"),
        )


@dataclass
class StateMachineDefinition:
    """
    Explicit finite state machine modeling complex UI interactions (modal, dropdown, accordion, tabs, forms, navigation).
    """
    machine_id: str
    initial_state: str
    states: List[str] = field(default_factory=list)
    transitions: List[StateTransition] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "initial_state": self.initial_state,
            "states": self.states,
            "transitions": [t.to_dict() for t in self.transitions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateMachineDefinition":
        return cls(
            machine_id=data.get("machine_id", ""),
            initial_state=data.get("initial_state", ""),
            states=data.get("states", []),
            transitions=[StateTransition.from_dict(t) for t in data.get("transitions", [])],
        )


# =========================================================================
# 4. Interaction Policies (Improvement 4)
# =========================================================================

@dataclass
class ValidationPolicy:
    validate_on: str = "submit"         # 'submit', 'change', 'blur'
    stop_on_first_error: bool = False
    show_inline_errors: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validate_on": self.validate_on,
            "stop_on_first_error": self.stop_on_first_error,
            "show_inline_errors": self.show_inline_errors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationPolicy":
        return cls(
            validate_on=data.get("validate_on", "submit"),
            stop_on_first_error=data.get("stop_on_first_error", False),
            show_inline_errors=data.get("show_inline_errors", True),
        )


@dataclass
class NavigationPolicy:
    default_type: str = "link"          # 'link', 'push', 'replace', 'scroll'
    scroll_to_top: bool = True
    prevent_default: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_type": self.default_type,
            "scroll_to_top": self.scroll_to_top,
            "prevent_default": self.prevent_default,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NavigationPolicy":
        return cls(
            default_type=data.get("default_type", "link"),
            scroll_to_top=data.get("scroll_to_top", True),
            prevent_default=data.get("prevent_default", True),
        )


@dataclass
class AccessibilityPolicy:
    enforce_keyboard_nav: bool = True
    focus_trap_modals: bool = True
    restore_focus: bool = True
    announce_live_regions: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enforce_keyboard_nav": self.enforce_keyboard_nav,
            "focus_trap_modals": self.focus_trap_modals,
            "restore_focus": self.restore_focus,
            "announce_live_regions": self.announce_live_regions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccessibilityPolicy":
        return cls(
            enforce_keyboard_nav=data.get("enforce_keyboard_nav", True),
            focus_trap_modals=data.get("focus_trap_modals", True),
            restore_focus=data.get("restore_focus", True),
            announce_live_regions=data.get("announce_live_regions", True),
        )


@dataclass
class AnimationPolicy:
    enable_transitions: bool = True
    duration_ms: int = 200
    easing: str = "ease"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enable_transitions": self.enable_transitions,
            "duration_ms": self.duration_ms,
            "easing": self.easing,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnimationPolicy":
        return cls(
            enable_transitions=data.get("enable_transitions", True),
            duration_ms=data.get("duration_ms", 200),
            easing=data.get("easing", "ease"),
        )


@dataclass
class FocusPolicy:
    auto_focus_first: bool = True
    focus_ring_style: str = "outline"
    trap_focus_when_modal: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_focus_first": self.auto_focus_first,
            "focus_ring_style": self.focus_ring_style,
            "trap_focus_when_modal": self.trap_focus_when_modal,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FocusPolicy":
        return cls(
            auto_focus_first=data.get("auto_focus_first", True),
            focus_ring_style=data.get("focus_ring_style", "outline"),
            trap_focus_when_modal=data.get("trap_focus_when_modal", True),
        )


@dataclass
class ToastPolicy:
    auto_dismiss_ms: int = 5000
    position: str = "bottom_right"
    stack_limit: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_dismiss_ms": self.auto_dismiss_ms,
            "position": self.position,
            "stack_limit": self.stack_limit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToastPolicy":
        return cls(
            auto_dismiss_ms=data.get("auto_dismiss_ms", 5000),
            position=data.get("position", "bottom_right"),
            stack_limit=data.get("stack_limit", 3),
        )


# =========================================================================
# 5. Separation of Interaction vs Behavior Definitions (Improvement 3)
# =========================================================================

@dataclass
class InteractionDefinition:
    """
    Declarative trigger-to-event binding for a UI component without framework handler translation.
    Emits an abstract event upon trigger activation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    component_id: str = ""
    component_type: str = ""
    element_role: str = ""              # e.g., 'trigger', 'target', 'close_button', 'tab_header'
    triggers: List[InteractionTrigger] = field(default_factory=list)
    emitted_event: str = ""             # e.g., 'ButtonClicked', 'ModalOpened'
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "component_id": self.component_id,
            "component_type": self.component_type,
            "element_role": self.element_role,
            "triggers": [t.to_dict() for t in self.triggers],
            "emitted_event": self.emitted_event,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionDefinition":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            component_id=data.get("component_id", ""),
            component_type=data.get("component_type", ""),
            element_role=data.get("element_role", ""),
            triggers=[InteractionTrigger.from_dict(t) for t in data.get("triggers", [])],
            emitted_event=data.get("emitted_event", ""),
            description=data.get("description", ""),
        )


@dataclass
class BehaviorDefinition:
    """
    Abstract behavior response driven by an interaction event or state machine transition.
    Encapsulates abstract actions, state machine references, policies, and accessibility semantics.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    component_id: str = ""
    component_type: str = ""
    trigger_event: str = ""             # Consumes an event emitted by InteractionDefinition
    actions: List[InteractionAction] = field(default_factory=list)
    state_machine_ref: Optional[str] = None  # Reference to StateMachineDefinition machine_id
    policies: Dict[str, Any] = field(default_factory=dict)
    accessibility_attributes: Dict[str, Any] = field(default_factory=dict)  # e.g., {'aria_expanded': 'isOpen', 'role': 'dialog'}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "component_id": self.component_id,
            "component_type": self.component_type,
            "trigger_event": self.trigger_event,
            "actions": [a.to_dict() for a in self.actions],
            "state_machine_ref": self.state_machine_ref,
            "policies": self.policies,
            "accessibility_attributes": self.accessibility_attributes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BehaviorDefinition":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            component_id=data.get("component_id", ""),
            component_type=data.get("component_type", ""),
            trigger_event=data.get("trigger_event", ""),
            actions=[InteractionAction.from_dict(a) for a in data.get("actions", [])],
            state_machine_ref=data.get("state_machine_ref"),
            policies=data.get("policies", {}),
            accessibility_attributes=data.get("accessibility_attributes", {}),
        )


# =========================================================================
# 6. Authoritative InteractionModel Layer
# =========================================================================

@dataclass
class InteractionModel:
    """
    The provider-neutral Interaction & Behavior domain model.
    Carries all interactions, behaviors, state machines, events, policies, and global states
    for consumption by downstream rendering providers.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    interactions: List[InteractionDefinition] = field(default_factory=list)
    behaviors: List[BehaviorDefinition] = field(default_factory=list)
    state_machines: Dict[str, StateMachineDefinition] = field(default_factory=dict)
    events: Dict[str, InteractionEvent] = field(default_factory=dict)
    policies: Dict[str, Any] = field(default_factory=dict)
    global_states: List[InteractionState] = field(default_factory=list)

    def add_interaction(self, defn: InteractionDefinition) -> None:
        self.interactions.append(defn)

    def add_behavior(self, beh: BehaviorDefinition) -> None:
        self.behaviors.append(beh)

    def add_state_machine(self, sm: StateMachineDefinition) -> None:
        self.state_machines[sm.machine_id] = sm

    def register_event(self, evt: InteractionEvent) -> None:
        self.events[evt.event_name] = evt

    def get_interactions_for_component(self, component_id: str) -> List[InteractionDefinition]:
        return [i for i in self.interactions if i.component_id == component_id or i.component_type == component_id]

    def get_behaviors_for_component(self, component_id: str) -> List[BehaviorDefinition]:
        return [b for b in self.behaviors if b.component_id == component_id or b.component_type == component_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "interactions": [i.to_dict() for i in self.interactions],
            "behaviors": [b.to_dict() for b in self.behaviors],
            "state_machines": {k: v.to_dict() for k, v in self.state_machines.items()},
            "events": {k: v.to_dict() for k, v in self.events.items()},
            "policies": self.policies,
            "global_states": [s.to_dict() for s in self.global_states],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionModel":
        if not data:
            return cls()
        sm_dict = {k: StateMachineDefinition.from_dict(v) for k, v in data.get("state_machines", {}).items()}
        ev_dict = {k: InteractionEvent.from_dict(v) for k, v in data.get("events", {}).items()}
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            project_id=data.get("project_id", ""),
            interactions=[InteractionDefinition.from_dict(i) for i in data.get("interactions", [])],
            behaviors=[BehaviorDefinition.from_dict(b) for b in data.get("behaviors", [])],
            state_machines=sm_dict,
            events=ev_dict,
            policies=data.get("policies", {}),
            global_states=[InteractionState.from_dict(s) for s in data.get("global_states", [])],
        )

    @classmethod
    def create_default_policies(cls) -> Dict[str, Any]:
        """
        Returns a dictionary of canonical default interaction policies.
        """
        return {
            "validation": ValidationPolicy().to_dict(),
            "navigation": NavigationPolicy().to_dict(),
            "accessibility": AccessibilityPolicy().to_dict(),
            "animation": AnimationPolicy().to_dict(),
            "focus": FocusPolicy().to_dict(),
            "toast": ToastPolicy().to_dict(),
        }
