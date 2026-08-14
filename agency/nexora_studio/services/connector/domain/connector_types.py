"""
Connector Type System
=====================
Part 3 of Phase 26 — Universal Connector Platform Foundation.

Defines the pluggable connector type hierarchy.
New connector types are registered via ConnectorTypeRegistry — no code modification required.
All types are provider-independent abstractions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Lifecycle Policy
# ---------------------------------------------------------------------------

class LifecyclePolicy(str, Enum):
    """
    Governs how a connector type behaves across lifecycle transitions.
    
    MANAGED — Full lifecycle: registered → running → removed. Platform manages all transitions.
    EPHEMERAL — Short-lived. Created per-execution, removed after. No persistent installation.
    PERSISTENT — Always-on. Platform ensures it is always RUNNING. Auto-restarts on failure.
    MANUAL — Operator controls all transitions. No automatic state changes.
    """
    MANAGED = "managed"
    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Connector Type Descriptor (provider-independent base)
# ---------------------------------------------------------------------------

@dataclass
class ConnectorTypeDescriptor:
    """
    Describes the characteristics and contract of a connector type.
    Registered in ConnectorTypeRegistry — one instance per type.

    This is a pure descriptor object. It does not contain execution logic.
    Execution adapters are implemented per type in future phases.
    """
    type_id: str                                # Unique type identifier, e.g. 'mcp', 'rest', 'cli'
    display_name: str                           # Human-readable name, e.g. 'MCP Connector'
    description: str = ""
    icon: str = ""                              # Icon identifier for UI
    lifecycle_policy: LifecyclePolicy = LifecyclePolicy.MANAGED

    # Credential requirements at the type level (per-connector may add more)
    required_credential_types: List[str] = field(default_factory=list)

    # Which UCEL execution targets this type can use
    supported_execution_targets: List[str] = field(default_factory=list)

    # Whether this type supports health probing
    supports_health_check: bool = True

    # Whether this type supports multiple simultaneous instances
    supports_multiple_instances: bool = True

    # Whether this type requires a persistent session (auth token, connection, etc.)
    requires_session: bool = False

    # Whether a connector of this type is installable from a remote registry
    is_remotely_installable: bool = False

    # Whether this type supports hot-reload without lifecycle restart
    supports_hot_reload: bool = False

    # Metadata passthrough
    type_metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"ConnectorTypeDescriptor(type_id={self.type_id!r}, name={self.display_name!r})"


# ---------------------------------------------------------------------------
# Built-in Connector Type Definitions
# ---------------------------------------------------------------------------
# Each definition is an instance of ConnectorTypeDescriptor.
# These are registered into ConnectorTypeRegistry at platform bootstrap.
# New types in future phases are added by creating new instances — not by
# modifying this file.

MCP_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="mcp",
    display_name="MCP Connector",
    description="Model Context Protocol connector. Communicates with MCP servers via JSON-RPC over stdio or HTTP/SSE.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=[],
    supported_execution_targets=["remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=True,
    is_remotely_installable=True,
    supports_hot_reload=False,
)

REPOSITORY_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="repository",
    display_name="Repository Connector",
    description="Source code repository connector. Supports Git-compatible providers (GitHub, GitLab, Bitbucket, local git).",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key", "oauth2", "ssh_key"],
    supported_execution_targets=["local", "remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=True,
    is_remotely_installable=False,
    supports_hot_reload=False,
)

REST_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="rest",
    display_name="REST API Connector",
    description="Generic REST API connector. Supports any HTTP/HTTPS endpoint with configurable authentication.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key", "bearer_token", "oauth2", "basic_auth"],
    supported_execution_targets=["remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=False,
    is_remotely_installable=False,
    supports_hot_reload=True,
)

GRAPHQL_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="graphql",
    display_name="GraphQL Connector",
    description="Generic GraphQL connector. Supports any GraphQL endpoint with query/mutation/subscription.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key", "bearer_token", "oauth2"],
    supported_execution_targets=["remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=False,
    is_remotely_installable=False,
    supports_hot_reload=True,
)

CLI_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="cli",
    display_name="CLI Tool Connector",
    description="Command-line tool connector. Executes system binaries with configurable arguments and environment.",
    lifecycle_policy=LifecyclePolicy.EPHEMERAL,
    required_credential_types=[],
    supported_execution_targets=["local"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=False,
    is_remotely_installable=True,
    supports_hot_reload=False,
)

SDK_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="sdk",
    display_name="SDK Connector",
    description="Python SDK connector. Wraps installed Python packages as capability providers.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key"],
    supported_execution_targets=["local"],
    supports_health_check=True,
    supports_multiple_instances=False,
    requires_session=False,
    is_remotely_installable=True,
    supports_hot_reload=False,
)

DOCKER_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="docker",
    display_name="Docker Container Connector",
    description="Docker container connector. Manages container lifecycle and executes capabilities inside containers.",
    lifecycle_policy=LifecyclePolicy.PERSISTENT,
    required_credential_types=[],
    supported_execution_targets=["local"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=False,
    is_remotely_installable=True,
    supports_hot_reload=False,
)

LOCAL_TOOL_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="local_tool",
    display_name="Local Tool Connector",
    description="Local Odoo-registered tool connector. Bridges the Connector Platform with the legacy tool registry.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=[],
    supported_execution_targets=["local"],
    supports_health_check=False,
    supports_multiple_instances=False,
    requires_session=False,
    is_remotely_installable=False,
    supports_hot_reload=True,
)

ODOO_MODULE_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="odoo_module",
    display_name="Odoo Module Connector",
    description="Odoo module connector. Exposes capabilities implemented as Odoo service models.",
    lifecycle_policy=LifecyclePolicy.PERSISTENT,
    required_credential_types=[],
    supported_execution_targets=["local"],
    supports_health_check=True,
    supports_multiple_instances=False,
    requires_session=False,
    is_remotely_installable=True,
    supports_hot_reload=False,
)

AI_PROVIDER_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="ai_provider",
    display_name="AI Model Provider Connector",
    description="AI language model connector. Exposes AI inference as capability namespaces routed through the AI provider bus.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key", "bearer_token"],
    supported_execution_targets=["remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=False,
    is_remotely_installable=False,
    supports_hot_reload=True,
)

DESIGN_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="design",
    display_name="Design Tool Connector",
    description="Design platform connector. Integrates with design tools (Penpot, Figma, Sketch, etc.) to import and export design artifacts.",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key", "oauth2"],
    supported_execution_targets=["remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=True,
    is_remotely_installable=False,
    supports_hot_reload=False,
)

DEPLOYMENT_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="deployment",
    display_name="Deployment Connector",
    description="Deployment target connector. Publishes generated websites to hosting platforms (Vercel, Netlify, S3, custom servers).",
    lifecycle_policy=LifecyclePolicy.MANAGED,
    required_credential_types=["api_key", "oauth2", "certificate"],
    supported_execution_targets=["remote"],
    supports_health_check=True,
    supports_multiple_instances=True,
    requires_session=True,
    is_remotely_installable=False,
    supports_hot_reload=False,
)

UNKNOWN_CONNECTOR_TYPE = ConnectorTypeDescriptor(
    type_id="unknown",
    display_name="Unknown Connector Type",
    description="Fallback for connector types not registered in this platform instance. Used for forward compatibility.",
    lifecycle_policy=LifecyclePolicy.MANUAL,
    required_credential_types=[],
    supported_execution_targets=[],
    supports_health_check=False,
    supports_multiple_instances=True,
    requires_session=False,
    is_remotely_installable=False,
    supports_hot_reload=False,
)


# ---------------------------------------------------------------------------
# All Built-in Types as an ordered registry-seed list
# ---------------------------------------------------------------------------

BUILTIN_CONNECTOR_TYPES: List[ConnectorTypeDescriptor] = [
    MCP_CONNECTOR_TYPE,
    REPOSITORY_CONNECTOR_TYPE,
    REST_CONNECTOR_TYPE,
    GRAPHQL_CONNECTOR_TYPE,
    CLI_CONNECTOR_TYPE,
    SDK_CONNECTOR_TYPE,
    DOCKER_CONNECTOR_TYPE,
    LOCAL_TOOL_CONNECTOR_TYPE,
    ODOO_MODULE_CONNECTOR_TYPE,
    AI_PROVIDER_CONNECTOR_TYPE,
    DESIGN_CONNECTOR_TYPE,
    DEPLOYMENT_CONNECTOR_TYPE,
    UNKNOWN_CONNECTOR_TYPE,
]
