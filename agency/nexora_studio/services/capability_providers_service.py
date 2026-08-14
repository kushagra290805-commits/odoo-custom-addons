# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class CapabilityProvidersService(models.AbstractModel):
    _name = 'nexora.capability_providers_service'
    _description = 'Canonical Capability Providers Service'

    @api.model
    def register_all_providers(self):
        """
        Dynamically installs/registers all native production capability providers.
        """
        _logger.info("Registering all native capability providers into UCEL...")
        providers = self._get_native_providers()
        registry = self.env['nexora.capability_registry'].sudo()
        installer = self.env['nexora.plugin_installer_service']
        
        for p in providers:
            existing = registry.search([('capability_code', '=', p['capability_code'])], limit=1)
            if not existing:
                try:
                    _logger.info(f"Installing {p['capability_code']}...")
                    # Generate a mock PluginDescriptor using the object itself or dictionary map
                    from ..models.plugin_descriptor import PluginDescriptor
                    desc = PluginDescriptor(
                        capability_id=p['capability_id'],
                        capability_code=p['capability_code'],
                        display_name=p['display_name'],
                        category=p['category'],
                        version=p.get('version', '1.0.0'),
                        author='Nexora Studio',
                        provider=p['provider'],
                        implementation_model=p['implementation_model'],
                        checksum='native',
                        supported_platforms=['linux', 'windows', 'darwin'],
                        supports_local=True,
                        supports_remote=True,
                        supports_async=True,
                        permissions=['network', 'filesystem'] if p.get('requires_filesystem') else ['network'],
                        dependencies=p.get('dependencies', []),
                        optional_dependencies=[],
                        minimum_runtime_version='1.0',
                        maximum_runtime_version='2.0',
                        metadata_version='1.0'
                    )
                    installer.install_descriptor(desc)
                except Exception as e:
                    _logger.error(f"Failed to register provider {p['capability_code']}: {e}")
        return True

    def _get_native_providers(self):
        return [
            {
                'capability_id': 'mcp.search',
                'capability_code': 'search',
                'display_name': 'Google Search',
                'category': 'Business Intelligence',
                'provider': 'google',
                'implementation_model': 'nexora.provider.google_search',
                'dependencies': ['python:google-api-python-client']
            },
            {
                'capability_id': 'mcp.firecrawl',
                'capability_code': 'firecrawl',
                'display_name': 'Firecrawl Website Scraper',
                'category': 'Business Intelligence',
                'provider': 'firecrawl',
                'implementation_model': 'nexora.provider.firecrawl',
                'dependencies': ['python:firecrawl-py']
            },
            {
                'capability_id': 'mcp.github',
                'capability_code': 'github',
                'display_name': 'GitHub API',
                'category': 'Developer Tools',
                'provider': 'github',
                'implementation_model': 'nexora.provider.github',
                'dependencies': ['python:PyGithub']
            },
            {
                'capability_id': 'mcp.playwright',
                'capability_code': 'playwright',
                'display_name': 'Playwright Browser Automation',
                'category': 'Browser Automation',
                'provider': 'microsoft',
                'implementation_model': 'nexora.provider.playwright',
                'dependencies': ['npm:playwright']
            },
            {
                'capability_id': 'mcp.figma',
                'capability_code': 'figma',
                'display_name': 'Figma Design Import',
                'category': 'Design',
                'provider': 'figma',
                'implementation_model': 'nexora.provider.figma',
                'dependencies': ['python:requests']
            },
            {
                'capability_id': 'npm',
                'capability_code': 'npm',
                'display_name': 'NPM Package Manager',
                'category': 'Developer Tools',
                'provider': 'npmjs',
                'implementation_model': 'nexora.provider.npm',
                'dependencies': ['binary:node']
            },
            {
                'capability_id': 'mcp.eslint',
                'capability_code': 'eslint',
                'display_name': 'ESLint Validator',
                'category': 'Validation',
                'provider': 'eslint',
                'implementation_model': 'nexora.provider.eslint',
                'dependencies': ['npm:eslint']
            },
            {
                'capability_id': 'mcp.page_reviewer',
                'capability_code': 'page_reviewer',
                'display_name': 'Page Reviewer (Placeholder)',
                'category': 'Validation',
                'provider': 'nexora',
                'implementation_model': 'nexora.provider.placeholder'
            },
            {
                'capability_id': 'mcp.section_reviewer',
                'capability_code': 'section_reviewer',
                'display_name': 'Section Reviewer (Placeholder)',
                'category': 'Validation',
                'provider': 'nexora',
                'implementation_model': 'nexora.provider.placeholder'
            },
            {
                'capability_id': 'mcp.crosspage_reviewer',
                'capability_code': 'crosspage_reviewer',
                'display_name': 'Crosspage Reviewer (Placeholder)',
                'category': 'Validation',
                'provider': 'nexora',
                'implementation_model': 'nexora.provider.placeholder'
            },
            {
                'capability_id': 'mcp.business_goal_reviewer',
                'capability_code': 'business_goal_reviewer',
                'display_name': 'Business Goal Reviewer (Placeholder)',
                'category': 'Validation',
                'provider': 'nexora',
                'implementation_model': 'nexora.provider.placeholder'
            },
            {
                'capability_id': 'mcp.brand_reviewer',
                'capability_code': 'brand_reviewer',
                'display_name': 'Brand Reviewer (Placeholder)',
                'category': 'Validation',
                'provider': 'nexora',
                'implementation_model': 'nexora.provider.placeholder'
            },
            {
                'capability_id': 'mcp.design_reviewer',
                'capability_code': 'design_reviewer',
                'display_name': 'Design Reviewer (Placeholder)',
                'category': 'Validation',
                'provider': 'nexora',
                'implementation_model': 'nexora.provider.placeholder'
            }
        ]
