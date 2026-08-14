import json
import logging
import uuid
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def migrate_source_registry(env):
    """
    Deterministically migrates source_registry config_json credentials
    to nexora.mcp_credential, leaving non-secret config intact.
    """
    SourceRegistry = env['nexora.source_registry']
    McpCredential = env['nexora.mcp_credential']
    McpServerConfig = env['nexora.mcp_server_config']
    Connector = env['nexora.connector']
    
    records = SourceRegistry.search([])
    
    report = {
        'inspected': len(records),
        'migrated': 0,
        'skipped': 0,
        'manual_review': 0,
        'credentials_removed': 0,
    }
    
    for record in records:
        if not record.is_mcp:
            # Non-MCP source, preserve as is
            report['skipped'] += 1
            continue
            
        if not record.config_json:
            report['skipped'] += 1
            continue
            
        try:
            config = json.loads(record.config_json)
        except json.JSONDecodeError:
            _logger.warning(f"Invalid JSON in config_json for {record.technical_name}")
            report['manual_review'] += 1
            continue
            
        # Detect credential bearing
        # The schema expected: {"credentials": {"api_key": "..."}} or similar
        # Since we must be deterministic, we check for explicit 'api_key' or 'token' in known keys
        credential_value = None
        credential_type = 'api_key'
        
        if 'api_key' in config:
            credential_value = config.pop('api_key')
        elif 'credentials' in config and 'api_key' in config['credentials']:
            credential_value = config['credentials'].pop('api_key')
            if not config['credentials']:
                config.pop('credentials')
        elif 'token' in config:
            credential_value = config.pop('token')
            credential_type = 'oauth'
            
        if not credential_value:
            # Non-secret configuration
            report['skipped'] += 1
            continue
            
        if not isinstance(credential_value, str) or len(credential_value.strip()) == 0:
            _logger.warning(f"Ambiguous credential value for {record.technical_name}")
            report['manual_review'] += 1
            continue
            
        # Create Credential
        cred = McpCredential.create({
            'name': f"Migrated {record.name} Credential",
            'technical_name': f"migrated_{record.technical_name}_{uuid.uuid4().hex[:8]}",
            'credential_type': credential_type,
            'is_active': True,
        })
        cred.write_secret(credential_value)
        
        # Create Server Config
        server_config = McpServerConfig.create({
            'name': f"Migrated {record.name} Config",
            'technical_name': f"migrated_{record.technical_name}_config",
            'provider_id': record.technical_name,
            'transport_type': 'stdio', # default assumption, needs verification later
            'startup_command': 'unknown',
            'credential_id': cred.id,
            'is_active': True
        })
        
        # Create Connector
        connector = Connector.create({
            'name': f"{record.name} Connector",
            'technical_name': f"migrated_{record.technical_name}_connector",
            'connector_type': 'mcp',
            'mcp_config_id': server_config.id,
            'status': 'offline',
            'lifecycle_state': 'registered'
        })
        
        # Link and wipe
        record.connector_id = connector.id
        record.config_json = json.dumps(config) # Write back the cleaned config
        
        report['migrated'] += 1
        report['credentials_removed'] += 1
        
    return report

