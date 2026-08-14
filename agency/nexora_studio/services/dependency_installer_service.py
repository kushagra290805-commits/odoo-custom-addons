# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import subprocess
import os

_logger = logging.getLogger(__name__)

class DependencyInstallerService(models.AbstractModel):
    _name = 'nexora.dependency_installer_service'
    _description = 'Canonical Dependency Installer Service'

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
