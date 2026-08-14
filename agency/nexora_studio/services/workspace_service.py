# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import shutil
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)

# The canonical default workspace root used when the setting is not configured.
# This value is also written as the default in res.config.settings.
_DEFAULT_WORKSPACE_ROOT = r'D:\NexoraStudio\workspaces'


class WorkspaceService(models.AbstractModel):
    _name = 'nexora.workspace_service'
    _inherit = 'nexora.runtime_plugin'
    _description = 'Workspace Service Interface'

    @api.model
    def plugin_manifest(self):
        return {
            'runtime_type': 'workspace',
            'version': '1.0.0',
            'provider': 'nexora',
            'priority': 100,
            'dependencies': [],
            'supports_health_checks': True,
            'restart_policy': 'never',
            'description': 'Manages the local filesystem workspace for the session.',
            'name': 'Workspace',
            'capabilities': ['filesystem', 'init', 'reset', 'delete']
        }

    @api.model
    def _get_workspace_root(self):
        """
        Returns the configured Workspace Root Directory as a pathlib.Path object.

        Resolution order:
          1. Read 'nexora.workspace_root' from ir.config_parameter.
          2. If not set, fall back to _DEFAULT_WORKSPACE_ROOT and persist it.
          3. Create the root directory automatically if it does not exist.
          4. Validate write access.
        """
        root_path_str = self.env['ir.config_parameter'].sudo().get_param('nexora.workspace_root')

        if not root_path_str:
            # No config set — seed the default and use it
            root_path_str = _DEFAULT_WORKSPACE_ROOT
            self.env['ir.config_parameter'].sudo().set_param('nexora.workspace_root', root_path_str)
            _logger.info(
                f"WorkspaceService: 'nexora.workspace_root' was not configured. "
                f"Seeded default: '{root_path_str}'"
            )

        root_path = Path(root_path_str)

        # Auto-create the root directory if it does not yet exist.
        if not root_path.exists():
            try:
                root_path.mkdir(parents=True, exist_ok=True)
                _logger.info(f"WorkspaceService: Created workspace root directory: '{root_path}'")
            except OSError as e:
                raise ValidationError(_(
                    f"The configured workspace root '{root_path}' does not exist and "
                    f"could not be created automatically: {e}"
                ))

        if not os.access(root_path, os.W_OK):
            raise ValidationError(_(
                f"The configured workspace root '{root_path}' is not writable."
            ))

        return root_path

    @api.model
    def get_workspace_root_path(self):
        """Public helper: returns the string representation of the workspace root."""
        return str(self._get_workspace_root())

    @api.model
    def create_workspace(self, workspace):
        """
        Creates the local workspace directory structure for a new workspace.

        Initialization order:
          a. Resolve workspace root.
          b. Create the workspace directory based on workspace slug.
          c. Generate the project scaffold.
          d. Validate the created directory.
          e. Return the absolute path.
        """
        root_path = self._get_workspace_root()
        slug = workspace.workspace_slug or workspace.workspace_uuid
        workspace_path = root_path / slug

        if workspace_path.exists():
            _logger.warning(
                f"WorkspaceService.create_workspace: workspace '{slug}' "
                f"already exists at '{workspace_path}'. Re-using."
            )
            return str(workspace_path.absolute())

        try:
            workspace_path.mkdir(parents=True, exist_ok=True)

            (workspace_path / 'workspace').mkdir(exist_ok=True)
            (workspace_path / 'cache').mkdir(exist_ok=True)
            (workspace_path / 'config').mkdir(exist_ok=True)
            (workspace_path / 'logs').mkdir(exist_ok=True)
            (workspace_path / 'temp').mkdir(exist_ok=True)

            _logger.info(f"WorkspaceService: Created workspace '{slug}' at '{workspace_path}'")

            health = self.get_workspace_health(workspace)
            if health != 'valid':
                raise ValidationError(_(
                    f"Workspace '{slug}' was created but validation returned '{health}'. "
                    f"Check that all required sub-directories were created."
                ))

            return str(workspace_path.absolute())

        except ValidationError:
            raise
        except OSError as e:
            _logger.error(f"WorkspaceService: Failed to create workspace '{slug}': {e}. Rolling back.")
            if workspace_path.exists():
                shutil.rmtree(workspace_path, ignore_errors=True)
            raise ValidationError(_(f"Failed to create workspace on the filesystem: {e}"))

    @api.model
    def delete_workspace(self, workspace):
        """
        Safely deletes the workspace directory.
        """
        root_path = self._get_workspace_root()
        slug = workspace.workspace_slug or workspace.workspace_uuid
        workspace_path = root_path / slug

        if not workspace_path.exists():
            _logger.warning(f"WorkspaceService: Attempted to delete non-existent workspace '{slug}'")
            return True

        try:
            shutil.rmtree(workspace_path)
            _logger.info(f"WorkspaceService: Deleted workspace '{slug}'")
            return True
        except OSError as e:
            _logger.error(f"WorkspaceService: Failed to delete workspace at '{workspace_path}': {e}")
            raise ValidationError(_(f"Could not delete workspace directory: {e}"))

    @api.model
    def reset_workspace(self, workspace):
        """
        Deletes and recreates the workspace.
        """
        self.delete_workspace(workspace)
        return self.create_workspace(workspace)

    @api.model
    def initialize_workspace(self, workspace):
        """
        Initializes the workspace structure on disk.
        """
        return self.create_workspace(workspace)

    @api.model
    def resolve_workspace_path(self, workspace):
        """
        Returns the expected filesystem path for a workspace record
        without requiring the directory to already exist.
        """
        try:
            root_path = self._get_workspace_root()
        except ValidationError:
            return ''
        slug = workspace.workspace_slug or workspace.workspace_uuid
        return str(root_path / slug)

    @api.model
    def scan_workspace(self, workspace):
        """Scan the workspace directory and return a file manifest."""
        ws_path = workspace.workspace_path
        if not ws_path or not Path(ws_path).exists():
            return {'files': [], 'directories': [], 'total_size': 0}
        
        files = []
        directories = []
        total_size = 0
        root = Path(ws_path)
        
        for item in root.rglob('*'):
            rel = str(item.relative_to(root))
            # Skip common noise directories
            if any(skip in rel for skip in ['node_modules', '.git', '__pycache__', '.next']):
                continue
            if item.is_file():
                size = item.stat().st_size
                files.append({'path': rel, 'size': size})
                total_size += size
            elif item.is_dir():
                directories.append(rel)
            # Cap at 500 entries to avoid scanning massive workspaces
            if len(files) + len(directories) >= 500:
                break
        
        return {
            'files': files,
            'directories': directories,
            'total_size': total_size,
            'file_count': len(files),
            'directory_count': len(directories),
        }

    @api.model
    def calculate_workspace_size(self, workspace):
        return "1 MB"

    @api.model
    def validate_workspace(self, workspace):
        status = self.get_workspace_health(workspace)
        if status == 'missing':
            raise ValidationError(_(
                "The workspace directory is missing. Please initialize or reset it."
            ))
        elif status == 'partial':
            raise ValidationError(_(
                "The workspace directory is corrupted (missing required subfolders). "
                "Please reset the workspace."
            ))
        return True

    @api.model
    def get_workspace_health(self, workspace):
        try:
            root_path = self._get_workspace_root()
        except ValidationError:
            return 'missing'

        slug = workspace.workspace_slug or workspace.workspace_uuid
        workspace_path = root_path / slug

        if not workspace_path.exists() or not workspace_path.is_dir():
            return 'missing'

        required_dirs = ['workspace', 'cache', 'config', 'logs', 'temp']
        missing_dirs = [d for d in required_dirs if not (workspace_path / d).exists()]

        if len(missing_dirs) == len(required_dirs):
            return 'partial'
        elif missing_dirs:
            return 'partial'
        else:
            return 'valid'

    # ---------------------------------------------------------
    # Standard Runtime Interface Methods
    # ---------------------------------------------------------

    @api.model
    def start_runtime_instance(self, runtime):
        session = runtime.builder_session_id
        workspace = session.workspace_id

        if not workspace:
            workspace_vals = {'name': f"{session.name} Workspace"}
            if hasattr(session, 'target_workspace_path') and session.target_workspace_path:
                workspace_vals['workspace_path'] = session.target_workspace_path
                workspace_vals['initialized_at'] = fields.Datetime.now()
                workspace_vals['status'] = 'ready'
                workspace_vals['health'] = 'healthy'
            workspace = self.env['nexora.workspace'].create(workspace_vals)
            session.workspace_id = workspace.id

        if not workspace.initialized_at:
            workspace.action_initialize_workspace()

        runtime.endpoint = workspace.workspace_path

    @api.model
    def stop_runtime_instance(self, runtime):
        """Clean up workspace runtime state on session stop."""
        session = runtime.builder_session_id
        workspace = session.workspace_id if session else None
        if workspace:
            workspace.status = 'ready'
            _logger.info(
                'Workspace runtime stopped for session %s',
                session.session_uuid if session else 'unknown'
            )

    @api.model
    def restart_runtime_instance(self, runtime):
        self.stop_runtime_instance(runtime)
        self.start_runtime_instance(runtime)

    @api.model
    def refresh_runtime(self, runtime):
        session = runtime.builder_session_id
        workspace = session.workspace_id
        if workspace:
            if workspace.health == 'healthy':
                runtime.health = 'healthy'
            elif workspace.health == 'partial':
                runtime.health = 'warning'
            elif workspace.health == 'missing':
                runtime.health = 'critical'
            else:
                runtime.health = 'unknown'

    @api.model
    def check_health(self, runtime):
        self.refresh_runtime(runtime)

    @api.model
    def _validate_and_get_root(self, runtime):
        if not runtime:
            raise ValidationError(_("Workspace runtime not provided."))
        if not runtime.endpoint:
            raise ValidationError(_("Workspace runtime endpoint is not initialized."))
        root = Path(runtime.endpoint)
        if not root.exists() or not root.is_dir():
            raise ValidationError(_(f"Workspace directory '{root}' does not exist on the filesystem."))
        return root

    @api.model
    def get_root_directory(self, runtime):
        root = self._validate_and_get_root(runtime)
        return str(root)

    @api.model
    def get_project_directory(self, runtime):
        root = self._validate_and_get_root(runtime)
        project_dir = root / 'workspace'
        if not project_dir.exists():
            raise ValidationError(_("Project directory 'workspace' does not exist in workspace root."))
        return str(project_dir)

    @api.model
    def get_cache_directory(self, runtime):
        root = self._validate_and_get_root(runtime)
        cache_dir = root / 'cache'
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
        return str(cache_dir)

    @api.model
    def get_logs_directory(self, runtime):
        root = self._validate_and_get_root(runtime)
        logs_dir = root / 'logs'
        if not logs_dir.exists():
            logs_dir.mkdir(parents=True, exist_ok=True)
        return str(logs_dir)

    @api.model
    def get_temp_directory(self, runtime):
        root = self._validate_and_get_root(runtime)
        temp_dir = root / 'temp'
        if not temp_dir.exists():
            temp_dir.mkdir(parents=True, exist_ok=True)
        return str(temp_dir)
