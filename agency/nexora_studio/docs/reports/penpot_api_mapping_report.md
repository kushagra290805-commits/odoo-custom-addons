# Penpot API Mapping Report (Phase 11B)

This technical report details the exact protocol specifications, request/response schemas, and parameter mappings between the vendor-neutral `DesignProvider` interface and Penpot's internal RPC-style HTTP API.

---

## 1. Protocol Specifications

- **Endpoint Structure**: `POST {base_url}/api/rpc/command/{command-name}`
- **Headers Required**:
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `Authorization: Token <pat_token>` (or `Cookie: penpot-session=<session_id>`)
- **Error Handling**: Penpot returns standard HTTP status codes (400 for validation errors, 401 for unauthenticated requests, 404 for missing commands/resources, 500/503 for server errors) alongside JSON error payloads (`{"type": "...", "code": "...", "explain": "..."}`).

---

## 2. Endpoint Mapping Details

### 2.1 Authentication & Health Validation
- **Interface Method**: `authenticate(credentials)` / `client.validate_connection()`
- **Penpot RPC Command**: `get-profile`
- **HTTP Method**: `POST /api/rpc/command/get-profile`
- **Request Payload**: `{}`
- **Response Payload (200 OK)**:
  ```json
  {
    "id": "uuid-here",
    "fullname": "User Name",
    "email": "user@example.com"
  }
  ```
- **Mapping Logic**: If HTTP status is 200 and `"id"` is present in the response dictionary (and not anonymous), authentication is marked successful.

---

### 2.2 Workspace Creation
- **Interface Method**: `create_workspace(name, config)`
- **Penpot RPC Command**: `create-team`
- **HTTP Method**: `POST /api/rpc/command/create-team`
- **Request Payload**:
  ```json
  {
    "name": "Workspace Name",
    "description": "Optional description"
  }
  ```
- **Response Payload (200 OK)**: Returns created team dictionary including `"id"` and `"name"`.

---

### 2.3 Project Listing
- **Interface Method**: `list_projects(workspace_id)`
- **Penpot RPC Commands**: `get-projects` / `get-teams`
- **Mapping Logic**:
  - If `workspace_id` is supplied, sends `POST /api/rpc/command/get-projects` with payload `{"team-id": workspace_id}`.
  - If `workspace_id` is `None`, sends `POST /api/rpc/command/get-teams` with payload `{}`, iterates across all returned teams, and aggregates the results of `get-projects` for each team ID.

---

### 2.4 Project Creation
- **Interface Method**: `create_project(name, metadata)`
- **Penpot RPC Command**: `create-project`
- **Request Payload**:
  ```json
  {
    "name": "Project Name",
    "team-id": "uuid-of-workspace-or-team"
  }
  ```
- **Mapping Logic**: Extracts `workspace_id` or `team_id` from `metadata`. If omitted, automatically queries `get-teams` and uses the default/first team ID.

---

### 2.5 Project Retrieval
- **Interface Method**: `get_project(project_id)`
- **Penpot RPC Command**: `get-project`
- **Request Payload**: `{"id": "project-uuid"}`
- **Response Payload (200 OK)**: Returns project metadata dictionary containing name, team ID, and file list.

---

### 2.6 Binary Asset Exports (`export_svg`, `export_png`, `export_pdf`, `export_assets`)
- **Interface Methods**: `export_svg(node_id, options)`, `export_png(node_id, options)`, `export_pdf(node_id, options)`
- **Penpot RPC Command**: `export-binfile`
- **Request Payload**:
  ```json
  {
    "file-id": "file-uuid",
    "object-id": "node-uuid",
    "format": "svg|png|pdf"
  }
  ```
- **ID Resolution Logic**: The provider checks if `node_id` is formatted as `"file_id:object_id"` or `"file_id/object_id"`. If not, it extracts `"file_id"` from the optional `options` dictionary.
- **Response Handling**:
  - For SVG: Decodes binary response or extracts string from JSON `"content"` field.
  - For PNG/PDF: Returns raw binary bytes.

---

## 3. Unsupported Granular Mutations (Boundary Definition)

The following methods map to Penpot's internal file mutation engine (`/api/rpc/command/update-file` or `upload-file`):
- `create_page`, `create_frame`, `create_component`, `update_component`, `delete_component`, `create_design_tokens`, `apply_theme`, `import_assets`, `sync_project`.

Because the changeset schema required by `update-file` (involving internal Clojure keyword maps and session revision concurrency vectors) is not part of Penpot's documented, stable API, any attempt to construct payloads would constitute brittle reverse-engineering. These methods raise `NotImplementedError` with documented rationale.
