# ADR 0021: Agency Workflow Realignment

**Status**: Accepted  
**Date**: 2026-07-16  

## Context

Nexora Studio was initially conceptualized with elements of a self-service SaaS Website Generator, where customers would interact directly with `Builder Session`, configure AI prompts, and invoke the Website Generation Engine. 
As the product evolved, it became evident that the optimal business model for Nexora Studio is an AI-powered internal development platform for an agency. 

In a SaaS model, exposing raw generation tools, AI controls, and `Builder Session` workspaces to untrained clients leads to an influx of support tickets, misalignment on expectations, and quality degradation. By pivoting to an **Agency Workflow**, Nexora Studio places the developer back in the driver's seat. 

The client submits requirements, the Developer owns the `Builder Session`, and the AI acts as a sophisticated, iterative assistant rather than a fully autonomous customer-facing product.

## Decision

We will completely realign the system's domain model, security boundaries, and generation flow to support the Agency Workflow. This involves several critical structural shifts:

### 1. Project Management Hierarchy (The Business Truth)
We are decoupling business specifications from technical configurations.
- **`nexora.project`**: The overarching client engagement (e.g., "Acme Corp Web Presence").
- **`nexora.project_request`**: Independent scopes of work under a project (New Website, Maintenance, Bug Fix).
- **`nexora.project_requirements`**: The single source of truth for all business-level requirements (branding, pages, features, assets). It replaces the concept of "Project Specification".

### 2. Developer Assignments
Developers will no longer be implicitly tied to a project. We introduce **`nexora.developer_assignment`** to route `Project Request`s to developers, enabling workload tracking, KanBan integration, and strict ownership tracking for the `Builder Session`.

### 3. Separation of Configuration and Session
- **`nexora.builder_configuration` is Immutable**: It acts purely as a technical snapshot generated from `Project Requirements`. Once created, it cannot be edited. It defines the framework, runtime, git profile, and AI provider selection for generation.
- **`nexora.builder_session` is Mutable**: It is an internal-only workspace where the assigned developer manages MCP states, runtime overrides, debugging configurations, and AI conversational context.

### 4. Continuous AI Review Pipeline
The Website Generation Engine will be extended to support a multi-pass AI review pipeline before a developer sees the code. The new stages include:
1. **AI Self Review** (Project completeness)
2. **AI Bug Fix Pass** (Compilation and runtime repair)
3. **AI Code Quality Pass** (Refactoring and architecture compliance)
4. **AI Security Review** (Vulnerability detection)

These stages output structured reports to the `Builder Session`. Developer review remains strictly mandatory before any client review or deployment.

### 5. Multi-Agent Provider Manager & Reproducibility
- The system will abstract AI integration through an **AI Provider Manager**, allowing dynamic routing between local (Ollama) and premium cloud (Claude, GPT, Gemini) models based on task complexity.
- **Strict Reproducibility**: Every AI generation pass will log the provider, model, exact prompt, generation parameters, patch diff, timestamps, and the approving developer to a central audit log. This guarantees unforgeable traceability for all code modifications.

## Consequences

- **Security Boundaries**: Clients are formally locked out of all generation pipelines, AI tools, and Builder Sessions. Client portals become strictly read-only regarding project statuses.
- **Clean Separation**: Technical complexity is completely separated from business requirements.
- **Quality Assurance**: AI acts as a continuous integrator and reviewer, enforcing agency-level code quality before a human developer takes over. 
- **Auditability**: The reproducibility doctrine ensures no AI "black box" code enters the production repository without an explicit, traceable lineage.
