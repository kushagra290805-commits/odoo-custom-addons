# ADR 0025: AI Configuration Governance Foundation

## Status
Approved

## Context
As the Nexora Studio platform scales, the AI configuration has become fragmented. Adapters, the `ProviderManager`, the `CostRouter`, and `Settings` all independently query `ir.config_parameter` for models, API keys, and routing logic. This configuration drift violates the Single Responsibility Principle and creates architectural blind spots. 

We need to establish a single authoritative AI Configuration Layer across Nexora Studio without redesigning the AI pipeline or changing the core orchestration (ProviderManager, CostRouter, etc.).

## Decision
1. **AI Configuration Service (`nexora.ai_configuration_service`):** We will introduce a centralized component divided into three logical sections:
   - **Configuration Repository:** Handles reading, writing, caching, and versioning config from `ir.config_parameter`.
   - **Model Resolver:** Handles resolving active providers, models, listing models, and validating against the catalog.
   - **Provider Health:** Performs readiness checks and configuration completeness checks.

2. **Remove Configuration Duplication:** All direct calls to `ir.config_parameter` and `adapter._default_model()` related to AI settings will be replaced by calls to `AIConfigurationService`.

3. **Refactor ProviderManager & CostRouter:** 
   - `ProviderManager` will perform routing, dispatch, retries, fallback execution, and validation, but will NEVER infer configuration or choose a default model.
   - `CostRouter` will only determine provider priority and pricing tiers without selecting models.

4. **Refactor Adapters:** Adapters will become purely execution engines. They will no longer contain `_default_model()` methods or directly fetch configuration keys from the environment.

5. **Settings UI Refactor:** The settings view will become a strict client of `AIConfigurationService`, no longer directly manipulating `ir.config_parameter`.

## Consequences
- **Positive:** Centralized configuration guarantees a single source of truth, enabling robust caching (read-through cache), validation, and testing. It prevents configuration drift.
- **Negative:** Minor refactoring effort across all adapters and orchestration layers; requires careful regression testing to ensure the existing pipeline continues to function seamlessly.
