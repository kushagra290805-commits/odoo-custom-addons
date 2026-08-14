# -*- coding: utf-8 -*-
"""
Context Builder — constructs a complete AI context from the Agency
Workflow data model for use by Stage 06 and all review stages.
"""
from odoo import models, api
import os
import subprocess
import json
import logging

_logger = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 120_000  # Compress if larger


class ContextBuilder(models.AbstractModel):
    _name = 'nexora.context_builder'
    _description = 'AI Context Builder'

    @api.model
    def build(self, builder_session):
        """
        Build and return a structured context dict from the full Agency
        Workflow chain for the given builder_session record.
        """
        ctx = {}

        # ── Session & Configuration ────────────────────────────────
        config = builder_session.builder_configuration_id
        ctx['session'] = {
            'id': builder_session.id,
            'name': builder_session.name,
            'status': builder_session.status,
        }
        ctx['configuration'] = {
            'id': config.id if config else None,
            'name': config.name if config else '',
            'environment': config.environment if config and hasattr(config, 'environment') else '',
        }

        # ── Project Chain ──────────────────────────────────────────
        ctx['project'] = {}
        ctx['project_request'] = {}
        ctx['requirements'] = {}
        try:
            assignments = self.env['nexora.developer_assignment'].search([
                ('builder_session_id', '=', builder_session.id)
            ], limit=1)
            if assignments:
                req = assignments.request_id
                ctx['project_request'] = {
                    'id': req.id,
                    'name': req.name,
                    'type': req.request_type,
                    'status': req.status,
                }
                project = req.project_id
                ctx['project'] = {
                    'id': project.id,
                    'name': project.name,
                    'client': project.partner_id.name if project.partner_id else '',
                }
                reqs = req.requirements_id
                if reqs:
                    ctx['requirements'] = {
                        'business_name': reqs.business_name or '',
                        'industry': reqs.industry or '',
                        'company_description': reqs.company_description or '',
                        'branding': reqs.branding_details or '',
                        'required_pages': reqs.required_pages or '',
                        'required_features': reqs.required_features or '',
                        'integrations': reqs.integrations or '',
                        'seo': reqs.seo_preferences or '',
                        'client_notes': reqs.client_notes or '',
                    }
        except Exception as e:
            _logger.debug('Context builder: project chain unavailable: %s', e)

        # ── Workspace ──────────────────────────────────────────────
        workspace = builder_session.workspace_id
        workspace_path = workspace.workspace_path if workspace else None
        ctx['workspace'] = {'path': workspace_path or ''}

        if workspace_path and os.path.isdir(workspace_path):
            ctx['workspace']['tree'] = self._collect_file_tree(workspace_path)
            ctx['workspace']['framework'] = self._detect_framework(workspace_path)
            ctx['workspace']['dependencies'] = self._read_dependencies(workspace_path)
        else:
            ctx['workspace']['tree'] = []
            ctx['workspace']['framework'] = 'unknown'
            ctx['workspace']['dependencies'] = {}

        # ── Git Status ─────────────────────────────────────────────
        ctx['git'] = self._collect_git_status(workspace_path)

        # ── Template Metadata ──────────────────────────────────────
        ctx['template'] = {}
        try:
            template_analyzer = self.env['nexora.template_analyzer']
            manifest = template_analyzer.analyze(workspace_path)
            ctx['template'] = manifest
        except Exception as e:
            _logger.debug('Context builder: template analysis skipped: %s', e)

        # ── Previous AI Audit Logs ─────────────────────────────────
        ctx['previous_audits'] = []
        try:
            audits = self.env['nexora.ai_audit_log'].search([
                ('builder_session_id', '=', builder_session.id)
            ], order='create_date desc', limit=10)
            for a in audits:
                ctx['previous_audits'].append({
                    'stage': a.generation_stage,
                    'provider': a.ai_provider,
                    'status': a.status,
                    'failure': a.failure_reason or '',
                })
        except Exception:
            pass

        # ── Runtime Events ─────────────────────────────────────────
        ctx['runtime_events'] = []
        try:
            events = self.env['nexora.runtime_event'].search([
                ('builder_session_id', '=', builder_session.id)
            ], order='create_date desc', limit=20)
            for ev in events:
                ctx['runtime_events'].append({
                    'type': ev.event_type,
                    'message': ev.message,
                })
        except Exception:
            pass

        # ── Capabilities ───────────────────────────────────────────
        ctx['capabilities'] = []
        try:
            caps = self.env['nexora.capability_registry'].search([])
            for c in caps:
                ctx['capabilities'].append({
                    'name': c.name,
                    'type': c.capability_type if hasattr(c, 'capability_type') else '',
                })
        except Exception:
            pass

        # ── Compression ────────────────────────────────────────────
        serialized = json.dumps(ctx, default=str)
        if len(serialized) > _MAX_CONTEXT_CHARS:
            ctx = self._compress(ctx, serialized)

        return ctx

    @api.model
    def to_prompt_text(self, context_dict):
        """Serialize context to a compact prompt string."""
        lines = ['=== PROJECT CONTEXT ===']
        for section, data in context_dict.items():
            if not data:
                continue
            lines.append(f'\n--- {section.upper()} ---')
            if isinstance(data, dict):
                for k, v in data.items():
                    if v:
                        lines.append(f'  {k}: {v}')
            elif isinstance(data, list):
                for item in data[:10]:
                    if isinstance(item, dict):
                        lines.append('  - ' + ', '.join(
                            f'{k}={v}' for k, v in item.items() if v
                        ))
                    else:
                        lines.append(f'  - {item}')
        return '\n'.join(lines)

    # ── Private Helpers ────────────────────────────────────────────

    def _collect_file_tree(self, workspace_path):
        """Walk workspace and return a compact file listing."""
        tree = []
        src = os.path.join(workspace_path, 'src')
        base = src if os.path.isdir(src) else workspace_path
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in (
                'node_modules', '.git', '__pycache__', '.nexora'
            )]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), base)
                tree.append(rel.replace('\\', '/'))
        return tree[:200]  # cap

    def _detect_framework(self, workspace_path):
        """Detect the JS/TS framework from package.json."""
        pkg_path = os.path.join(workspace_path, 'src', 'package.json')
        if not os.path.isfile(pkg_path):
            pkg_path = os.path.join(workspace_path, 'package.json')
        if not os.path.isfile(pkg_path):
            return 'unknown'
        try:
            with open(pkg_path, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            if 'next' in deps:
                return 'nextjs'
            if 'nuxt' in deps:
                return 'nuxt'
            if '@angular/core' in deps:
                return 'angular'
            if 'svelte' in deps:
                return 'svelte'
            if 'vue' in deps:
                return 'vue'
            if 'react' in deps:
                return 'react'
            if 'vite' in deps:
                return 'vite'
            return 'vanilla'
        except Exception:
            return 'unknown'

    def _read_dependencies(self, workspace_path):
        """Read the dependencies from package.json."""
        pkg_path = os.path.join(workspace_path, 'src', 'package.json')
        if not os.path.isfile(pkg_path):
            pkg_path = os.path.join(workspace_path, 'package.json')
        if not os.path.isfile(pkg_path):
            return {}
        try:
            with open(pkg_path, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
            return pkg.get('dependencies', {})
        except Exception:
            return {}

    def _collect_git_status(self, workspace_path):
        """Return git status info dict."""
        if not workspace_path or not os.path.isdir(
            os.path.join(workspace_path, '.git')
        ):
            return {'initialized': False}
        try:
            diff = subprocess.run(
                ['git', 'diff', '--stat'],
                cwd=workspace_path, capture_output=True, text=True, timeout=10
            ).stdout.strip()
            branch = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=workspace_path, capture_output=True, text=True, timeout=5
            ).stdout.strip()
            return {
                'initialized': True,
                'branch': branch,
                'diff_stat': diff[:2000] if diff else 'clean',
            }
        except Exception:
            return {'initialized': True, 'error': 'git command failed'}

    def _compress(self, ctx, serialized):
        """Aggressively trim large sections to fit the context budget."""
        # Drop the heaviest sections first
        if 'workspace' in ctx and 'tree' in ctx['workspace']:
            ctx['workspace']['tree'] = ctx['workspace']['tree'][:50]
        ctx.pop('runtime_events', None)
        ctx.pop('capabilities', None)
        if 'previous_audits' in ctx:
            ctx['previous_audits'] = ctx['previous_audits'][:3]
        return ctx

    @api.model
    def build_assistant_context(self, builder_session, active_file_path=None):
        """
        Build and return a structured context specifically tailored for the Builder Assistant.
        This includes the conversation memory and focused file contents.
        """
        ctx = {}

        # ── Session & Configuration ────────────────────────────────
        ctx['session'] = {
            'id': builder_session.id,
            'name': builder_session.name,
        }

        # ── Workspace ──────────────────────────────────────────────
        workspace = builder_session.workspace_id
        workspace_path = workspace.workspace_path if workspace else None
        
        ctx['workspace'] = {'path': workspace_path or ''}
        if workspace_path and os.path.isdir(workspace_path):
            ctx['workspace']['tree'] = self._collect_file_tree(workspace_path)
            ctx['workspace']['dependencies'] = self._read_dependencies(workspace_path)
            
            # Read Active File Content
            if active_file_path:
                full_active_path = os.path.join(workspace_path, active_file_path.strip('/'))
                if os.path.isfile(full_active_path):
                    try:
                        with open(full_active_path, 'r', encoding='utf-8') as f:
                            ctx['workspace']['active_file'] = {
                                'path': active_file_path,
                                'content': f.read()
                            }
                    except Exception as e:
                        _logger.warning(f"Context builder: could not read active file {active_file_path}: {e}")

        # ── Conversation History ───────────────────────────────────
        try:
            history = self.env['nexora.builder_conversation'].get_messages(builder_session.id)
            # Take last 10 messages to save context budget
            ctx['conversation_history'] = history[-10:] if history else []
        except Exception as e:
            _logger.warning(f"Context builder: could not load conversation memory: {e}")
            ctx['conversation_history'] = []

        # ── Git Status ─────────────────────────────────────────────
        ctx['git'] = self._collect_git_status(workspace_path)
        
        return ctx
