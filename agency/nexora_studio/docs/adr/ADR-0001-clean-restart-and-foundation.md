# ADR-0001
## Title
Clean Restart and Enterprise Foundation for Nexora Studio

## Status
Accepted

## Date
2026-07-10

## Context

The previous implementation was intentionally abandoned despite containing many completed features. A clean implementation was chosen as it is lower risk than continuous migration.

Reasons for this decision:
- Architecture evolved significantly.
- Earlier implementation accumulated experimental code.
- Multiple iterations introduced technical debt.
- Core business workflow was redesigned.
- Builder Session Service became a first-class architectural component.
- Template Store responsibilities were redefined.
- Project Configuration became an immutable project snapshot.
- Frontend templates are stored outside Odoo.
- AI and MCP integration architecture was finalized.

## Decision

This document records the official architecture.

**Nexora Studio Responsibilities:**
- Internal agency operating system
- Agency workflow orchestration
- Client management
- Project management
- Project Configuration
- AI orchestration
- Deployment orchestration
- Integration with Builder Session Service

**Template Store Responsibilities:**
- Metadata
- Versioning
- Template catalog
- Deployment profiles
- References to frontend templates

**Frontend Templates Responsibilities:**
- HTML
- CSS
- JavaScript
- Assets
- Component source
- Theme source

**Builder Session Service Responsibilities:**
- Shared workspace
- File synchronization
- Preview server
- Git integration
- MCP integration
- AI integration
- Builder sessions

*Note: Clients never interact directly with Odoo.*

## Architectural Principles

1. Never duplicate existing Odoo functionality.
2. Extend Odoo instead of replacing it.
3. Keep modules highly cohesive and loosely coupled.
4. Frontend source code never lives in the database.
5. Builder Session Service owns the editable workspace.
6. Odoo owns business data.
7. Git owns source code history.
8. AI never bypasses the Builder Session Service.
9. Every major architectural change requires a new ADR.
10. Every phase must remain installable and independently testable.

## Consequences

**Positive:**
- Clean architecture
- Lower technical debt
- Easier maintenance
- Better scalability
- Predictable integrations
- Easier onboarding
- Enterprise-grade modularity

**Negative:**
- Previous implementation discarded
- Initial rebuild effort
- More upfront planning

## Future ADRs

The following numbers are reserved for future topics:
- ADR-0002 Module Boundaries
- ADR-0003 Registry Architecture
- ADR-0004 Builder Session Service
- ADR-0005 Template Store
- ADR-0006 Deployment Pipeline
- ADR-0007 AI & MCP Integration
- ADR-0008 Multi-tenant Client Projects
