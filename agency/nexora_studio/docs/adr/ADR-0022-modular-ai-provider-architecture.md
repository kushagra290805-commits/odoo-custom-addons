# ADR-0022: Modular AI Provider Architecture

## Status: Accepted

## Date: 2026-07-16

## Context

Phase 8C.3 established the `AIProviderManager` as the single routing endpoint
for all AI generation operations, replacing the legacy `AIProviderFactory` and
`MockProvider`.  However, the implementation was monolithic — provider-specific
HTTP logic (Ollama, Claude, OpenAI) was embedded directly inside
`route_request()`.  This made it impossible to:

- Add new providers without modifying the manager
- Configure providers independently
- Implement cost-based routing
- Support provider-specific features (model listing, JSON mode, etc.)

## Decision

Introduce a modular **Adapter Architecture** under `services/ai/`:

### Components

1. **BaseAdapter** (`nexora.ai_adapter_base`) — Abstract interface defining
   `is_available()`, `list_models()`, `chat_completion()`, `generate_code()`.
   Includes built-in retry logic and parameter helpers.

2. **Typed Adapters** — One adapter per provider, each inheriting from
   BaseAdapter:
   - `nexora.ai_adapter.ollama`
   - `nexora.ai_adapter.openrouter`
   - `nexora.ai_adapter.openai`
   - `nexora.ai_adapter.claude`
   - `nexora.ai_adapter.gemini`
   - `nexora.ai_adapter.generic_openai`

3. **CostRouter** (`nexora.ai_cost_router`) — Classifies tasks into
   cost tiers (simple/medium/complex) and selects the first available
   provider from a configurable fallback chain.

4. **ProviderManager** (`nexora.ai_provider_manager`) — Preserved model
   name for backward compatibility.  Now delegates to CostRouter and
   typed adapters instead of containing provider logic directly.

5. **ContextBuilder** (`nexora.context_builder`) — Assembles the full
   Agency Workflow chain into a structured context dict for AI prompts.

6. **PatchEngine** (`nexora.patch_engine`) — Secure pipeline for parsing,
   validating, and applying AI-generated code changes with path traversal
   protection, syntax validation, and git checkpointing.

7. **TemplateAnalyzer** (`nexora.template_analyzer`) — Auto-discovers
   pages, layouts, components, hooks, stores, API layers, and theme
   variables from a workspace.

### Key Constraint: AbstractModel Bool Evaluation

Odoo `AbstractModel` recordsets evaluate to `False` with `bool()` because
they have zero records.  All adapter existence checks must use
`adapter is not None` instead of `if adapter:`.

## Consequences

- Any new AI provider can be added by creating a single adapter file that
  inherits from `nexora.ai_adapter_base`.
- Provider selection is fully runtime-configurable via `ir.config_parameter`.
- The generation pipeline (Stages 06, 09-12) no longer contains any
  provider-specific or hardcoded generation logic.
- Stage 06 now generates code based entirely on Project Requirements,
  Builder Configuration, and Template Analysis.
- All AI operations are routed through the CostRouter for intelligent
  cost optimization.
