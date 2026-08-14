# -*- coding: utf-8 -*-
import os
from odoo import models, api, _
from odoo.exceptions import UserError

class WorkspaceFileService(models.AbstractModel):
    _name = 'nexora.workspace_file_service'
    _description = 'Workspace File System Service'

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

    @api.model
    def _get_workspace_path(self, session_id):
        session = self.env['nexora.builder_session'].browse(session_id)
        if not session.exists():
            raise UserError(_("Session not found."))
        
        workspace = session.workspace_id
        if not workspace:
            raise UserError(_("No workspace linked to this session."))
            
        if workspace.status != 'ready' or not workspace.workspace_path:
            raise UserError(_("Workspace is not ready or path is missing."))
            
        path = workspace.workspace_path
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception:
                raise UserError(_("Workspace directory could not be created."))
            
        return workspace.workspace_path

    @api.model
    def get_file_tree(self, session_id):
        try:
            base_path = self._get_workspace_path(session_id)
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

        def _build_tree(dir_path, relative_to):
            tree = []
            try:
                for entry in os.scandir(dir_path):
                    if entry.name in ('.git', 'node_modules', '__pycache__', 'dist', 'build', '.odoo'):
                        continue
                    
                    rel_path = os.path.relpath(entry.path, relative_to)
                    # Convert Windows backslashes to forward slashes for DTO
                    rel_path = rel_path.replace('\\', '/')
                    
                    try:
                        stat = entry.stat()
                        size = stat.st_size if entry.is_file() else 0
                        modified = int(stat.st_mtime * 1000)
                    except OSError:
                        size = 0
                        modified = 0

                    node = {
                        'id': rel_path,
                        'name': entry.name,
                        'path': rel_path,
                        'type': 'folder' if entry.is_dir() else 'file',
                        'size': size,
                        'modifiedAt': modified
                    }
                    if entry.is_dir():
                        node['children'] = _build_tree(entry.path, relative_to)
                    tree.append(node)
            except PermissionError:
                pass
            
            return sorted(tree, key=lambda x: (x['type'] == 'file', x['name'].lower()))

        tree = _build_tree(base_path, base_path)
        return {'status': 'success', 'data': tree}

    @api.model
    def get_file_content(self, session_id, file_path):
        try:
            base_path = self._get_workspace_path(session_id)
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

        full_path = os.path.abspath(os.path.join(base_path, file_path.replace('/', os.sep)))
        
        # Prevent path traversal
        if not full_path.startswith(os.path.abspath(base_path)):
            return {'status': 'error', 'error': 'Permission Denied: Path traversal detected'}

        if not os.path.exists(full_path):
            return {'status': 'error', 'error': 'File not found'}

        if not os.path.isfile(full_path):
            return {'status': 'error', 'error': 'Path is not a file'}

        size = os.path.getsize(full_path)
        if size > self.MAX_FILE_SIZE:
            return {'status': 'error', 'error': 'File exceeds maximum size limit of 10MB'}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                'status': 'success',
                'data': {
                    'path': file_path,
                    'content': content,
                    'size': size,
                    'readonly': False
                }
            }
        except UnicodeDecodeError:
            return {'status': 'error', 'error': 'Unsupported encoding or binary file'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def save_file(self, session_id, file_path, content):
        try:
            base_path = self._get_workspace_path(session_id)
            full_path = os.path.abspath(os.path.join(base_path, file_path.replace('/', os.sep)))
            if not full_path.startswith(os.path.abspath(base_path)):
                return {'status': 'error', 'error': 'Permission Denied: Path traversal detected'}

            if os.path.exists(full_path) and not os.path.isfile(full_path):
                return {'status': 'error', 'error': 'Cannot overwrite a directory with a file'}
            
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'file.saved', f"File saved: {file_path}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def create_file(self, session_id, file_path):
        try:
            base_path = self._get_workspace_path(session_id)
            full_path = os.path.abspath(os.path.join(base_path, file_path.replace('/', os.sep)))
            if not full_path.startswith(os.path.abspath(base_path)):
                return {'status': 'error', 'error': 'Permission Denied: Path traversal detected'}

            if os.path.exists(full_path):
                return {'status': 'error', 'error': 'File already exists'}
            
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write('')
                
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'file.created', f"File created: {file_path}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def create_folder(self, session_id, folder_path):
        try:
            base_path = self._get_workspace_path(session_id)
            full_path = os.path.abspath(os.path.join(base_path, folder_path.replace('/', os.sep)))
            if not full_path.startswith(os.path.abspath(base_path)):
                return {'status': 'error', 'error': 'Permission Denied: Path traversal detected'}

            if os.path.exists(full_path):
                return {'status': 'error', 'error': 'Folder already exists'}
            
            os.makedirs(full_path, exist_ok=True)
                
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'folder.created', f"Folder created: {folder_path}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def delete_node(self, session_id, node_path):
        try:
            import shutil
            base_path = self._get_workspace_path(session_id)
            full_path = os.path.abspath(os.path.join(base_path, node_path.replace('/', os.sep)))
            if not full_path.startswith(os.path.abspath(base_path)):
                return {'status': 'error', 'error': 'Permission Denied: Path traversal detected'}
                
            if full_path == os.path.abspath(base_path):
                return {'status': 'error', 'error': 'Cannot delete workspace root'}

            if not os.path.exists(full_path):
                return {'status': 'error', 'error': 'Not found'}
            
            is_folder = os.path.isdir(full_path)
            if is_folder:
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
                
            session = self.env['nexora.builder_session'].browse(session_id)
            event_type = 'folder.deleted' if is_folder else 'file.deleted'
            self.env['nexora.builder_session_service']._emit_event(
                session, event_type, f"Deleted: {node_path}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def rename_node(self, session_id, old_path, new_path):
        try:
            base_path = self._get_workspace_path(session_id)
            old_full = os.path.abspath(os.path.join(base_path, old_path.replace('/', os.sep)))
            new_full = os.path.abspath(os.path.join(base_path, new_path.replace('/', os.sep)))
            
            if not old_full.startswith(os.path.abspath(base_path)) or not new_full.startswith(os.path.abspath(base_path)):
                return {'status': 'error', 'error': 'Permission Denied: Path traversal detected'}
                
            if old_full == os.path.abspath(base_path):
                return {'status': 'error', 'error': 'Cannot rename workspace root'}

            if not os.path.exists(old_full):
                return {'status': 'error', 'error': 'Source not found'}
                
            if os.path.exists(new_full):
                return {'status': 'error', 'error': 'Destination already exists'}
            
            is_folder = os.path.isdir(old_full)
            os.rename(old_full, new_full)
                
            session = self.env['nexora.builder_session'].browse(session_id)
            event_type = 'folder.renamed' if is_folder else 'file.renamed'
            self.env['nexora.builder_session_service']._emit_event(
                session, event_type, f"Renamed: {old_path} -> {new_path}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
