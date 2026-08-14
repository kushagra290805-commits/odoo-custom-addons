# Workspace Architecture Audit (Phase 7 Audit Report)

**Date:** July 2026  
**Type:** Strictly Read-Only Architecture Audit  
**Scope:** Workspace & File System Subsystem (`models/workspace.py`, `services/workspace_service.py`, `services/workspace_file_service.py`, `services/git_service.py`, `models/git_runtime.py`)  

---

## Executive Summary

This report analyzes the architecture of the **Nexora Studio Workspace and File System Subsystem**. Our audit confirms a strict **Physical Filesystem Governance Model**: workspaces (`nexora.workspace`) represent directories on the host filesystem (defaulting to `D:\NexoraStudio\workspaces`), and file operations (`nexora.workspace_file_service`) execute directly against disk without storing file blobs in Odoo database tables. Furthermore, runtime services (such as Git and Preview) attach to the **Builder Session** (`nexora.builder_session`), not the workspace model, preserving clear architectural boundaries.

---

## 1. Architectural Roles & Responsibilities

```mermaid
classDiagram
    class BuilderSession {
        +Char session_uuid
        +Selection status
        +Many2one workspace_id
        +One2many runtime_ids
    }
    class Workspace {
        +Char workspace_uuid
        +Char workspace_slug
        +Char workspace_path
        +Selection status
        +Selection health
    }
    class WorkspaceService {
        +_get_workspace_root()
        +create_workspace()
        +archive_workspace()
        +delete_workspace()
    }
    class WorkspaceFileService {
        +get_file_tree(session_id)
        +get_file_content(session_id, path)
        +write_file(session_id, path, content)
        +delete_file(session_id, path)
    }
    class GitService {
        +_run_git(repo_path, cmd)
        +git_init(runtime)
        +git_commit(runtime, msg)
        +git_status(runtime)
    }
    class GitRuntime {
        +Many2one runtime_id
        +Char current_branch
        +Boolean is_dirty
        +One2many commit_ids
    }

    BuilderSession --> Workspace : Links to (1:1)
    BuilderSession --> GitRuntime : Orchestrates via Runtime (1:N)
    WorkspaceService ..> Workspace : Manages Lifecycle & Directory
    WorkspaceFileService ..> Workspace : Executes Physical Disk CRUD
    GitService ..> GitRuntime : Executes Git Subprocess in Workspace Path
```

---

## 2. Core Service Analysis

### 2.1 Workspace Lifecycle (`nexora.workspace` & `nexora.workspace_service`)
- **Physical Provisioning:** When `create_workspace()` is called, `WorkspaceService` resolves the root directory from `ir.config_parameter` (`nexora.workspace_root`, defaulting to `D:\NexoraStudio\workspaces`). It creates a physical folder named after `workspace_slug` or `workspace_uuid`, verifying host write permissions.
- **Orchestration Rule:** The docstrings in `models/workspace.py` explicitly mandate: *"Workspace ONLY represents the local filesystem state. It does NOT orchestrate other runtimes. Runtimes attach to Builder Session, NOT Workspace."*

### 2.2 Filesystem CRUD (`nexora.workspace_file_service`)
- **Pure Disk Execution:** Unlike systems that virtualize file storage in SQL databases, `WorkspaceFileService` executes standard Python OS/path operations (`os.scandir`, `os.path.exists`, `open(..., 'w')`) directly against `workspace.workspace_path`.
- **Directory Tree Filtering:** When building file trees via `get_file_tree()`, the service automatically filters out noisy system and build folders: `.git`, `node_modules`, `__pycache__`, `dist`, `build`, and `.odoo`.
- **Safety Constraints:** Enforces a hard file size ceiling (`MAX_FILE_SIZE = 10 * 1024 * 1024` / 10MB) to prevent memory exhaustion during read/write operations.

### 2.3 Git Runtime & Source Control (`nexora.git_service` & `nexora.git_runtime`)
- **Subprocess Integration:** `GitService._run_git()` executes host Git CLI commands (`git status`, `git commit`, `git branch`, `git diff`) via `subprocess.run(...)` inside the workspace directory.
- **State Synchronization:** `GitRuntime` records track repository state in Odoo (branch name, commit SHA, dirty status, commits ahead/behind), synchronized by `GitService._sync_state_to_db()` after every Git operation.

---

## 3. Concurrency & Safety Audit

| Risk Area | Current Architectural Handling | Identified Vulnerability / Gap | Recommended Future Remediation |
| :--- | :--- | :--- | :--- |
| **File Lock Contention**| None in `WorkspaceFileService`. | Simultaneous disk writes from parallel Odoo HTTP requests or background generation workers can corrupt files or cause race conditions. | Implement a file locking or mutex mechanism in `WorkspaceFileService` during write/delete operations. |
| **Path Traversal (LFI)**| Relies on `os.path.relpath` and basic string checks. | Need strict boundary enforcement to ensure `file_path` arguments cannot traverse above `workspace.workspace_path` via `../`. | Ensure `os.path.abspath()` is validated against `os.path.commonpath()` for every file access. |
| **Subprocess Deadlocks**| `subprocess.run(..., capture_output=True, text=True, check=raise_on_error)`. | Commands without explicit timeouts can hang indefinitely if Git prompts for credentials or SSH host key verification. | Add `timeout=30` (or appropriate threshold) to all `subprocess.run()` invocations in `GitService`. |
