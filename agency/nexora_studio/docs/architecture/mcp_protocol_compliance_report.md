# MCP Protocol Compliance Report

## Overview
This report verifies that the MCP Connector correctly processes and normalizes standard JSON-RPC payloads according to the Model Context Protocol specifications (v2025-11-25) at the connector boundaries. 

## Verified Facts
- **Transport Mechanism**: `mcp.client.stdio` transport handles standard input/output streaming without altering raw JSON-RPC structures.
- **Protocol Regression Fixtures**: Executable deterministic fixtures are stored in `scratch/aat_suite/mcp/fixtures/` covering success, failure, and malformed scenarios.
- **Payload Parsing**: Upstream SDK `pydantic` parsers validate structural integrity of messages (e.g., `JSONRPCMessage`, `CallToolResult`). Our `McpTransport` and `ConnectorDispatcher` accurately map upstream exceptions (like `pydantic_core._pydantic_core.ValidationError` and `-32600 Invalid Request`) into the internal `ConnectorExecutionResult` taxonomy (`CONNECTOR_EXECUTION_ERROR`).

## Measured Evidence
- ✅ `tools_list_success`: The `tools/list` RPC correctly extracts `tools` array matching schema definitions.
- ✅ `tools_call_success`: The `tools/call` RPC parses nested list content strictly formatted as `TextContent`, `ImageContent`, or `EmbeddedResource`.
- ✅ `protocol_error`: Raw JSON-RPC `error` objects are reliably unpacked into `error` properties and wrapped in `CONNECTOR_EXECUTION_ERROR`.
- ✅ `malformed_response`: Responses omitting required `content` fields are trapped at the transport boundary without corrupting internal dispatcher cache state.

## Known Limitations
- The underlying `mcp` SDK silently discards non-JSON lines printed to standard output before valid JSON-RPC frames. While resilient, this obscures verbose debug logging emitted by some servers before `initialize`.

## Certification Status
**GO.** JSON-RPC structure parsing operates robustly at our boundary without duplicating downstream parsing layers.
