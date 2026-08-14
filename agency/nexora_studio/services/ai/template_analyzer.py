# -*- coding: utf-8 -*-
"""
Template Analyzer — discovers structure of a web project template.

Automatically detects: pages, layouts, components, design tokens,
theme, routing, assets, forms, hooks, stores, and API layer.
"""
from odoo import models, api
import os
import re
import json
import logging

_logger = logging.getLogger(__name__)


class TemplateAnalyzer(models.AbstractModel):
    _name = 'nexora.template_analyzer'
    _description = 'Template Intelligence — automatic project structure analyzer'

    @api.model
    def analyze(self, workspace_path):
        """
        Walk the workspace source directory and return a structured
        template manifest dict.
        """
        if not workspace_path or not os.path.isdir(workspace_path):
            return {}

        src = os.path.join(workspace_path, 'src')
        base = src if os.path.isdir(src) else workspace_path

        manifest = {
            'pages': [],
            'layouts': [],
            'components': [],
            'design_tokens': [],
            'theme': {},
            'routing': [],
            'assets': [],
            'forms': [],
            'hooks': [],
            'stores': [],
            'api_layer': [],
            'config_files': [],
            'framework': self._detect_framework(workspace_path),
        }

        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in (
                'node_modules', '.git', '__pycache__', '.nexora', 'dist', 'build'
            )]
            rel_dir = os.path.relpath(root, base).replace('\\', '/')
            dir_lower = rel_dir.lower()

            for fname in files:
                rel_path = os.path.join(rel_dir, fname).replace('\\', '/')
                if rel_path.startswith('./'):
                    rel_path = rel_path[2:]
                ext = os.path.splitext(fname)[1].lower()
                name_lower = fname.lower()

                # Pages
                if self._is_page(dir_lower, name_lower, ext):
                    manifest['pages'].append(rel_path)

                # Layouts
                elif self._is_layout(dir_lower, name_lower, ext):
                    manifest['layouts'].append(rel_path)

                # Components
                elif self._is_component(dir_lower, name_lower, ext):
                    manifest['components'].append(rel_path)

                # Design tokens / theme
                elif self._is_design_token(dir_lower, name_lower, ext):
                    manifest['design_tokens'].append(rel_path)

                # Routing
                elif self._is_routing(dir_lower, name_lower, ext):
                    manifest['routing'].append(rel_path)

                # Assets
                elif ext in ('.png', '.jpg', '.jpeg', '.svg', '.gif', '.ico',
                             '.webp', '.woff', '.woff2', '.ttf', '.eot'):
                    manifest['assets'].append(rel_path)

                # Hooks
                elif self._is_hook(dir_lower, name_lower, ext):
                    manifest['hooks'].append(rel_path)

                # Stores
                elif self._is_store(dir_lower, name_lower, ext):
                    manifest['stores'].append(rel_path)

                # API layer
                elif self._is_api(dir_lower, name_lower, ext):
                    manifest['api_layer'].append(rel_path)

                # Forms
                elif self._is_form(dir_lower, name_lower, ext):
                    manifest['forms'].append(rel_path)

                # Config files
                elif name_lower in (
                    'tailwind.config.js', 'tailwind.config.ts',
                    'postcss.config.js', 'vite.config.js', 'vite.config.ts',
                    'next.config.js', 'next.config.ts', 'next.config.mjs',
                    'tsconfig.json', '.eslintrc.json', '.prettierrc',
                    'nuxt.config.ts', 'svelte.config.js',
                ):
                    manifest['config_files'].append(rel_path)

        # Read theme from CSS variables if possible
        manifest['theme'] = self._extract_theme(base)

        return manifest

    # ── Classification Helpers ─────────────────────────────────────

    def _is_page(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.astro'):
            return False
        return ('pages' in dir_lower or 'views' in dir_lower
                or 'app/' in dir_lower or name.startswith('page'))

    def _is_layout(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte'):
            return False
        return ('layout' in dir_lower or 'layout' in name)

    def _is_component(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte'):
            return False
        return ('component' in dir_lower or 'ui/' in dir_lower
                or 'shared/' in dir_lower)

    def _is_design_token(self, dir_lower, name, ext):
        if ext not in ('.css', '.scss', '.less', '.json'):
            return False
        return ('token' in name or 'variables' in name or 'theme' in name
                or 'colors' in name or 'design' in dir_lower)

    def _is_routing(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx'):
            return False
        return ('route' in name or 'router' in name or 'navigation' in name)

    def _is_hook(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx'):
            return False
        return ('hooks' in dir_lower or name.startswith('use'))

    def _is_store(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx'):
            return False
        return ('store' in dir_lower or 'state' in dir_lower
                or 'store' in name or 'slice' in name)

    def _is_api(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx'):
            return False
        return ('api/' in dir_lower or 'services/' in dir_lower
                or 'api' in name or 'service' in name or 'client' in name)

    def _is_form(self, dir_lower, name, ext):
        if ext not in ('.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte'):
            return False
        return ('form' in dir_lower or 'form' in name)

    def _detect_framework(self, workspace_path):
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

    def _extract_theme(self, base_dir):
        """Try to extract CSS custom properties from global stylesheets."""
        theme = {}
        for candidate in ('index.css', 'global.css', 'globals.css', 'app.css',
                          'styles/globals.css', 'styles/index.css'):
            css_path = os.path.join(base_dir, candidate)
            if os.path.isfile(css_path):
                try:
                    with open(css_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    # Extract --variable: value pairs
                    for m in re.finditer(r'--([\w-]+)\s*:\s*([^;]+);', content):
                        theme[m.group(1)] = m.group(2).strip()
                except Exception:
                    pass
                break
        return theme
