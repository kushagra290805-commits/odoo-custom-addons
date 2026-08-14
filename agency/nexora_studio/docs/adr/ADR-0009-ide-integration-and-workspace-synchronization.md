# ADR-0009 — IDE Integration & Builder Workspace Synchronization

**Status**: Accepted  
**Date**: 2026-07-13  
**Supersedes**: Initial Phase 6G implementation plan (Rejected: introduced dedicated `nexora.ide_runtime` model violating the Runtime Plugin Architecture)

---

## Context

Phase 6G introduces the Antigravity IDE as a first-class participant in the Builder Session lifecycle. The naive approach of introducing a dedicated `nexora.ide_runtime` ORM model was rejected because it would:

- Duplicate lifecycle state that already lives in `nexora.runtime` (status, health, process_id, started_at, stopped_at, last_activity).
- Require `BuilderSessionService` and `RuntimeService` to acquire knowledge of an IDE-specific model, violating the zero-hardcoding constraint established in ADR-0004, ADR-0005, and ADR-0008.
- Break the ownership hierarchy: `BuilderSession → nexora.runtime → RuntimePlugin`.

The correct approach is to register the IDE as another **Runtime Capability** using exactly the same mechanism used by `Workspace`, `Git`, and `Preview`.

---

## Decision

### 1. IDE as a Runtime Capability (Not a Separate ORM Model)

The IDE is represented exclusively through **`nexora.runtime`** records — the same universal runtime record used by every other capability. No new ORM model is introduced.

Lifecycle state (`status`, `health`, `process_id`, `started_at`, `stopped_at`, `last_activity`, `endpoint`) comes entirely from `nexora.runtime`. The only IDE-specific state that must persist beyond the generic runtime fields is stored in `nexora.runtime.metadata_json` as a structured JSON blob.

**Prohibited**: Introducing any model named `nexora.ide_runtime`, `nexora.ide_session`, or any derivative thereof. Such models duplicate lifecycle state and violate this ADR.

### 2. Runtime Capability Registry Entry

`nexora.ide_service` registers into `nexora.runtime_capability` via `synchronize_runtime_capabilities()`:

| Field | Value |
|---|---|
| `runtime_type` | `'ide'` |
| `startup_priority` | `175` |
| `dependencies` | `['workspace', 'git']` |
| `plugin_service` | `'nexora.ide_service'` |
| `supports_health_checks` | `True` |
| `restart_policy` | `'on_failure'` |

This causes Kahn's topological sorting algorithm to automatically generate the dependency order:

**Startup**: `Workspace (100) → Git (150) → IDE (175) → Preview (200)`  
**Shutdown (reverse)**: `Preview → IDE → Git → Workspace`

No ordering is hardcoded in `BuilderSessionService` or `RuntimeService`. All ordering is derived dynamically from the registry.

### 3. IDE Launcher Abstraction (`nexora.ide_launcher`)

Mirrors the `nexora.preview_launcher` pattern established in ADR-0007.

`nexora.ide_launcher` is an abstract `AbstractModel` defining the **IDE Launcher Contract**:

```python
class IDELauncher(models.AbstractModel):
    _name = 'nexora.ide_launcher'

    def launcher_manifest(self) -> dict: ...
    def detect(self, workspace_path: str) -> bool | int: ...
    def validate(self, workspace_path: str) -> dict: ...
    def launch(self, workspace_path: str, session_context: dict, runtime) -> dict: ...
    def stop(self, runtime) -> bool: ...
    def restart(self, workspace_path: str, session_context: dict, runtime) -> dict: ...
    def health(self, runtime) -> str: ...
    def reattach(self, pid: int, workspace_path: str) -> bool: ...
    def cleanup(self, owned_pids: set = None) -> list: ...
    def get_runtime_info(self, runtime) -> dict: ...
```

`launcher_manifest()` must return:
```python
{
    'launcher_id': str,         # e.g., 'antigravity', 'vscode', 'cursor'
    'display_name': str,        # e.g., 'Antigravity IDE'
    'priority': int,            # Detection priority (higher wins)
    'supported_platforms': list,
    'dependency_requirements': list,
    'description': str,
    'version': str,
    'provider': str
}
```

### 4. Antigravity IDE Launcher (`nexora.ide_launcher_antigravity`)

The first concrete implementation. Discovers the Antigravity IDE process, attaches the workspace path and session context, and monitors process health.

