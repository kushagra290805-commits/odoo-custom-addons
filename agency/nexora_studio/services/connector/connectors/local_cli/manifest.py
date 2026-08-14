from typing import Any, Dict
from odoo.addons.nexora_studio.services.connector.domain.models import ConnectorManifest

def get_manifest() -> ConnectorManifest:
    """Returns the canonical manifest for the Local CLI Connector."""
    return ConnectorManifest(
        connector_id="core.local_cli",
        display_name="Local CLI Connector",
        connector_type_id="cli",
        description="Executes shell commands directly on the host machine running the Nexora platform.",
        version="1.0.0",
        author="Nexora Team",
        publisher="Nexora",
        capabilities=[
            "shell.execute",
            "process.spawn",
            "process.kill",
            "dependency.install"
        ],
        transports=["local_subprocess"],
        credential_requirements=[],
        configuration_schema={
            "type": "object",
            "properties": {
                "working_directory": {
                    "type": "string",
                    "description": "Default working directory for commands"
                },
                "allowed_executables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of allowed executables (empty means all allowed)"
                },
                "default_timeout_seconds": {
                    "type": "number",
                    "default": 60
                },
                "max_output_size_bytes": {
                    "type": "integer",
                    "default": 1048576  # 1 MB
                },
                "shell": {
                    "type": "boolean",
                    "default": True
                }
            }
        },
        metadata={
            "is_core": True,
            "transport": "subprocess"
        }
    )
