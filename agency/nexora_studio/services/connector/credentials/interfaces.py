"""
Connector Credential Architecture — Interfaces Only
====================================================
Part 8 of Phase 26 — Universal Connector Platform Foundation.

Defines four pure abstract base classes:
  - SecretsProvider         (key-value secret store)
  - CredentialResolver      (resolves ConnectorCredentialReferences to values)
  - ConfigurationProvider   (manages connector configuration)
  - AuthenticationProvider  (manages connector authentication sessions)

NO implementations are provided in Phase 26.
Implementations will be introduced in Connector Platform Phase 1 (Phase 27+).

These interfaces are the boundary defined by Phase 25.1.5 PRE-001.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..domain.models import (
    ConnectorConfiguration,
    ConnectorCredentialReference,
    ConnectorRuntimeContext,
    ConnectorSession,
)


# ---------------------------------------------------------------------------
# Supporting Result Types
# ---------------------------------------------------------------------------

@dataclass
class CredentialValidationResult:
    """Result of validating that a credential reference can be resolved."""
    valid: bool
    credential_key: str
    error: str = ""
    metadata: Dict[str, Any] = None  # type: ignore

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ValidationResult:
    """Generic validation result."""
    valid: bool
    errors: List[str] = None  # type: ignore

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class AuthenticationResult:
    """Result of an authentication attempt."""
    success: bool
    session: Optional[ConnectorSession] = None
    error: str = ""
    requires_user_interaction: bool = False  # True for OAuth2 browser flows
    interaction_url: str = ""                # OAuth2 authorization URL if applicable


# ---------------------------------------------------------------------------
# Interface 1: SecretsProvider
# ---------------------------------------------------------------------------

class SecretsProvider(ABC):
    """
    Abstract interface for a secure key-value secret store.

    Implementations must:
    - Store secrets encrypted at rest
    - Never log secret values
    - Provide atomic get/set/delete operations
    - Support namespaced key prefixes for isolation

    Planned implementations (Phase 27+):
    - OdooSecretsStore — uses encrypted Odoo field on nexora.connector_configuration
    - EnvSecretsStore — reads from environment variables (dev/CI only)
    - VaultSecretsStore — integrates with HashiCorp Vault or similar
    """

    @abstractmethod
    def get_secret(self, key: str) -> str:
        """
        Retrieve a secret value by key.
        Raises KeyError if the key does not exist.
        Never returns None — raises instead.
        """

    @abstractmethod
    def set_secret(self, key: str, value: str) -> None:
        """
        Store a secret value. Encrypts before persisting.
        Raises ValueError if the key is invalid.
        """

    @abstractmethod
    def delete_secret(self, key: str) -> None:
        """
        Delete a secret. No-op if key does not exist.
        """

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """
        List all secret keys, optionally filtered by prefix.
        Returns key names only — never values.
        """

    @abstractmethod
    def has_secret(self, key: str) -> bool:
        """Returns True if the key exists in the store."""


# ---------------------------------------------------------------------------
# Interface 2: CredentialResolver
# ---------------------------------------------------------------------------

class CredentialResolver(ABC):
    """
    Abstract interface for resolving ConnectorCredentialReferences to their runtime values.

    Takes a ConnectorCredentialReference (which contains a key and type)
    and returns the resolved credential value dict ready for injection into
    a ConnectorRuntimeContext.

    Implementations must:
    - Read from SecretsProvider using the reference.credential_key
    - Never cache resolved credentials in memory beyond the request lifetime
    - Never log resolved credential values
    """

    @abstractmethod
    def resolve(
        self,
        reference: ConnectorCredentialReference,
        context: ConnectorRuntimeContext,
    ) -> Dict[str, str]:
        """
        Resolve a credential reference to a dict of credential fields.
        For API keys: {'api_key': '<value>'}
        For OAuth2: {'access_token': '<value>', 'token_type': 'Bearer'}
        For SSH keys: {'private_key': '<pem content>'}
        Raises RuntimeError if the credential cannot be resolved.
        """

    @abstractmethod
    def validate(
        self,
        reference: ConnectorCredentialReference,
    ) -> CredentialValidationResult:
        """
        Validate that a credential reference can be resolved without actually resolving it.
        Does NOT make external calls — only checks that the key exists in the store.
        """


# ---------------------------------------------------------------------------
# Interface 3: ConfigurationProvider
# ---------------------------------------------------------------------------

class ConfigurationProvider(ABC):
    """
    Abstract interface for managing connector configurations.

    Configuration management responsibilities:
    - Reading the current configuration for a connector
    - Updating configuration values
    - Retrieving the configuration JSON schema
    - Validating configuration against schema

    Implementations must:
    - Store configuration values in nexora.connector_configuration (Odoo model)
    - Treat secrets in configuration as references, not values
    - Return typed ConnectorConfiguration objects, not raw dicts
    """

    @abstractmethod
    def get_configuration(self, connector_id: str) -> ConnectorConfiguration:
        """
        Retrieve the current configuration for a connector.
        Returns an empty ConnectorConfiguration if none is set.
        Raises KeyError if the connector_id is not registered.
        """

    @abstractmethod
    def update_configuration(
        self,
        connector_id: str,
        config: ConnectorConfiguration,
    ) -> None:
        """
        Persist updated configuration for a connector.
        Triggers validation after update.
        Raises ValidationError if the configuration violates the schema.
        """

    @abstractmethod
    def get_schema(self, connector_id: str) -> Dict[str, Any]:
        """
        Retrieve the JSON Schema for the connector's configuration.
        Returns {} if no schema is defined.
        """

    @abstractmethod
    def validate_configuration(
        self,
        connector_id: str,
        config: ConnectorConfiguration,
    ) -> ValidationResult:
        """
        Validate configuration against the connector's schema.
        Returns ValidationResult with errors if invalid.
        Does NOT persist the configuration.
        """


# ---------------------------------------------------------------------------
# Interface 4: AuthenticationProvider
# ---------------------------------------------------------------------------

class AuthenticationProvider(ABC):
    """
    Abstract interface for managing connector authentication.

    Manages the full authentication lifecycle:
    authenticate → session → refresh → revoke

    Implementations are specific to credential types:
    - ApiKeyAuthProvider — resolves API key from SecretsProvider, returns non-expiring session
    - OAuth2AuthProvider — orchestrates OAuth2 code flow, manages token refresh
    - SshKeyAuthProvider — resolves SSH key, validates fingerprint
    - BasicAuthProvider — resolves username/password, base64-encodes for HTTP headers

    Implementations must:
    - Accept ConnectorCredentialReference (not raw credentials)
    - Delegate actual secret retrieval to CredentialResolver
    - Return a ConnectorSession with a scoped, non-logged access_token
    - Never store raw credentials — only resolved session tokens
    """

    @abstractmethod
    def authenticate(
        self,
        connector_id: str,
        credentials: Dict[str, str],
    ) -> AuthenticationResult:
        """
        Authenticate using resolved credentials.
        Returns an AuthenticationResult containing a ConnectorSession on success.
        The session's access_token is the resolved, ready-to-use credential.
        """

    @abstractmethod
    def refresh(
        self,
        connector_id: str,
        session: ConnectorSession,
    ) -> ConnectorSession:
        """
        Refresh an expired or near-expiry session.
        Returns a new ConnectorSession with updated tokens.
        Raises RuntimeError if the session cannot be refreshed.
        """

    @abstractmethod
    def revoke(
        self,
        connector_id: str,
        session: ConnectorSession,
    ) -> None:
        """
        Revoke an active session (e.g., invalidate OAuth2 token).
        Best-effort — implementations must not raise on revocation failure.
        """

    @abstractmethod
    def validate_session(
        self,
        session: ConnectorSession,
    ) -> bool:
        """
        Validate that a session is still active and usable.
        Should make a lightweight API call if possible (e.g., GET /me).
        Returns True if valid, False if expired or invalid.
        """
