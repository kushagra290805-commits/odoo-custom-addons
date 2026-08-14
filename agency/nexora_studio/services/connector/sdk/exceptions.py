"""
Connector SDK Exceptions
========================
Phase 27.0 — Universal Connector Platform Production Hardening
Unified error taxonomy for the entire Connector Platform.
"""

from typing import Optional, Dict, Any

class ConnectorError(Exception):
    """
    Base exception for all connector errors.
    Contains structured fields for telemetry and standard API responses.
    """
    def __init__(
        self,
        error_code: str,
        category: str,
        severity: str,
        retryable: bool,
        user_safe_message: str,
        technical_message: str,
        root_cause: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(technical_message)
        self.error_code = error_code
        self.category = category
        self.severity = severity.upper()
        self.retryable = retryable
        self.user_safe_message = user_safe_message
        self.technical_message = technical_message
        self.root_cause = root_cause
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "category": self.category,
            "severity": self.severity,
            "retryable": self.retryable,
            "user_safe_message": self.user_safe_message,
            "technical_message": self.technical_message,
            "root_cause_type": type(self.root_cause).__name__ if self.root_cause else None,
            "metadata": self.metadata
        }


class ValidationException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Validation", severity=kwargs.pop("severity", "WARNING"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class ConfigurationException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Configuration", severity=kwargs.pop("severity", "ERROR"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class AuthenticationException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Authentication", severity=kwargs.pop("severity", "ERROR"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class AuthorizationException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Authorization", severity=kwargs.pop("severity", "WARNING"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class CompatibilityException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Compatibility", severity=kwargs.pop("severity", "ERROR"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class RuntimeException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Runtime", severity=kwargs.pop("severity", "ERROR"),
            retryable=kwargs.pop("retryable", False), user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class TransportException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Transport", severity=kwargs.pop("severity", "ERROR"),
            retryable=kwargs.pop("retryable", True), user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class ProviderException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Provider", severity=kwargs.pop("severity", "ERROR"),
            retryable=kwargs.pop("retryable", False), user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class RegistryException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Registry", severity=kwargs.pop("severity", "ERROR"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class PersistenceException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Persistence", severity=kwargs.pop("severity", "CRITICAL"),
            retryable=kwargs.pop("retryable", True), user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class TimeoutException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Timeout", severity=kwargs.pop("severity", "WARNING"),
            retryable=kwargs.pop("retryable", True), user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class CancellationException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="Cancellation", severity=kwargs.pop("severity", "INFO"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

class InternalPlatformException(ConnectorError):
    def __init__(self, error_code: str, user_safe_message: str, technical_message: str, **kwargs):
        super().__init__(
            error_code=error_code, category="InternalPlatform", severity=kwargs.pop("severity", "CRITICAL"),
            retryable=False, user_safe_message=user_safe_message, technical_message=technical_message, **kwargs
        )

# Maintain backwards compatibility aliases for the AAT test suite during migration
ConnectorConfigurationError = ConfigurationException
ConnectorExecutionError = RuntimeException
ConnectorAuthenticationError = AuthenticationException
ConnectorTimeoutError = TimeoutException
