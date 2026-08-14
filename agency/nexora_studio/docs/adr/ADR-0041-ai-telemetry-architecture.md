# ADR-0041: AI Telemetry & Operational Analytics Architecture

**Status:** Accepted (Frozen in Phase 18.3.1)
**Date:** 2026-07-30

## Context
With the introduction of the Unified Provider Platform (Phase 18.2) and the deprecation of fragmented provider adapters, we needed a unified telemetry and operational analytics architecture. Previous phases suffered from fragmented API requests, isolated token counting, and high overhead due to client-side data aggregations.

To successfully support future phases such as Streaming, Agent Runtime, and Client Website Generation, the telemetry boundaries and tracking mechanisms must be explicitly formalized and strictly decoupled from the core response pipelines.

## Decision
We establish the **AI Telemetry & Operational Analytics Architecture** with the following structural mandates:

### 1. Shared HTTP Abstraction
**All AI Provider Adapters MUST route through the single `_request()` method in `ai_adapter_base.py`.**
- Direct use of `requests.get()` or `requests.post()` in child adapters is strictly prohibited.
- `_request()` manages standard timeouts, connection pooling, and foundational HTTP error conversion (preventing bespoke JSON decoding crashes).

### 2. TelemetryRecorder Responsibilities
**Telemetry must operate entirely decoupled from the generation output path.**
- The `TelemetryRecorder` (`nexora.telemetry_recorder`) handles event parsing, cost calculation, and history logging.
- It operates safely inside a `try/except` block with `sudo()`. Telemetry failures must **never** break or abort a user’s prompt generation.
- It maps directly to `nexora.ai_execution_history`, `nexora.provider.cost_ledger`, `nexora.provider.metrics_aggregation`, and `nexora.runtime_event`.

### 3. DashboardService Responsibilities & API Boundaries
**Metrics aggregation must occur on the backend.**
- The `AIDashboardService` (`nexora.ai_dashboard_service`) is the only system permitted to calculate rolling averages, token sums, and error rates.
- The `AIAnalyticsAPI` REST endpoint (`/api/v1/ai/metrics/dashboard`) acts as a pure delivery transport layer. The React frontend is explicitly forbidden from downloading raw execution histories to perform client-side map/reduce operations.

### 4. Builder Traceability & Execution Constraints
**Every request must trace back to a Builder Session.**
- The `AIExecutionContext` is established as an immutable dataclass (`frozen=True`) passed throughout the generation pipeline.
- It tracks `workspace_id`, `project_id`, and `builder_session_id`. Modifying these correlation IDs after instantiation is an architecture violation.

### 5. Console Integration
- The React frontend `nexora-console` accesses Odoo backend telemetry via Vite proxy pointing explicitly to Odoo's internal API port (`http://127.0.0.1:8069`). All future dashboard panels must query the Odoo REST API and must not establish alternative tracking mechanisms.

## Consequences & Invariants
Future phases (Streaming, Agent Runtime, Client Website Generation) must respect these architectural invariants:
1. **Never bypass `_request()`**: If new streaming protocols (like Server-Sent Events) are added, they must be implemented at the `ai_adapter_base.py` level.
2. **Never break `AIExecutionContext` immutability**: Agentic tools needing scratch data must not mutate the context object; they must derive or return new states.
3. **Never block the event loop for telemetry**: Future tracking (e.g., streaming chunk tracking) must dispatch telemetry asynchronously or securely within non-blocking error bounds.

This architecture freeze ensures operational stability and consistent token accounting regardless of the AI model invoked.
