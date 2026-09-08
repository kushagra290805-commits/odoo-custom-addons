# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import subprocess
import os
import json
import shutil
import time

_logger = logging.getLogger(__name__)

class DependencyInstallerService(models.AbstractModel):
    _name = 'nexora.dependency_installer_service'
    _description = 'Canonical Dependency Installer Service'

    # ------------------------------------------------------------------
    # Phase 47.11 (U9.2): project-wide install + production build.
    #
    # These extend the canonical dependency-install owner so a generated
    # project can install its complete package.json dependency graph and run
    # its own authoritative production build. Command execution is delegated
    # to the canonical nexora.execution_sandbox_service boundary (never raw
    # subprocess here), and only ever runs inside the managed workspace.
    # install_node()/install_git()/install_python() are unchanged.
    # ------------------------------------------------------------------

    @api.model
    def _npm_executable(self):
        for candidate in ('npm.cmd', 'npm.exe', 'npm'):
            path = shutil.which(candidate)
            if path:
                return path
        return None

    @api.model
    def _sandbox(self):
        return self.env['nexora.execution_sandbox_service']

    @api.model
    def _read_package_json(self, workspace_path):
        pkg_path = os.path.join(workspace_path, 'package.json')
        if not os.path.isfile(pkg_path):
            return None
        try:
            with open(pkg_path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return None

    @api.model
    def install_project(self, workspace_path):
        """Install the complete dependency graph of a generated project.

        Runs ``npm install`` (no added packages, no global install) inside the
        managed workspace through the canonical sandbox. Returns a structured
        result; success is only reported when npm exits zero.
        """
        sandbox = self._sandbox()
        if not workspace_path or not sandbox.is_within_allowed_roots(workspace_path):
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': 'Sandbox violation: install requested outside the managed workspace.',
                'error': 'workspace_not_allowed', 'workspace_path': workspace_path,
            }
        if not os.path.isdir(workspace_path):
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': f'Workspace directory does not exist: {workspace_path}',
                'error': 'workspace_missing', 'workspace_path': workspace_path,
            }
        if self._read_package_json(workspace_path) is None:
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': f'package.json not found in workspace: {workspace_path}',
                'error': 'package_json_missing', 'workspace_path': workspace_path,
            }
        npm = self._npm_executable()
        if not npm:
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': 'npm executable not found in PATH.',
                'error': 'npm_unavailable', 'workspace_path': workspace_path,
            }
        cmd = [npm, 'install', '--no-audit', '--no-fund']
        started = time.time()
        res = sandbox.execute_local(cmd, cwd=workspace_path, timeout=900)
        duration = round(time.time() - started, 2)
        exit_code = res.get('returncode')
        success = bool(res.get('success')) and exit_code == 0
        return {
            'success': success,
            'exit_code': exit_code,
            'stdout': res.get('stdout', '') or '',
            'stderr': res.get('stderr', '') or res.get('error', '') or '',
            'command': 'npm install --no-audit --no-fund',
            'duration_s': duration,
            'workspace_path': workspace_path,
            'error': None if success else (res.get('error') or 'install_failed'),
        }

    @api.model
    def build_project(self, workspace_path):
        """Run the generated project's authoritative production build.

        Executes the project's own ``package.json`` build script via
        ``npm run build`` inside the managed workspace through the canonical
        sandbox. Success requires BOTH a zero exit code AND the presence of the
        expected build output (dist/ or build/); exit code alone is not enough.
        """
        sandbox = self._sandbox()
        if not workspace_path or not sandbox.is_within_allowed_roots(workspace_path):
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': 'Sandbox violation: build requested outside the managed workspace.',
                'error': 'workspace_not_allowed', 'workspace_path': workspace_path,
                'dist_path': None, 'dist_present': False,
            }
        if not os.path.isdir(workspace_path):
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': f'Workspace directory does not exist: {workspace_path}',
                'error': 'workspace_missing', 'workspace_path': workspace_path,
                'dist_path': None, 'dist_present': False,
            }
        pkg = self._read_package_json(workspace_path)
        if pkg is None:
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': f'package.json not found in workspace: {workspace_path}',
                'error': 'package_json_missing', 'workspace_path': workspace_path,
                'dist_path': None, 'dist_present': False,
            }
        build_script = (pkg.get('scripts') or {}).get('build')
        if not build_script:
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': 'package.json defines no authoritative build script.',
                'error': 'build_script_missing', 'workspace_path': workspace_path,
                'dist_path': None, 'dist_present': False,
            }
        npm = self._npm_executable()
        if not npm:
            return {
                'success': False, 'exit_code': None, 'stdout': '', 'command': None,
                'stderr': 'npm executable not found in PATH.',
                'error': 'npm_unavailable', 'workspace_path': workspace_path,
                'dist_path': None, 'dist_present': False,
            }
        cmd = [npm, 'run', 'build']
        started = time.time()
        res = sandbox.execute_local(cmd, cwd=workspace_path, timeout=600)
        duration = round(time.time() - started, 2)
        exit_code = res.get('returncode')
        exit_ok = bool(res.get('success')) and exit_code == 0

        dist_path = None
        for candidate in ('dist', 'build'):
            full = os.path.join(workspace_path, candidate)
            if os.path.isdir(full):
                dist_path = full
                break
        dist_present = dist_path is not None

        success = exit_ok and dist_present
        error = None
        if not success:
            if not exit_ok:
                error = res.get('error') or 'build_failed'
            else:
                error = 'build_output_missing'
        return {
            'success': success,
            'exit_code': exit_code,
            'stdout': res.get('stdout', '') or '',
            'stderr': res.get('stderr', '') or res.get('error', '') or '',
            'command': 'npm run build',
            'build_script': build_script,
            'duration_s': duration,
            'workspace_path': workspace_path,
            'dist_path': dist_path,
            'dist_present': dist_present,
            'error': error,
        }

    @api.model
    def install_git(self, repo_url, target_dir):
        _logger.info(f"Git cloning {repo_url} into {target_dir}")
        if os.path.exists(target_dir) and os.listdir(target_dir):
            _logger.info(f"Target directory {target_dir} already exists and is not empty. Pulling instead.")
            return self._run_command(['git', 'pull'], cwd=target_dir)
        os.makedirs(target_dir, exist_ok=True)
        return self._run_command(['git', 'clone', repo_url, target_dir])

    @api.model
    def install_node(self, package, directory=None, is_global=False):
        cmd = ['npm', 'install']
        if is_global:
            cmd.append('-g')
        cmd.append(package)
        _logger.info(f"Installing NPM package: {' '.join(cmd)}")
        return self._run_command(cmd, cwd=directory)

    @api.model
    def install_python(self, package, directory=None):
        cmd = ['python', '-m', 'pip', 'install', package]
        _logger.info(f"Installing Python package: {' '.join(cmd)}")
        return self._run_command(cmd, cwd=directory)

    def _run_command(self, cmd, cwd=None):
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
            _logger.info(f"Command successful: {' '.join(cmd)}")
            return {'success': True, 'stdout': result.stdout}
        except subprocess.CalledProcessError as e:
            _logger.error(f"Command failed: {e.stderr}")
            return {'success': False, 'error': e.stderr}
