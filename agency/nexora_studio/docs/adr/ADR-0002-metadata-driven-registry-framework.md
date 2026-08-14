# ADR-0002
## Title
Metadata-Driven Registry Framework

## Status
Accepted

## Date
2026-07-10

## Context

The Nexora Studio architecture requires a robust and flexible way to register internal platform applications, capabilities, navigation entries, and services without hardcoding them or duplicating standard Odoo business models. A purely metadata-driven registry approach avoids polluting the business data space while providing high extensibility for future phases.

## Decision

We will implement a Metadata-Driven Registry Framework consisting of five core entities: `nexora.component`, `nexora.capability`, `nexora.service`, `nexora.navigation`, and `nexora.category`.

- **Why a metadata-driven registry exists:** To loosely couple the platform's features, capabilities, and menus, allowing features to be dynamically discovered and toggled.
- **Why it must not duplicate Odoo business models:** Nexora Studio is an operating system layering over Odoo; standard CRM/Project workflows remain native to Odoo, whereas registries only track *internal platform features*.
- **Why Components replace Applications:** "Component" is a more accurate terminology reflecting modular functionality, whereas "Application" implies a massive standalone system.
- **Why categories are database driven instead of Python Selection fields:** Database-driven categories (`nexora.category`) allow infinite extensibility at runtime without modifying Python code or restarting the server.
- **Why XML IDs are used instead of numeric IDs:** XML IDs provide immutable, environment-agnostic canonical identifiers that survive database migrations and multi-environment deployments.
- **Why active replaces enabled:** `active` is the standard Odoo ORM convention for soft-deletion and toggling visibility seamlessly.
- **Why semantic_version is used:** It strictly enforces standardized release version tracking for components.

## Consequences

**Positive:**
- Extremely extensible architecture.
- Full compliance with Odoo standard conventions.
- Easy to query capabilities at runtime.

**Negative:**
- Requires careful handling of XML IDs to prevent data duplication.
