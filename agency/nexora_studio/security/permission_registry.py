from odoo import models

NEXORA_PERMISSIONS = {
    'group_nexora_super_admin': [
        'users.manage', 'users.reset_password', 'users.enable', 'users.disable',
        'sessions.view', 'sessions.manage', 'audit.read', 'projects.manage',
        'templates.manage', 'runtimes.manage', 'console.access', 'odoo.backend.access'
    ],
    'group_nexora_admin': [
        'users.manage_developers', 'users.reset_developer_password',
        'sessions.view', 'audit.read', 'projects.manage',
        'templates.manage', 'runtimes.manage', 'console.access', 'odoo.backend.access_limited'
    ],
    'group_nexora_developer': [
        'console.access', 'projects.read', 'projects.write', 'templates.read'
    ],
    'group_nexora_viewer': [
        'console.access', 'projects.read', 'templates.read'
    ]
}

def get_user_permissions(user):
    perms = set()
    for group_xml_id, permissions in NEXORA_PERMISSIONS.items():
        if user.has_group(f'nexora_studio.{group_xml_id}'):
            perms.update(permissions)
    return list(perms)

def get_user_primary_role(user):
    if user.has_group('nexora_studio.group_nexora_super_admin'):
        return 'super_admin'
    if user.has_group('nexora_studio.group_nexora_admin'):
        return 'admin'
    if user.has_group('nexora_studio.group_nexora_developer'):
        return 'developer'
    if user.has_group('nexora_studio.group_nexora_viewer'):
        return 'viewer'
    return 'none'
