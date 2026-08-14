# Interaction Translation Report: React Provider Implementation

- **Document Version**: 1.0.0
- **Phase**: 12D (Interaction & Behavior Synthesis Engine)
- **Target Audience**: Frontend Engineers, Provider Developers, React Specialists

---

## 1. Executive Summary

This report documents the translation mechanism utilized by the **React Rendering Provider** (`ReactRenderingProvider`) and **React Component Library** (`ReactComponentLibrary`) to transform provider-neutral interaction domain models into production-ready React 18 / JSX runtime code.

The translation layer serves as the critical bridge that converts abstract finite state automata (`StateMachineDefinition`), canonical event emissions (`InteractionEvent`), and WAI-ARIA UX rules (`AccessibilityPolicy`) into standard React patterns: `useState` hooks, `useRef` DOM references, `useEffect` lifecycle event listeners, and JSX event handler props (`onClick`, `onKeyDown`).

---

## 2. Translation Pipeline Architecture

When `ReactRenderingProvider.generate_project(context)` is invoked, it extracts `context.interaction_model` and passes it to `ReactComponentLibrary`:

```
Provider-Neutral Domain Model                 React Runtime Implementation
(services/design/interaction_model.py)        (services/design/react_component_library.py)
+------------------------------------+        +--------------------------------------------+
| StateMachineDefinition             |  --->  | const [isOpen, setIsOpen] = useState(...)  |
| - initial_state: "CLOSED"          |        | const [activeTab, setActiveTab] = useState |
| - transitions: ["TOGGLE", ...]     |        | const [expanded, setExpanded] = useState   |
+------------------------------------+        +--------------------------------------------+
                                              
+------------------------------------+        +--------------------------------------------+
| InteractionEvent                   |  --->  | if (onClose) onClose();                    |
| - event_name: "ModalClosed"        |        | if (onChange) onChange(idx);               |
| - event_name: "TabSelected"        |        | if (onSelect) onSelect(option, idx);       |
+------------------------------------+        +--------------------------------------------+
                                              
+------------------------------------+        +--------------------------------------------+
| AccessibilityPolicy                |  --->  | role="dialog" aria-modal="true"            |
| - wai_aria_role: "dialog"          |        | role="tablist" aria-selected={isSelected}  |
| - keyboard_shortcuts: ["Escape"]   |        | onKeyDown={(e) => handleKeyDown(e)}        |
| - trap_focus: True                 |        | modalRef.current.querySelectorAll(...)     |
+------------------------------------+        +--------------------------------------------+
```

---

## 3. State Machine to Hook Translation

Provider-neutral state machines define finite state automata without referencing React hooks. The React translation layer maps these automata into functional component hooks:

### 3.1 Modal Dialog Translation (`modal_sm`)
- **Neutral Model**: `StateMachineDefinition(initial_state="CLOSED", transitions=[StateTransition(from_state="CLOSED", to_state="OPEN", trigger="TOGGLE")])`
- **React Translation**:
  - In `Modal.jsx`: Injects `isOpen` boolean prop and `onClose` callback prop.
  - In consuming parent components (`App.jsx` or section wrappers): Synthesizes `const [modalOpen, setModalOpen] = useState(false);` and binds `<Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} />`.

### 3.2 Accordion Translation (`accordion_sm`)
- **Neutral Model**: `StateMachineDefinition(initial_state="COLLAPSED", transitions=[StateTransition(from_state="COLLAPSED", to_state="EXPANDED", trigger="TOGGLE")])`
- **React Translation**:
  - In `Accordion.jsx`: Synthesizes internal state `const [expanded, setExpanded] = useState(defaultExpanded);`.
  - Maps `"TOGGLE"` trigger to toggle handler:
    ```javascript
    const handleToggle = (idx) => {
      setExpanded(expanded === idx ? null : idx);
    };
    ```

