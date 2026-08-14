# ADR-0029: Design Provider Framework & Penpot Adoption

## Status: Accepted

## Date: 2026-07-25

## Context
As Nexora Studio scales its AI-driven website generation and design intelligence capabilities, external design asset integrations have become a critical architectural boundary. Previously, architectural plans and prototype adapters referenced Figma Desktop as a primary design source. However, Figma Desktop has proven to be an unnecessary blocker: its proprietary, closed-desktop ecosystem introduces integration friction, authentication bottlenecks, and vendor lock-in that conflict with Nexora Studio's cloud-native, automated builder workflows.

We require a vendor-neutral design architecture that isolates Builder Sessions from any specific design tool while adopting an open-source, web-first primary provider.

## Decision

We establish the **Design Provider Framework** and adopt **Penpot** as our default design provider.

### 1. Vendor-Neutral Abstraction Layer (`DesignProvider`)
All design system interactions must go through the abstract `DesignProvider` interface located in `services/design/design_provider.py`. No core module, Builder Session, or generation orchestrator may directly import or depend on Penpot, Figma, or any specific vendor library.

The `DesignProvider` interface exposes a comprehensive, future-ready contract:
- **Core Operations**: `authenticate`, `create_project`, `create_page`, `create_component`, `export_svg`, `export_png`, `export_pdf`, `get_project`.
- **Expanded Operations**: `create_workspace`, `create_frame`, `update_component`, `delete_component`, `create_design_tokens`, `apply_theme`, `export_assets`, `import_assets`, `list_projects`, `sync_project`, `validate_design`.

### 2. Primary Default Provider (`PenpotDesignProvider`)
We register Penpot (`PenpotDesignProvider`) as the primary default design provider. In accordance with our architecture-first mandate, this provider is introduced as an architectural stub (`services/design/penpot_provider.py`). All methods explicitly raise `NotImplementedError("Architecture stub...")` until runtime integration and API communication are authorized in subsequent execution phases.

### 3. Design Orchestration (`nexora.design_orchestrator`)
We introduce an Odoo abstract model, `nexora.design_orchestrator`, responsible for provider discovery, instantiation, and routing. Builder Sessions interact with design assets exclusively by requesting an interface handle from this orchestrator.

### 4. Complete Eradication of Figma as a Core Dependency
All existing code, test suites, Component Source Framework (CSF) adapters (`figma_adapter.py`), registries, and architectural records have been stripped of mandatory Figma dependencies. While Figma may be supported in the future as an optional secondary provider, it must never appear as a required dependency in any execution pipeline or roadmap.

## Consequences

### Positive
- **Zero Vendor Lock-In**: The Builder Session is completely decoupled from external design tool implementations.
- **Open-Source Alignment**: Selecting Penpot aligns Nexora Studio with open web standards (SVG/CSS native design) and self-hosted cloud compatibility.
- **Future-Ready Contract**: The 19-method interface anticipates all future design automation requirements without requiring breaking schema changes later.

### Negative / Trade-offs
- **Deferred Runtime Integration**: Until Penpot API client wrappers and network transports are implemented in future phases, design operations remain in an architectural stub state.
