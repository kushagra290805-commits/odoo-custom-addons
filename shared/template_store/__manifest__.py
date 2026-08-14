# -*- coding: utf-8 -*-
{
    'name': 'Nexora Template Store & Generation Engine',
    'version': '1.0.0',
    'category': 'Services/Templates',
    'summary': 'Single unified enterprise registry for template management and workspace generation',
    'description': """
Nexora Template Store & Generation Engine
=========================================
Single module responsible for all reusable template management, versioning, compatibility tracking, and automated workspace generation.
Generation is an integrated capability of the Template Store to transform reusable templates into active client project workspaces.

Key Capabilities Owned by Template Store:
-----------------------------------------
1. Template Registry & Metadata: Frontend templates (`nexora.template_frontend`), backend templates (`nexora.template_backend`), versions (`nexora.template_version`), compatibility matrix (`nexora.template_compatibility`), and schemas (`nexora.template_metadata`).
2. Generator Architecture Registry: Generator types (`nexora.generator_type`) and capabilities (`nexora.generator_capability`).
3. Metadata-Driven Pipelines: Generation pipelines (`nexora.generation_pipeline`) and ordered stages (`nexora.generation_stage`).
4. Abstract Generation Orchestration: Extensible interfaces (`nexora.generation_service`, `nexora.pipeline_service`, `nexora.validation_service`, `nexora.variable_engine`, `nexora.merge_service`, `nexora.workspace_preparation_service`).
5. Generation Jobs & Telemetry: Complete lifecycle tracking (`nexora.generation_job`), variable mapping (`nexora.generation_variable`), and audit logs (`nexora.generation_log`).
    """,
    'author': 'Nexora',
    'license': 'LGPL-3',
    'sequence': 10,
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/template_store_seed_data.xml',
        'views/menu_views.xml',
        'views/template_frontend_views.xml',
        'views/template_backend_views.xml',
        'views/template_version_views.xml',
        'views/template_compatibility_views.xml',
        'views/template_metadata_views.xml',
        'views/generator_type_views.xml',
        'views/generation_pipeline_views.xml',
        'views/generation_job_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
