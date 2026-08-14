# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import subprocess
import logging
from pathlib import Path
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)

class GitService(models.AbstractModel):
    _name = 'nexora.git_service'
    _inherit = 'nexora.runtime_plugin'
    _description = 'Git Runtime Service Interface'

    @api.model
    def plugin_manifest(self):
        return {
            'runtime_type': 'git',
            'version': '1.0.0',
            'provider': 'nexora',
            'priority': 150,  # After workspace (100)
            'dependencies': ['workspace'],
            'supports_health_checks': True,
            'restart_policy': 'on_failure',
            'description': 'Manages the source control lifecycle for the session using Git.',
            'name': 'Git Source Control',
            'capabilities': [
                "clone",
                "fetch",
                "pull",
                "push",
                "commit",
                "branch",
                "merge",
                "checkout",
                "history",
                "diff"
            ]
        }
        
    def _run_git(self, repo_path, cmd, raise_on_error=True, require_repo=True):
        """Helper to run a git command via subprocess."""
        if not repo_path:
            raise ValidationError(_("No repository path provided."))
            
        if require_repo:
            if not (Path(repo_path) / '.git').exists():
                raise ValidationError(_("The workspace is not initialized as a Git repository."))
            
        full_cmd = ["git"] + cmd
        try:
            result = subprocess.run(
                full_cmd, 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                check=raise_on_error
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.CalledProcessError as e:
            if raise_on_error:
                _logger.error(f"Git command failed: {' '.join(full_cmd)}\nError: {e.stderr}")
                raise ValidationError(_(f"Git command failed: {e.stderr.strip()}"))
            return e.stdout.strip(), e.stderr.strip(), e.returncode
        except FileNotFoundError:
            raise ValidationError(_("Git executable not found on the host system."))

    @api.model
    def _get_workspace_path(self, runtime):
        """Helper to get physical path from workspace runtime."""
        session = runtime.builder_session_id
            
        if session and session.workspace_id:
            return session.workspace_id.workspace_path
        return session.target_workspace_path
        
    @api.model
    def _sync_state_to_db(self, runtime):
        """Synchronizes git state to Odoo database."""
        repo_path = self._get_workspace_path(runtime)
        git_rt = self.env['nexora.git_runtime'].search([('runtime_id', '=', runtime.id)], limit=1)
        if not git_rt:
            git_rt = self.env['nexora.git_runtime'].create({'runtime_id': runtime.id})
            
        if not (Path(repo_path) / '.git').exists():
            if not self.env.context.get('ignore_missing_git', False):
                raise ValidationError(_("The workspace is not initialized as a Git repository. Please Initialize or Clone a repository first."))
            return git_rt
            
        # Sync branch
        stdout, _err, _code = self._run_git(repo_path, ['branch', '--show-current'], raise_on_error=False)
        git_rt.current_branch = stdout
        
        # Sync commit
        stdout, _err, _code = self._run_git(repo_path, ['rev-parse', 'HEAD'], raise_on_error=False)
        git_rt.current_commit = stdout
        
        # Sync remote URL
        stdout, _err, _code = self._run_git(repo_path, ['config', '--get', 'remote.origin.url'], raise_on_error=False)
        git_rt.repository_url = stdout
        
        # Sync dirty state
        stdout, _err, _code = self._run_git(repo_path, ['status', '--porcelain'], raise_on_error=False)
        git_rt.is_dirty = bool(stdout)
        
        # Ahead / Behind
        if git_rt.current_branch:
            stdout, _err, _code = self._run_git(repo_path, ['rev-list', '--left-right', '--count', f'HEAD...origin/{git_rt.current_branch}'], raise_on_error=False)
            if stdout and '\t' in stdout:
                ahead, behind = stdout.split('\t')
                git_rt.ahead = int(ahead)
                git_rt.behind = int(behind)
                
        # Sync branches
        stdout, _err, _code = self._run_git(repo_path, ['for-each-ref', '--format=%(refname:short) %(upstream:short) %(objectname)', 'refs/heads/'], raise_on_error=False)
        if stdout:
            existing_branches = {b.name: b for b in git_rt.branch_ids}
            branch_lines = stdout.split('\n')
            for line in branch_lines:
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    name, upstream, commit = parts[0], parts[1], parts[2]
                    if name in existing_branches:
                        existing_branches[name].write({'upstream': upstream, 'latest_commit': commit})
                    else:
                        self.env['nexora.git_branch'].create({
                            'git_runtime_id': git_rt.id,
                            'name': name,
                            'upstream': upstream,
                            'latest_commit': commit
                        })
                        
        # Sync recent commits
        limit = runtime.builder_session_id.builder_configuration_id.git_history_sync_limit or 50
        # Format: SHA|Author|Date(Unix)|Message
        stdout, _err, _code = self._run_git(repo_path, ['log', f'-n{limit}', '--pretty=format:%H|%an|%at|%s'], raise_on_error=False)
        if stdout:
            git_rt.commit_ids.unlink() # clear old
            commits_to_create = []
            for line in stdout.split('\n'):
                parts = line.split('|', 3)
                if len(parts) == 4:
                    try:
                        commit_date = datetime.utcfromtimestamp(int(parts[2]))
                    except Exception:
                        commit_date = fields.Datetime.now()
                        
                    commits_to_create.append({
                        'git_runtime_id': git_rt.id,
                        'sha': parts[0],
                        'author': parts[1],
                        'date': commit_date,
                        'message': parts[3]
                    })
            if commits_to_create:
                self.env['nexora.git_commit'].create(commits_to_create)
                
        return git_rt

    # ---------------------------------------------------------
    # Standard Runtime Interface Methods
    # ---------------------------------------------------------

    @api.model
    def start_runtime_instance(self, runtime):
        """
        Starts the Git runtime for the given session.
        """
        try:
            self.with_context(ignore_missing_git=True)._sync_state_to_db(runtime)
            runtime.endpoint = "Git Local"
        except Exception as e:
            raise ValidationError(str(e))

    @api.model
    def stop_runtime_instance(self, runtime):
        """Stops the Git runtime (no-op)."""
        pass

    @api.model
    def restart_runtime_instance(self, runtime):
        self.stop_runtime_instance(runtime)
        self.start_runtime_instance(runtime)

    @api.model
    def refresh_runtime(self, runtime):
        """Refreshes status and health of the Git runtime."""
        self.with_context(ignore_missing_git=True)._sync_state_to_db(runtime)

    @api.model
    def check_health(self, runtime):
        repo_path = self._get_workspace_path(runtime)
        if not (Path(repo_path) / '.git').exists():
            runtime.health = 'partial' # It's just not initialized
            return
            
        stdout, stderr, code = self._run_git(repo_path, ['fsck'], raise_on_error=False)
        if code != 0:
            runtime.health = 'critical'
        else:
            runtime.health = 'healthy'

    # ---------------------------------------------------------
    # Public Git Operations for UI
    # ---------------------------------------------------------
    
    @api.model
    def git_init(self, runtime):
        repo_path = self._get_workspace_path(runtime)
        self._run_git(repo_path, ['init'], require_repo=False)
        self._sync_state_to_db(runtime)
        
    @api.model
    def git_clone(self, runtime, url):
        repo_path = self._get_workspace_path(runtime)
        # Clone into current directory (. requires empty dir)
        self._run_git(repo_path, ['clone', url, '.'], require_repo=False)
        self._sync_state_to_db(runtime)
        
    @api.model
    def git_fetch(self, runtime):
        repo_path = self._get_workspace_path(runtime)
        self._run_git(repo_path, ['fetch', '--all'])
        
        git_rt = self.env['nexora.git_runtime'].search([('runtime_id', '=', runtime.id)], limit=1)
        if git_rt:
            git_rt.last_fetch = fields.Datetime.now()
            
        self._sync_state_to_db(runtime)
        
    @api.model
    def git_pull(self, runtime):
        repo_path = self._get_workspace_path(runtime)
        self._run_git(repo_path, ['pull'])
        
        git_rt = self.env['nexora.git_runtime'].search([('runtime_id', '=', runtime.id)], limit=1)
        if git_rt:
            git_rt.last_pull = fields.Datetime.now()
            
        self._sync_state_to_db(runtime)
        
    @api.model
    def git_push(self, runtime):
        repo_path = self._get_workspace_path(runtime)
        git_rt = self.env['nexora.git_runtime'].search([('runtime_id', '=', runtime.id)], limit=1)
        
        if git_rt and git_rt.current_branch:
            self._run_git(repo_path, ['push', 'origin', git_rt.current_branch])
            git_rt.last_push = fields.Datetime.now()
            
        self._sync_state_to_db(runtime)
        
    @api.model
    def git_commit(self, runtime, message):
        repo_path = self._get_workspace_path(runtime)
        self._run_git(repo_path, ['add', '.'])
        self._run_git(repo_path, ['commit', '-m', message])
        self._sync_state_to_db(runtime)

    # ---------------------------------------------------------
    # Session Level API Methods (For UI / API)
    # ---------------------------------------------------------
    
    @api.model
    def _get_session_repo_path(self, session_id):
        return self.env['nexora.workspace_file_service']._get_workspace_path(session_id)

    @api.model
    def _get_session_runtime(self, session_id):
        session = self.env['nexora.builder_session'].browse(session_id)
        if not session.exists():
            raise ValidationError(_("Session not found"))
        runtime = session.runtime_ids.filtered(lambda r: r.plugin_name == 'git')
        if not runtime:
            raise ValidationError(_("Git runtime not found for session"))
        return runtime[0]

    @api.model
    def init_session_repo(self, session_id):
        try:
            repo_path = self._get_session_repo_path(session_id)
            self._run_git(repo_path, ['init'], require_repo=False)
            
            runtime = self._get_session_runtime(session_id)
            self._sync_state_to_db(runtime)
            
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'git.repository.initialized', "Git repository initialized."
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def get_session_status(self, session_id):
        try:
            repo_path = self._get_session_repo_path(session_id)
            # Porcelain format gives us precise status for each file
            stdout, _err, _code = self._run_git(repo_path, ['status', '--porcelain'], raise_on_error=False, require_repo=False)
            
            if _code == 128: # Not a git repo
                return {'status': 'success', 'data': {'is_repo': False, 'files': []}}
                
            files = []
            if stdout:
                for line in stdout.split('\n'):
                    if len(line) > 3:
                        status = line[0:2]
                        path = line[3:]
                        files.append({'path': path, 'status': status})
                        
            return {'status': 'success', 'data': {'is_repo': True, 'files': files}}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def commit_session(self, session_id, message, files_to_stage=None):
        try:
            repo_path = self._get_session_repo_path(session_id)
            
            if files_to_stage and len(files_to_stage) > 0:
                for f in files_to_stage:
                    self._run_git(repo_path, ['add', f])
            else:
                self._run_git(repo_path, ['add', '.'])
                
            stdout, stderr, code = self._run_git(repo_path, ['commit', '-m', message])
            
            runtime = self._get_session_runtime(session_id)
            self._sync_state_to_db(runtime)
            
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'git.commit.created', f"Committed: {message}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def get_session_history(self, session_id):
        try:
            repo_path = self._get_session_repo_path(session_id)
            stdout, _err, _code = self._run_git(repo_path, ['log', '-n', '50', '--pretty=format:%H|%an|%at|%s'], raise_on_error=False, require_repo=False)
            
            if _code == 128 or _code == 128: # Not a repo or no commits yet
                return {'status': 'success', 'data': []}
                
            commits = []
            if stdout:
                for line in stdout.split('\n'):
                    parts = line.split('|', 3)
                    if len(parts) == 4:
                        commits.append({
                            'hash': parts[0],
                            'author': parts[1],
                            'timestamp': int(parts[2]),
                            'message': parts[3]
                        })
            return {'status': 'success', 'data': commits}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def get_session_branches(self, session_id):
        try:
            repo_path = self._get_session_repo_path(session_id)
            stdout, _err, _code = self._run_git(repo_path, ['branch', '--list'], raise_on_error=False, require_repo=False)
            
            if _code == 128:
                return {'status': 'success', 'data': []}
                
            branches = []
            if stdout:
                for line in stdout.split('\n'):
                    name = line[2:].strip()
                    is_current = line.startswith('*')
                    if name:
                        branches.append({'name': name, 'current': is_current})
            return {'status': 'success', 'data': branches}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def create_session_branch(self, session_id, branch_name):
        try:
            repo_path = self._get_session_repo_path(session_id)
            self._run_git(repo_path, ['branch', branch_name])
            
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'git.branch.created', f"Branch created: {branch_name}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def checkout_session_branch(self, session_id, branch_name):
        try:
            repo_path = self._get_session_repo_path(session_id)
            self._run_git(repo_path, ['checkout', branch_name])
            
            runtime = self._get_session_runtime(session_id)
            self._sync_state_to_db(runtime)
            
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'git.checkout.completed', f"Checked out: {branch_name}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def delete_session_branch(self, session_id, branch_name):
        try:
            repo_path = self._get_session_repo_path(session_id)
            self._run_git(repo_path, ['branch', '-D', branch_name])
            
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'git.branch.deleted', f"Branch deleted: {branch_name}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @api.model
    def restore_session_file(self, session_id, file_path):
        try:
            repo_path = self._get_session_repo_path(session_id)
            self._run_git(repo_path, ['restore', file_path])
            
            session = self.env['nexora.builder_session'].browse(session_id)
            self.env['nexora.builder_session_service']._emit_event(
                session, 'git.restore.completed', f"Restored file: {file_path}"
            )
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
