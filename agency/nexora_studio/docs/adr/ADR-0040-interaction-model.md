# ADR-0040: Interaction & Behavior Synthesis Engine

- **Status**: Accepted
- **Date**: 2026-07-26
- **Context**: Nexora Studio Phase 12D
- **Decision-Makers**: AI Engineering, Architecture Review Board

## 1. Executive Summary

In accordance with ADR-0035 (Frozen Planning Layer Contracts) and ADR-0039 (Provider Interface & Multi-Renderer Foundation), Nexora Studio requires an abstracted interaction layer that models user behaviors, state transitions, event emissions, and accessibility policies without coupling to any specific UI rendering framework. 

This ADR formalizes the **Interaction & Behavior Synthesis Engine**, establishing provider-neutral domain models (`InteractionModel`, `StateMachineDefinition`, `InteractionEvent`, `ValidationPolicy`, etc.) that act as the single source of truth for component interactivity. Providers (such as `ReactRenderingProvider`) consume these neutral definitions to synthesize framework-specific hooks (`useState`, `useRef`), event handlers, and WAI-ARIA compliant DOM structures.

---

## 2. Architectural Context & Problem Statement

Prior to Phase 12D, interactivity in generated applications was either hardcoded into framework-specific templates or inferred implicitly during JSX generation. This created three major architectural liabilities:
1. **Framework Leakage**: Interaction rules contained React-specific concepts (`onClick`, `useState`, `useEffect`), making it impossible to reuse the same behavior logic for Flutter, Vue, or Angular providers.
2. **Inconsistent Accessibility**: WAI-ARIA roles, focus trapping, and keyboard shortcuts (Escape dismissal, Enter/Space toggling, Arrow navigation) were applied ad-hoc rather than enforced by a centralized contract.
3. **Unstructured State Flows**: Complex interactive components (modals, dropdowns, tabs, accordions) lacked explicit state machine definitions, leading to unpredictable transition bugs and difficult testability.

---

## 3. Decision & Architectural Architecture

We introduce a dedicated interaction synthesis layer between the **Component Manifest** and the **Rendering Provider**:

```
Requirements Engine
        ↓
Planning Layer (ADR-0035 Frozen)
        ↓
Render Model (RenderProject)
        ↓
Component Manifest (ComponentManifest)
        ↓
Interaction Model (InteractionModel)   <--- [NEW: Provider-Neutral]
        ↓
Rendering Context (RenderingContext)
        ↓
Rendering Provider (e.g., ReactRenderingProvider)
        ↓
Generated UI Project (Vite / React / ARIA)
```

### 3.1 Zero Framework Keyword Leakage Contract
The domain models in `services/design/interaction_model.py` are strictly prohibited from referencing framework-specific keywords or syntax.
- **Forbidden**: `React`, `JSX`, `DOM`, `useState`, `useEffect`, `useRef`, `onClick`, `onChange`, `HTML`, `Flutter`, `Angular`, `Vue`.
- **Enforced Neutrality**: State transitions are represented via generic trigger strings (`"CLICK"`, `"TOGGLE"`, `"KEYDOWN"`, `"HOVER"`) and action identifiers (`"OPEN"`, `"CLOSE"`, `"SELECT"`, `"EXPAND"`).

### 3.2 Provider-Neutral Domain Models
The interaction domain models comprise:
- **`InteractionModel`**: The root aggregate attached to `RenderingContext`, registering component-level interaction definitions, state machines, events, and behaviors.
- **`InteractionDefinition`**: Binds a component ID and category to triggers, actions, and accessibility labels.
- **`BehaviorDefinition`**: Groups validation rules, navigation actions, and UI policies for a specific component.
- **`StateMachineDefinition` & `StateTransition`**: Explicitly defines finite state automata for interactive patterns (e.g., `modal_sm` transitioning between `"CLOSED"` and `"OPEN"` via `"TOGGLE"` or `"DISMISS"` triggers).
- **`InteractionEvent`**: Defines an Event Bus model with canonical event emissions (`ButtonClicked`, `ModalOpened`, `ModalClosed`, `TabSelected`, `AccordionToggled`, `DropdownOpened`, `ValidationFailed`, `RouteChanged`).
- **`Policy Objects`**: Abstract rules for UX and accessibility:
  - `ValidationPolicy`: Trigger timing (`"on_blur"`, `"on_submit"`), error display, and debounce rules.
  - `NavigationPolicy`: Routing behavior (`"push"`, `"replace"`), scroll restoration, and guard conditions.
  - `AccessibilityPolicy`: WAI-ARIA role assignments, keyboard shortcuts (`["Escape"]`, `["ArrowRight", "ArrowLeft"]`), and focus trapping flags (`trap_focus=True`).
  - `AnimationPolicy`, `FocusPolicy`, and `ToastPolicy`.

---

## 4. Interaction Builder Engine

The `InteractionBuilder` (`services/design/interaction_builder.py`) traverses the `RenderProject` and `ComponentManifest` to infer appropriate interactivity for 17 canonical component categories:
1. `modal`: Generates `modal_sm` state machine, `ModalOpened`/`ModalClosed` events, Escape shortcut, and focus trapping.
2. `accordion`: Generates `accordion_sm`, `AccordionToggled` event, `role="region"`, and Enter/Space toggling.
3. `tabs`: Generates `tabs_sm`, `TabSelected` event, `role="tablist"/"tab"/"tabpanel"`, and Arrow key navigation.
4. `dropdown`: Generates `dropdown_sm`, `DropdownOpened` event, `role="listbox"/"option"`, and Escape dismissal.
5. `navbar`, `sidebar`, `footer`, `menu`, `hero`, `card`, `grid`, `table`, `form`, `input`, `button`, `badge`, and `generic`.

---

## 5. Provider Translation Contract

Rendering providers consume `RenderingContext.interaction_model` and translate neutral definitions into framework-specific runtime code. For the **React Rendering Provider**:
- **State Machine Translation**: Maps `StateMachineDefinition` initial states and transitions to React `useState` hooks and toggle/select handler functions.
- **Event Bus Translation**: Translates `InteractionEvent` emissions into optional callback prop invocations (e.g., `if (onClose) onClose();`).
- **Accessibility Translation**: Translates `AccessibilityPolicy` into WAI-ARIA JSX attributes (`role`, `aria-expanded`, `aria-selected`, `aria-controls`, `aria-modal`) and DOM event listeners (`onKeyDown`, focus trapping queries, active element restoration).

---

## 6. Verification & Automated QA

Compliance with this ADR is enforced across four verification suites in `tests/`:
1. **`test_interaction_builder.py`**: Verifies inference across 17 component categories and asserts 0% framework keyword leakage.
2. **`test_interaction_translation.py`**: Verifies that `ReactRenderingProvider` correctly translates neutral models into React hooks, handlers, and ARIA attributes without modifying the underlying domain models.
3. **`test_accessibility_behavior.py`**: Verifies WAI-ARIA roles, Escape key handling, Enter/Space toggling, Arrow key navigation, focus trapping, and focus restoration upon modal dismissal.
4. **`test_playwright_interaction.py`**: Launches an end-to-end headless Chromium browser session via Playwright, executing real user clicks and keyboard events against synthesized Vite/React interactive playgrounds.

---

## 7. Consequences & Next Steps

- **Positive**: Complete decoupling of UI interaction rules from rendering frameworks; guaranteed WAI-ARIA compliance across all generated components; robust E2E testability.
- **Constraints**: All future rendering providers (e.g., Flutter, Vue) must implement translation layers for `InteractionModel` without altering the domain classes or planning pipeline.
