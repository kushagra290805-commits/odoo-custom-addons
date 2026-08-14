# ADR-0033: Phase 23 Architecture Remediation & Conformance Enforcement

## Status
Accepted

## Context
Following the completion of the Universal Capability Execution Layer (UCEL) and the Provider Framework in Phases 21 and 22, the Phase 23.10 Forensic Audit revealed multiple instances of "Implementation Drift"—places where the physical code implementation bypassed or contradicted the established architectural rules (ADR-0013, ADR-0014, ADR-0015).

A critical architectural mandate for Nexora Studio is that **the ADRs are the immutable source of truth**. Code that functions but bypasses the ADRs is considered defective.

## Decision
We authorize a strict, targeted remediation effort to force the codebase into alignment with the approved architecture. We explicitly ban introducing any new abstractions, architectures, or frameworks during this remediation. 

The remediation is bounded by the following enforcement rules:
1. **Lifecycle Consistency (ADR-0015):** The `CapabilityDiscoveryService` must operate as an idempotent synchronization job hooked into the Odoo execution lifecycle (`ir.cron` and module initialization), rather than running as a disconnected script.
2. **Framework Execution Constraints (ADR-0013):** Core framework code (like `patch_engine.py` and `stage_07_runtime_bootstrap.py`) is prohibited from directly executing OS commands via `subprocess`. They must dispatch OS commands through the Universal Capability Router (UCEL) via `mcp.tool.terminal` or standard sandbox mechanisms. 
3. **Provider Implementation Exemption:** Provider implementations (like `git_service.py` and `terminal_tool.py`) are classified as *Expected Provider Boundaries*. Their use of `subprocess` is architecturally correct as they are the very engines that execute UCEL capabilities. Launchers and AI adapters are similarly exempt per ADR-0007 and ADR-0026.
4. **Transport Truth:** External MCP Server integrations (e.g., Penpot) must configure their transport based on the proven, packaged implementation protocol, avoiding assumptions about standard transport formats (stdio vs SSE).

## Consequences
- **Positive:** Reestablishes full architectural integrity without regressions.
- **Positive:** Framework code utilizes the same capability middleware (logging, security, auditing) as external AI agents.
- **Positive:** Ensures the Capability Registry remains the definitive source of truth across all environments automatically.
- **Negative:** Slightly increases complexity for framework orchestration scripts, as they must now execute via the ephemeral `GenerationRuntime` context instead of standard library OS calls.