### 3.3 Tabs Translation (`tabs_sm`)
- **Neutral Model**: `StateMachineDefinition(initial_state="TAB_0", transitions=[StateTransition(from_state="*", to_state="TAB_N", trigger="SELECT")])`
- **React Translation**:
  - In `Tabs.jsx`: Synthesizes `const [activeTab, setActiveTab] = useState(defaultTab);`.
  - Maps `"SELECT"` trigger to index selection handler:
    ```javascript
    const handleSelect = (idx) => {
      setActiveTab(idx);
      if (onChange) onChange(idx);
    };
    ```

### 3.4 Dropdown Translation (`dropdown_sm`)
- **Neutral Model**: `StateMachineDefinition(initial_state="CLOSED", transitions=[StateTransition(from_state="CLOSED", to_state="OPEN", trigger="CLICK")])`
- **React Translation**:
  - In `Dropdown.jsx`: Synthesizes `const [isOpen, setIsOpen] = useState(false);` and `const [focusedIndex, setFocusedIndex] = useState(-1);`.
  - Maps trigger to menu toggle:
    ```javascript
    const toggleOpen = () => {
      setIsOpen(!isOpen);
      if (!isOpen) setFocusedIndex(0);
    };
    ```

---

## 4. Event Bus to Callback Translation

In provider-neutral architecture, interactions emit named events (`InteractionEvent`). The React translation layer translates event emissions into standard React callback prop patterns:
- **`ModalClosed`**: Translated to `if (onClose) onClose();` invoked upon background overlay click, close button activation, or Escape key press.
- **`TabSelected`**: Translated to `if (onChange) onChange(idx);` invoked whenever a user clicks or arrow-navigates to a new tab.
- **`AccordionToggled`**: Translated to `if (onToggle) onToggle(idx, isOpen);` allowing parent components to track panel expansion.
- **`DropdownOpened` / Option Selection**: Translated to `if (onSelect) onSelect(option, idx);` invoked when a user activates a listbox option.

---

## 5. Behavior & Policy Translation

UI policies defined in `BehaviorDefinition` are translated into React DOM attributes and event listeners:

### 5.1 Accessibility Policy Translation
- **WAI-ARIA Attributes**: Synthesizes exact string literals for dynamic ARIA states:
  - Accordion headers: `aria-expanded={open ? 'true' : 'false'}` and `aria-controls={"accordion-panel-" + idx}`.
  - Tab buttons: `role="tab"`, `aria-selected={isSelected ? 'true' : 'false'}`, `tabIndex={isSelected ? 0 : -1}`.
  - Dropdown trigger: `aria-haspopup="listbox"`, `aria-expanded={isOpen ? 'true' : 'false'}`.

### 5.2 Keyboard Shortcuts & DOM Event Listeners
- Translates `keyboard_shortcuts` lists into `onKeyDown` handler branches:
  - **Escape Dismissal**: In `Modal.jsx` and `Dropdown.jsx`, binds global or container keydown listeners:
    ```javascript
    if (isOpen && e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
      if (triggerRef.current) triggerRef.current.focus();
    }
    ```
  - **Arrow Key Navigation**: In `Tabs.jsx` and `Accordion.jsx`, computes modular arithmetic indices for Left/Right and Up/Down navigation, automatically transferring DOM focus:
    ```javascript
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      nextIdx = (idx + 1) % tabs.length;
    }
    handleSelect(nextIdx);
    const targetTab = document.getElementById(`tab-btn-${nextIdx}`);
    if (targetTab) targetTab.focus();
    ```

---

## 6. Translation Verification Suite

To ensure translation integrity, `tests/test_interaction_translation.py` validates that:
1. `ReactRenderingProvider` accepts `interaction_model` in `RenderingContext` without error.
2. All synthesized `.jsx` files contain expected React hooks (`useState`, `useRef`, `useEffect`).
3. ARIA attributes and keyboard handlers match the policy specifications defined in the neutral model.
4. The underlying `InteractionModel` objects remain 100% provider-neutral before, during, and after React translation.

---

## 7. Summary

The React translation layer successfully bridges the provider-neutral Interaction & Behavior Synthesis Engine with modern React 18 frontend best practices. By translating finite state automata into functional component hooks and accessibility policies into compliant JSX attributes, Nexora Studio delivers accessible, highly interactive web applications without compromising architectural decoupling.
