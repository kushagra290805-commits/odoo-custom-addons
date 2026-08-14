# MCP Interoperability Matrix

| Server | MCP SDK Version | Protocol Features Exercised | Discovery Result | Execution Result | Resources / Prompts | Known Limitations |
|--------|----------------|-----------------------------|------------------|------------------|---------------------|-------------------|
| `@modelcontextprotocol/server-filesystem` | official Python `mcp` SDK v1.1.2 | `tools/list`, `tools/call` | ✅ Passed | ✅ Passed | Not explicitly tested in AAT | None |
| `@modelcontextprotocol/server-memory` | official Python `mcp` SDK v1.1.2 | `tools/list`, `tools/call` | ✅ Passed | ✅ Passed | N/A | Prints non-JSON startup messages to stdout which are gracefully ignored by Python `mcp` SDK. |
| `@modelcontextprotocol/server-sequential-thinking` | official Python `mcp` SDK v1.1.2 | `tools/list`, `tools/call` | ✅ Passed | ✅ Passed | N/A | None |

*Note: This matrix represents only servers actively verified with full JSON-RPC trace capture in the AAT regression suite. It does not claim universal compatibility with all MCP servers.*
