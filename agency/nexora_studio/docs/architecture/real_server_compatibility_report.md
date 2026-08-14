# Real Server Compatibility Report

## Overview
This report validates the interoperability of the Universal Connector Platform with actual MCP reference servers without any architectural drift from ADR-0050.

## Verified Facts
- **Execution Engine**: All real server processes are spawned using `anyio.open_process` (shell=False) through the official `mcp.client.stdio` transport adapter.
- **Payload Verification**: JSON-RPC schema compliance is handled cleanly by the upstream SDK.
- **Trace Interception**: `TraceReceiveStream` and `TraceSendStream` safely capture bidirectional JSON-RPC frames during full interoperability suites.

## Measured Evidence
- **Filesystem Server**: Passed discovering `tools/list` and executing `tools/call` for local directory inspection.
- **Memory Server**: Passed standard graph persistence and knowledge extraction commands. Start-up stdio pollution ("Knowledge Graph MCP Server running on stdio") was logged and safely discarded without breaking JSON-RPC parsing.
- **Sequential Thinking Server**: Passed execution of nested reasoning step lists natively.

## Known Limitations
- The AAT suite focused exclusively on `tools/list` and `tools/call`. While `resources/list` and `prompts/list` are syntactically mapped inside `McpTransport`, their behavior was not exhaustively asserted against real-server fixtures in this phase.
- `npx` global installs heavily dictate cold-start timings during interop tests. Network failures during `npx` execution will throw connection timeouts.

## Certification Status
**GO.** The platform acts as a compliant transparent proxy for real-world Node.js MCP tools without imposing any non-standard constraints.
