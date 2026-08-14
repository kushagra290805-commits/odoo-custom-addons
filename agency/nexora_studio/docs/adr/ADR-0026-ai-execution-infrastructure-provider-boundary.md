# ADR 0026: AI Execution Infrastructure Provider Boundary

## Status
Accepted

## Date
2026-07-22

## Context
During Phase 6D, we encountered significant execution pipeline challenges and backend runtime instability. Workers were hanging indefinitely because AI provider adapters (like OpenAI, Ollama, Claude, Gemini) contained legacy, hardcoded retry loops that failed to respect timeout boundaries when configuration or authentication failed. 

Additionally, provider configuration was improperly spread across the orchestration UI (Nexora Console) and the backend (Odoo). This created fragmented state management, where the console attempted to govern the fallback models and API keys, leading to race conditions and inconsistent execution traces. 

We needed to establish a hardened AI Execution Infrastructure that enforces Odoo as the sole source of truth and implements a robust, centralized execution boundary.

## Decision
1. **Odoo as Single Source of Truth:**
   - Nexora Console acts strictly as an orchestrator. It triggers execution but is no longer responsible for configuring API keys, base URLs, or fallback models. The provider configuration in the Console is read-only.
2. **AIExecutionContext:**
   - A single, immutable context object now threads through the entire pipeline (from orchestration down to the adapters), carrying request IDs, job correlation metadata, and resolved model parameters, eliminating fragmented parameters.
3. **ModelResolutionService & CostRouter:**
   - Introduced a deterministic fallback chain. The `CostRouter` evaluates provider capabilities (e.g., requires 'chat' or 'code') and yields a deterministic `ProviderResolution` struct.
4. **ProviderExecutionPolicy:**
   - Ripped out all legacy retry loops from the individual provider adapters.
   - Centralized HTTP timeout, circuit breaking, and retry logic into a single Execution Policy engine. It fast-fails on 401/403 (configuration errors), triggers CostRouter fallback on 429 (rate limits), and applies exponential backoff for 5xx/ReadTimeout network errors.
5. **ProviderHealthService:**
   - Checks endpoint reachability and capability verification separately from execution logic.
6. **AIExecutionHistory & ProviderTelemetry:**
   - Every execution is persistently logged to a new Odoo model, `nexora.ai_execution_history`, capturing provider, model, latency, HTTP failure classification, and error messages.

## Consequences
- **Benefits:** Complete elimination of worker hanging issues. Deep observability into provider performance through persistent telemetry. Deterministic, testable fallback routing. Clear boundary between orchestration (Nexora Console) and execution (Odoo).
- **Trade-offs:** Centralizing the HTTP policy means adapters are tightly bound to the standard requests library signature. The CostRouter logic must be rigorously maintained as new capability tiers emerge.
- **Future extension points:** The immutable `AIExecutionContext` can be extended to support multi-agent correlation IDs, streaming response hooks, and task-level (BuilderSession) model overrides.

## Alternatives Considered
- **Adapter-local retry logic:** Kept initially, but rejected because it led to uncontrolled infinite loops and decoupled HTTP classification logic.
- **Frontend-managed provider configuration:** Rejected because it violates the security boundary and forces the frontend to distribute credentials to the backend via payloads.
- **Direct provider selection without routing:** Rejected as it creates brittle implementations that fail immediately when a primary provider experiences downtime.
- **Stateless execution without execution context:** Rejected due to the inability to properly trace a generation job through the Model Resolution, Cost Routing, and Telemetry layers cleanly.

## Future Considerations
- **Distributed circuit breakers:** Moving the in-memory circuit breaker state to a centralized Redis/database store to unify state across multi-worker deployments (e.g., Gunicorn/uWSGI).
- **Multi-worker execution:** Implementing full async dispatch (e.g. celery or `queue_job`) to decouple the HTTP gateway from the generation lifecycle entirely.
- **Distributed execution history:** Offloading telemetry logging to a distributed log sink to reduce relational database write pressure at scale.
- **Advanced provider scoring:** Utilizing the persistent `AIExecutionHistory` telemetry to dynamically rank providers based on historical latency and failure rates.
- **Dynamic cost optimization:** Factoring live token-pricing APIs into the `CostRouter` to choose the most cost-efficient capable model automatically.
