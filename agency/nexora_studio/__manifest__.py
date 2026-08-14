# -*- coding: utf-8 -*-
{
    # ---------------------------------------------------------
    # Nexora Studio - Enterprise Foundation
    # ---------------------------------------------------------
    'name': 'Nexora Studio',
    'version': '1.0.0',
    'category': 'Services',
    'summary': 'Enterprise digital service agency operating system',
    'description': 'Initial enterprise foundation for Nexora Studio (Odoo 19 Community).',
    'author': 'Nexora',
    'license': 'LGPL-3',
    
    # ---------------------------------------------------------
    # Core Dependencies
    # ---------------------------------------------------------
    'depends': [
        'base',
        'mail',
        'contacts',
        'crm',
        'project',
        'website',
        'template_store',
    ],
    
    # ---------------------------------------------------------
    # Application Resources
    # ---------------------------------------------------------
    'data': [
        
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/registry_views.xml',
        'views/res_config_settings_views.xml',
        'views/workspace_views.xml',
        'views/runtime_capability_views.xml',
        'views/builder_configuration_views.xml',
        'views/builder_session_views.xml',
        'views/runtime_views.xml',
        'views/menu_views.xml',
        'views/provider_registry_views.xml',
        'views/ai_audit_log_views.xml',
        'views/runtime_event_views.xml',
        'views/auth_views.xml',
        'data/registry_seed_data.xml',
        'data/nexora_seed_data.xml',
        'data/openrouter_config.xml',
        'data/ai_catalog_cron.xml',
        'data/nexora_capability_cron.xml',
        'data/provider_actions.xml',
        'data/source_registry_data.xml',
        # Phase 26 — Universal Connector Platform
        'data/connector_health_cron.xml',
        'views/connector_views.xml',
        # Phase 28 — MCP Connector Onboarding
        'views/mcp_server_views.xml',
        'wizard/mcp_connection_test_wizard.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'nexora_studio/static/src/xml/dashboard.xml',
            'nexora_studio/static/src/js/dashboard.js',
        ],
    },
    'external_dependencies': {},
    
    # ---------------------------------------------------------
    # Module Installation settings
    # ---------------------------------------------------------
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_provider_platform',
    'post_load': 'post_load_provider_platform',
}
