# Penpot Capability Matrix (Phase 11B)

This document provides an exhaustive mapping of every method defined in the abstract `DesignProvider` interface to its support status, corresponding Penpot RPC endpoint, and implementation status in `PenpotDesignProvider`.

In accordance with Phase 11B architectural rules: **No invented mutation payloads are permitted.** If an intra-file mutation requires an undocumented `update-file` changeset schema, it is classified as *Unsupported* and raises a descriptive `NotImplementedError` rather than implementing a brittle workaround.

---

## Capability Mapping Table

| Method Name | Status | Penpot RPC Endpoint | Implementation Status | Notes / Limitations |
| :--- | :--- | :--- | :--- | :--- |
| `authenticate` | **Supported** | `/api/rpc/command/get-profile` | Implemented | Uses `PenpotAuthenticator` abstraction (PAT / Session IDs) and validates against live profile endpoint. |
| `create_workspace` | **Supported** | `/api/rpc/command/create-team` | Implemented | Maps directly to Penpot team creation (`name`, optional `description`). |
| `list_projects` | **Supported** | `/api/rpc/command/get-projects`<br>`/api/rpc/command/get-teams` | Implemented | Lists projects by team/workspace ID, or aggregates projects across all accessible teams. |
| `create_project` | **Supported** | `/api/rpc/command/create-project` | Implemented | Requires `workspace_id` (team-id) in metadata; auto-resolves default team if omitted. |
| `get_project` | **Supported** | `/api/rpc/command/get-project` | Implemented | Retrieves project metadata and file structure from live server. |
| `export_svg` | **Supported** | `/api/rpc/command/export-binfile` | Implemented | Calls binary export with `:format "svg"`. Parses `file_id:object_id` or options. |
| `export_png` | **Supported** | `/api/rpc/command/export-binfile` | Implemented | Calls binary export with `:format "png"`. Returns raw binary bytes or decoded content. |
| `export_pdf` | **Supported** | `/api/rpc/command/export-binfile` | Implemented | Calls binary export with `:format "pdf"`. Returns raw binary bytes. |
| `export_assets` | **Supported** | `/api/rpc/command/export-binfile` | Implemented | Batch executes `export_svg`/`export_png`/`export_pdf` across multiple node IDs. |
| `validate_design` | **Supported** | `/api/rpc/command/get-project`<br>`/api/rpc/command/get-file` | Implemented | Retrieves project/file hierarchy and verifies structure against accessibility rules. |
| `create_page` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Requires undocumented `changes` changeset schema. Raises `NotImplementedError`. |
| `create_frame` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Requires undocumented frame insertion schema. Raises `NotImplementedError`. |
| `create_component` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Requires undocumented component tree schema. Raises `NotImplementedError`. |
| `update_component` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Requires undocumented component mutation schema. Raises `NotImplementedError`. |
| `delete_component` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Requires undocumented node deletion schema. Raises `NotImplementedError`. |
| `create_design_tokens` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Token metadata mutation schema is not publicly stable. Raises `NotImplementedError`. |
| `apply_theme` | **Unsupported** | `/api/rpc/command/update-file` (undocumented) | Explicit Limitation | Theme application changeset schema is unsupported. Raises `NotImplementedError`. |
| `import_assets` | **Unsupported** | `/api/rpc/command/upload-file` / multipart | Explicit Limitation | Media upload requires multipart schema not supported in basic RPC. Raises `NotImplementedError`. |
| `sync_project` | **Unsupported** | N/A (Bidirectional Sync) | Explicit Limitation | Bidirectional token sync requires granular mutation support. Raises `NotImplementedError`. |

---

## Architectural Rationale for Explicit Limitations

In Penpot's architecture, structural entities like **Pages**, **Frames**, **Components**, and **Design Tokens** do not exist as standalone, top-level database resources accessible via CRUD REST endpoints. Instead, they are embedded inside a unified **Penpot File Document** (Clojure data tree).

Modifying these internal nodes requires sending an RPC call to `/api/rpc/command/update-file` containing a complex changeset array (`changes`), revision number (`revn`), and session concurrency control data. Because this changeset schema is internal to the frontend-backend synchronization engine and is not documented in stable API specifications, implementing it would require reverse-engineering frontend JavaScript bundles.

Following the project's mandate — **"If a capability is unavailable through supported interfaces, report it explicitly instead of implementing a brittle workaround"** — all 9 granular intra-file mutation methods raise a clear, descriptive `NotImplementedError` explaining this boundary.
