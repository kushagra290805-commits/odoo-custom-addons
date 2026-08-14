# Phase 28 — Capability Discovery Report

## Discovery Process
The `McpCapabilityDiscoveryService` coordinates discovery via:
1. Dispatching `tools.list`, `resources.list`, `prompts.list` requests to the runtime.
2. Parsing the resulting JSON outputs.
3. Translating raw capability responses into the `nexora.mcp_discovered_tool` authoritative persistence model.

## Model Independence
The discovery persists raw JSON schemas and signatures, ensuring the data is strictly declarative. No execution data is bound into the discovery model, protecting ADR-0050 connector isolation boundaries.
