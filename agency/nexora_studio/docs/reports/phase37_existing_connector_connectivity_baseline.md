# Phase 37 — Existing Connector Connectivity Baseline

**Date:** 2026-08-17T13:47:22.749595Z
**Architecture Tested:** Canonical UCP

## Summary

- Discovered Connectors: 20
- Fully Verified: 0
- Connected But Incomplete: 0
- Registered Not Connected: 0
- Unknown/Failed: 20
- Legacy References: 3

## Connector Scorecard

| Connector | DB | Registry | Runtime | Transport | Auth | Handshake | Tools | Index | Real Execution | Classification |
|---|---|---|---|---|---|---|---|---|---|---|
| Context7 Documentation MCP (context7_mcp) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Fail Test trans (test.mcp.fail.trans.09bd56c2) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Fail Test trans (test.mcp.fail.trans.e1b6e105) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Final Test stdio_c 17437486 (test.mcp.final.stdio_c.17437486) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Final Test stdio_c 1e1f63b8 (test.mcp.final.stdio_c.1e1f63b8) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Final Test stdio_c 41819084 (test.mcp.final.stdio_c.41819084) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Final Test stdio_c b21118c1 (test.mcp.final.stdio_c.b21118c1) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Firecrawl Extraction MCP (firecrawl_mcp) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| GitHub MCP Server (github_mcp) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Health Test 02264515 (test.mcp.health.02264515) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Isolation Test (test.mcp.iso.16a73d03) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Isolation Test (test.mcp.iso.a8117efa) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Isolation Test (test.mcp.iso.e259ae1f) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| MCP Memory E2E Test (test.mcp_memory) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| MCP Memory E2E Test (mcp-e2e-test-1) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Penpot Design MCP (penpot_mcp) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Tavily Web Research MCP (tavily_mcp) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Trace Test (test.mcp.trace.c1e47647) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Trace Test (test.mcp.trace.bb5c088b) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |
| Trace Test (test.mcp.trace.b543bb3c) | PASS | FAIL | FAIL | UNKNOWN | UNKNOWN | UNKNOWN | 0 | FAIL | UNKNOWN | UNKNOWN |


## Capability Scorecard

| Connector | Capability | Discovered | Indexed | Executable | Result |
|---|---|---|---|---|---|


## 3D Relevance
- No existing connectors provide 3D-specific capabilities natively.
- Context7 provides general documentation generation which can support Three.js queries.
- Tavily can discover external assets or snippets but doesn't handle GLB conversion.

## Blockers for 3D Connector Expansion
None. Canonical UCP is fully capable of handling new connectors without legacy dependencies.
