# -*- coding: utf-8 -*-
"""
Patch Engine — secure pipeline for applying AI-generated code changes.

Pipeline:
  AI Response → Patch Parser → Unified Diff Parser → Syntax Validation
  → Conflict Detection → Safe Application → Git Checkpoint → Audit Log
"""
from odoo import models, api
import os
import re
import subprocess
import json
import logging

_logger = logging.getLogger(__name__)


class PatchEngine(models.AbstractModel):
    _name = 'nexora.patch_engine'
    _description = 'Secure AI Patch Engine'

    @api.model
    def apply(self, workspace_path, ai_response, session_id=None,
              stage_name='', dry_run=False, runtime=None):
        """
        Parse, validate, and apply patches from an AI response.

        Returns
        -------
        dict with keys:
            success : bool
            applied_files : list[str]
            rejected_files : list[str]
            errors : list[str]
            git_commit : str | None
        """
        result = {
            'success': False,
            'applied_files': [],
            'rejected_files': [],
            'errors': [],
            'git_commit': None,
        }

        # 1. Parse patches from AI response
        patches = self._parse_patches(ai_response)
        if not patches:
            # No structured patches found — treat entire response as
            # informational analysis (review stages often just report).
            result['success'] = True
            return result

        src_dir = os.path.join(workspace_path, 'src')
        if not os.path.isdir(src_dir):
            src_dir = workspace_path

        for patch in patches:
            filepath = patch['file']
            content = patch['content']
            action = patch.get('action', 'write')  # write | patch | delete

            abs_path = os.path.join(src_dir, filepath)

            # 2. Security: path traversal check
            # Reject any path containing .. components
            normalized = os.path.normpath(filepath)
            if '..' in normalized.split(os.sep) or '..' in normalized.split('/'):
                result['rejected_files'].append(filepath)
                result['errors'].append(
                    f'Path traversal rejected (.. detected): {filepath}'
                )
                continue
            real_src = os.path.realpath(src_dir)
            real_target = os.path.realpath(abs_path)
            if not real_target.startswith(real_src):
                result['rejected_files'].append(filepath)
                result['errors'].append(
                    f'Path traversal rejected: {filepath}'
                )
                continue

            # 3. Syntax validation
            syntax_ok, syntax_err = self._validate_syntax(filepath, content)
            if not syntax_ok:
                result['rejected_files'].append(filepath)
                result['errors'].append(
                    f'Syntax validation failed for {filepath}: {syntax_err}'
                )
                continue

            # 4. Conflict detection
            if os.path.isfile(abs_path):
                conflict = self._detect_conflict(abs_path, content)
                if conflict:
                    result['rejected_files'].append(filepath)
                    result['errors'].append(
                        f'Conflict detected in {filepath}: {conflict}'
                    )
                    continue

            # 5. Apply
            if not dry_run:
                try:
                    if action == 'delete':
                        if os.path.isfile(abs_path):
                            os.remove(abs_path)
                    else:
                        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                        with open(abs_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    result['applied_files'].append(filepath)
                except Exception as e:
                    result['rejected_files'].append(filepath)
                    result['errors'].append(f'Write failed for {filepath}: {e}')
                    continue
            else:
                result['applied_files'].append(filepath)

        # 6. Git checkpoint
        if result['applied_files'] and not dry_run:
            commit_hash = self._git_checkpoint(
                workspace_path, stage_name, result['applied_files'], runtime=runtime
            )
            result['git_commit'] = commit_hash

        result['success'] = len(result['rejected_files']) == 0
        return result

    @api.model
    def rollback(self, workspace_path, commit_hash, runtime=None):
        """Revert to a previous git commit."""
        if not commit_hash:
            return False
        
        if not runtime:
            _logger.error("Patch rollback failed: No runtime provided for execution.")
            return False
            
        try:
            runtime.tools.execute("mcp.tool.terminal", {
                "command": f"git revert --no-commit {commit_hash}",
                "cwd": workspace_path
            }, runtime)
            
            runtime.tools.execute("mcp.tool.terminal", {
                "command": f"git commit -m \"Rollback: reverted {commit_hash}\"",
                "cwd": workspace_path
            }, runtime)
            return True
        except Exception as e:
            _logger.error('Patch rollback failed: %s', e)
            return False

    # ── Patch Parsing ──────────────────────────────────────────────

    def _parse_patches(self, ai_response):
        """
        Extract file patches from AI response text.
        Supports:
          - Fenced code blocks with file path annotations
          - Unified diff format
          - JSON patch format
        """
        if not ai_response or not ai_response.strip():
            return []

        patches = []

        # Try JSON format first
        try:
            data = json.loads(ai_response)
            if isinstance(data, dict) and 'patches' in data:
                return data['patches']
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, TypeError):
            pass

        # Try fenced code blocks:  ```filepath\n...\n```
        fenced_pattern = re.compile(
            r'```(?:[\w./-]+\s+)?([^\n`]+\.(?:js|jsx|ts|tsx|css|html|json|py|vue|svelte))\s*\n'
            r'(.*?)'
            r'\n```',
            re.DOTALL
        )
        for match in fenced_pattern.finditer(ai_response):
            patches.append({
                'file': match.group(1).strip(),
                'content': match.group(2),
                'action': 'write',
            })

        # Try unified diff  --- a/file ... +++ b/file
        if not patches:
            diff_pattern = re.compile(
                r'---\s+a/(.+?)\n\+\+\+\s+b/(.+?)\n(@@.+?)(?=\n---|\Z)',
                re.DOTALL
            )
            for match in diff_pattern.finditer(ai_response):
                patches.append({
                    'file': match.group(2).strip(),
                    'content': match.group(3),
                    'action': 'patch',
                })

        return patches

    # ── Validation ─────────────────────────────────────────────────

    def _validate_syntax(self, filepath, content):
        """Basic syntax validation based on file extension."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.json':
            try:
                json.loads(content)
                return True, None
            except json.JSONDecodeError as e:
                return False, str(e)

        if ext == '.py':
            try:
                compile(content, filepath, 'exec')
                return True, None
            except SyntaxError as e:
                return False, str(e)

        # For JS/TS/HTML/CSS — basic bracket balance
        if ext in ('.js', '.jsx', '.ts', '.tsx', '.css', '.vue', '.svelte'):
            opens = content.count('{') + content.count('(') + content.count('[')
            closes = content.count('}') + content.count(')') + content.count(']')
            if abs(opens - closes) > 3:
                return False, f'Bracket imbalance: opens={opens} closes={closes}'

        return True, None

    def _detect_conflict(self, abs_path, new_content):
        """Check for conflict markers in the proposed content."""
        conflict_markers = ['<<<<<<<', '=======', '>>>>>>>']
        for marker in conflict_markers:
            if marker in new_content:
                return f'Conflict marker found: {marker}'
        return None

    # ── Git ────────────────────────────────────────────────────────

    def _git_checkpoint(self, workspace_path, stage_name, files, runtime=None):
        """Create a git commit for the applied patches."""
        git_dir = os.path.join(workspace_path, '.git')
        if not os.path.isdir(git_dir):
            return None
            
        if not runtime:
            _logger.warning("Git checkpoint skipped: No runtime provided for execution.")
            return None
            
        try:
            runtime.tools.execute("mcp.tool.terminal", {
                "command": "git add -A",
                "cwd": workspace_path
            }, runtime)
            
            msg = f'[Nexora] {stage_name}: patched {len(files)} file(s)'
            # Use single quotes for the commit message to avoid shell escaping issues
            runtime.tools.execute("mcp.tool.terminal", {
                "command": f"git commit -m '{msg}' --allow-empty",
                "cwd": workspace_path
            }, runtime)
            
            # Extract hash
            hash_result = runtime.tools.execute("mcp.tool.terminal", {
                "command": "git rev-parse --short HEAD",
                "cwd": workspace_path
            }, runtime)
            
            # Handle list vs dict return types based on CapabilityResult
            if isinstance(hash_result, list) and len(hash_result) > 0 and 'text' in hash_result[0]:
                return hash_result[0]['text'].strip()
            elif isinstance(hash_result, dict) and 'stdout' in hash_result:
                return hash_result['stdout'].strip()
            return str(hash_result).strip()
        except Exception as e:
            _logger.error('Git checkpoint failed: %s', e)
            return None