Since Antigravity is an external process managed by the IDE application itself (not spawned by Odoo), the launcher's role is:
- **Attach**: Record the active Antigravity process PID and open workspace path in `nexora.runtime.metadata_json`.
- **Monitor**: Verify the process is alive via `psutil` or `os.kill(pid, 0)`.
- **Detach**: Clear the PID and workspace mapping on stop.
- **Recover**: On Odoo restart, scan for active IDE processes matching the stored PID and workspace path.

Future IDE launchers (`VS Code`, `Cursor`, `Windsurf`, `Zed`) follow the identical contract. No changes to `IDEService` or `BuilderSessionService` are required.

### 5. IDE Service (`nexora.ide_service`) — Runtime Plugin

`nexora.ide_service` implements the full `nexora.runtime_plugin` lifecycle contract:

```
start_runtime_instance(runtime)    → detect launcher → validate → launch → update runtime
stop_runtime_instance(runtime)     → resolve launcher → stop → update runtime
restart_runtime_instance(runtime)  → stop → start
recover_runtime_instance(runtime)  → resolve launcher → reattach → update runtime
check_health(runtime)              → resolve launcher → health() → update runtime
refresh_runtime(runtime)           → check_health()
```

Dynamic launcher discovery mirrors `PreviewService.get_all_launchers()`:
1. Walk `env.registry.models` to find all subclasses of `nexora.ide_launcher`.
2. Score each via `launcher.detect(workspace_path)`.
3. Select the highest-scoring launcher.
4. No `if antigravity / if vscode / if cursor` conditionals. Selection is entirely metadata-driven.

Public convenience API (delegates to runtime lifecycle):
```python
start_ide(session)
stop_ide(session)
restart_ide(session)
attach_workspace(session, workspace_path)
detach_workspace(session)
get_ide_status(session)
```

### 6. Runtime Event Emission

`IDEService` emits lifecycle events through the established `nexora.runtime_event` mechanism (via `BuilderSessionService._emit_event`). The event type selection is extended with:

```
'ATTACHED' — Workspace attached to IDE
'DETACHED' — Workspace detached from IDE
```

Existing `STARTED`, `STOPPED`, `FAILED`, `RECOVERED`, `HEALTHY` events apply normally.

### 7. Preview Service Dependency Update

`PreviewService.plugin_manifest()` updates its dependency list from `['workspace']` to `['workspace', 'ide']`. This ensures that:
- Kahn's algorithm places Preview **after** IDE in the startup order.
- If the IDE runtime fails to start, Preview is automatically aborted and marked `stopped`.

### 8. Runtime Type Extension

`nexora.runtime.runtime_type` Selection field is extended with `('ide', 'IDE')`.

---

## Ownership Hierarchy (Mandatory)

```
Builder Session
       │
       ▼
nexora.runtime  (runtime_type='ide')
       │
       ▼
IDEService (nexora.ide_service)
  ─ RuntimePlugin lifecycle methods
       │
       ▼
IDE Launcher Discovery (dynamic, score-based)
       │
       ▼
nexora.ide_launcher_antigravity  (first implementation)
```

The `Workspace` is only an **input resource** passed to the IDE launcher as `workspace_path`. It is not a parent in the ownership tree.

---

## Consequences

**Positive:**
- Zero duplicate lifecycle state. All status, health, and process tracking lives in `nexora.runtime`.
- `BuilderSessionService` and `RuntimeService` require **zero modifications**. The IDE runtime is discovered and orchestrated identically to every other runtime capability.
- Adding `VS Code`, `Cursor`, `Windsurf`, or `Zed` requires only creating a new `nexora.ide_launcher_<name>` AbstractModel. No architectural changes.
- The dependency graph (`Workspace → Git → IDE → Preview`) is computed automatically by Kahn's algorithm from the capability registry. No hardcoding.

**Negative:**
- IDE-specific metadata (workspace path, attachment status, PID) is stored in `nexora.runtime.metadata_json` rather than typed ORM fields, requiring JSON serialization and careful null-handling. This is acceptable given the constraint against dedicated models.

---

## Architectural Constraints (Mandatory Compliance)

| Constraint | Rationale |
|---|---|
| **No `nexora.ide_runtime` model or derivatives** | Duplicate lifecycle state |
| **No `if antigravity / if vscode / if cursor` conditionals in IDEService** | Metadata-driven selection only |
| **No hardcoded ordering in BuilderSessionService or RuntimeService** | Topological sort from registry |
| **All IDE lifecycle events must pass through `nexora.runtime_event`** | Consistent audit trail |
| **Future IDE launchers must implement `nexora.ide_launcher` contract** | Plugin architecture integrity |
