# Interaction & Behavior Synthesis Architecture Report

- **Document Version**: 1.0.0
- **Phase**: 12D (Interaction & Behavior Synthesis Engine)
- **Target Audience**: Core AI Architects, Provider Developers, Quality Assurance Engineers

---

## 1. Executive Summary

This technical report details the architecture and implementation of the **Interaction & Behavior Synthesis Engine** in Nexora Studio. Designed to bridge the gap between static component manifests and interactive frontend applications, the engine models user interactions, finite state machines, event buses, and accessibility policies in a **100% provider-neutral** format.

By abstracting interaction rules away from framework-specific syntax (such as React's `useState` or DOM `onClick` handlers), Nexora Studio ensures that interactive behavior can be synthesized uniformly across multiple rendering targets (React, Vue, Flutter, Angular) while strictly preserving the frozen planning layer contracts established in ADR-0035.

---

## 2. Architectural Boundaries & Pipeline Flow

The interaction layer operates as an intermediate transformation stage within the multi-provider rendering pipeline:

```
+-------------------------------------------------------+
|                 AI Requirements Engine                |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|          Planning Layer (ADR-0035 Frozen)             |
|   (Blueprint, Design System, Layout, Asset, Content)  |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|             Render Model (RenderProject)              |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|          Component Manifest (ComponentManifest)       |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|        Interaction Model (InteractionModel)           |  <=== [Phase 12D Synthesis]
|  - State Machines, Event Bus, Policies, Behaviors     |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|         Rendering Context (RenderingContext)          |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|    Rendering Provider (e.g., ReactRenderingProvider)  |
+-------------------------------------------------------+
                            ↓
+-------------------------------------------------------+
|              Generated UI Code & Bundles              |
+-------------------------------------------------------+
```

### 2.1 Non-Modification Guarantees
The introduction of `InteractionModel` and `InteractionBuilder` required **zero modifications** to existing upstream planning and design engines:
- Requirements Engine
- Builder Session & Blueprint Engine
- Design System Engine & Layout Intelligence Engine
- Asset Planning Engine & Content Intelligence Engine
- Render Model (`RenderProject`, `RenderPage`, `RenderSection`)
- Component Manifest (`ComponentManifest`, `ComponentEntry`)

---

## 3. Domain Model Architecture (`interaction_model.py`)

The domain models reside in `services/design/interaction_model.py` and are built around strict separation of concerns:

### 3.1 Root Aggregate (`InteractionModel`)
- Acts as the primary container attached to `RenderingContext.interaction_model`.
- Maintains dictionaries mapping component IDs and categories to their respective definitions, state machines, events, and behaviors.
- Provides registration and lookup APIs: `register_interaction()`, `add_state_machine()`, `register_event()`, `register_behavior()`.

### 3.2 Interaction Definitions (`InteractionDefinition`)
- Defines what triggers interactivity on a component and what actions result from those triggers.
- Composed of `InteractionTrigger` (e.g., trigger type `"CLICK"`, key target `"Escape"`) and `InteractionAction` (e.g., action type `"TOGGLE"`, target `"modal-panel"`).

### 3.3 State Machine Automata (`StateMachineDefinition`, `StateTransition`)
- Replaces ad-hoc boolean flags with formal finite state automata.
- Defines `initial_state` and a list of `StateTransition` objects specifying `from_state`, `to_state`, `trigger`, and optional `guard` conditions.
- Canonical automata supported: `modal_sm`, `accordion_sm`, `tabs_sm`, `dropdown_sm`, `pagination_sm`, `form_sm`, `navbar_sm`.

### 3.4 Provider-Neutral Event Bus (`InteractionEvent`)
- Enforces an event bus pattern where user interactions emit structured domain events rather than executing direct DOM manipulations.
- Standard event catalog:
  - `ButtonClicked`: Emitted on interactive button activation.
  - `ModalOpened` / `ModalClosed`: Emitted on dialog state transitions.
  - `TabSelected`: Emitted when active tab index changes.
  - `AccordionToggled`: Emitted when accordion panels expand or collapse.
  - `DropdownOpened`: Emitted when listbox menus open.
  - `ValidationFailed`: Emitted when form input validation policies fail.
  - `RouteChanged`: Emitted during navigation policy execution.

### 3.5 Policy Objects
- Encapsulates UX rules and WAI-ARIA accessibility constraints:
  - `ValidationPolicy`: Controls validation timing (`"on_blur"`, `"on_submit"`), debounce milliseconds, and error display rules.
  - `NavigationPolicy`: Controls routing actions (`"push"`, `"replace"`), target URIs, and scroll restoration.
  - `AccessibilityPolicy`: Specifies WAI-ARIA roles (`"dialog"`, `"region"`, `"tablist"`, `"listbox"`), keyboard shortcuts (`["Escape"]`, `["Enter", " "]`, `["ArrowRight", "ArrowLeft"]`), focus trapping (`trap_focus=True`), and focus restoration (`restore_focus=True`).
  - `AnimationPolicy`, `FocusPolicy`, and `ToastPolicy`.

---

## 4. Interaction Inference Engine (`interaction_builder.py`)

The `InteractionBuilder` class in `services/design/interaction_builder.py` provides automated synthesis of interactivity from static manifests.

### 4.1 Inference Algorithm
When `InteractionBuilder.build(render_project, manifest)` is invoked:
1. It initializes an empty `InteractionModel(project_id)`.
2. It iterates through all pages and sections in the `RenderProject`, mapping each section and component entry in the `ComponentManifest` to a canonical category.
3. It executes category-specific builder rules (`_infer_component_category`), registering appropriate state machines, events, behaviors, and accessibility policies.

### 4.2 Supported Component Categories
The inference engine supports 17 distinct component categories:
| Category | State Machine | Canonical Event | WAI-ARIA Role | Keyboard Shortcuts |
| :--- | :--- | :--- | :--- | :--- |
| `modal` | `modal_sm` | `ModalOpened` / `ModalClosed` | `dialog` | `Escape` |
| `accordion` | `accordion_sm` | `AccordionToggled` | `region` | `Enter`, `Space`, `ArrowDown/Up` |
| `tabs` | `tabs_sm` | `TabSelected` | `tablist`/`tab`/`tabpanel` | `ArrowRight`, `ArrowLeft`, `Home/End` |
| `dropdown` | `dropdown_sm` | `DropdownOpened` | `listbox`/`option` | `Escape`, `ArrowDown/Up`, `Enter` |
| `navbar` / `menu` | `navbar_sm` | `RouteChanged` | `navigation` | `Tab`, `Enter` |
| `form` / `input` | `form_sm` | `ValidationFailed` | `form` / `textbox` | `Enter` (submit) |
| `button` / `cta` | N/A | `ButtonClicked` | `button` | `Enter`, `Space` |
| `sidebar`, `footer`, `hero`, `card`, `grid`, `table`, `badge`, `generic` | N/A | Category-specific | Generic / Semantic | Standard focus |

---

## 5. Architectural Verification & Zero Leakage Compliance

To guarantee that no rendering framework syntax leaks into the domain models or builder engine, automated unit tests (`tests/test_interaction_builder.py`) inspect all generated dictionary attributes, strings, and class names.
- **Verification Method**: Reflection and regex scanning across all properties of `InteractionDefinition`, `BehaviorDefinition`, `StateMachineDefinition`, and `Policy` objects.
- **Audit Result**: **0% Framework Keyword Leakage confirmed** across 100% of synthesized component models.

---

## 6. Summary

The Interaction & Behavior Synthesis Engine successfully provides a robust, provider-neutral foundation for interactive frontend generation. By formalizing state machines, event buses, and accessibility policies at the domain layer, Nexora Studio ensures high-quality, accessible, and maintainable UI code synthesis across all supported rendering providers.
