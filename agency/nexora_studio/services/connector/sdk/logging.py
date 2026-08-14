import logging
import json
import contextvars
from typing import Any, Dict, Optional

# Context variables for auto-propagating logging context
connector_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('connector_id', default=None)
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('correlation_id', default=None)
session_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('session_id', default=None)
capability_namespace_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('capability_namespace', default=None)

class StructuredConnectorLogger:
    """
    A structured logger wrapper that strictly outputs JSON format logs and automatically
    includes context propagated via contextvars.
    """
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        
    def _log(self, level: int, message: str, *args: Any, **kwargs: Any) -> None:
        """Internal method to format and emit structured logs."""
        if not self._logger.isEnabledFor(level):
            return
            
        if args:
            try:
                message = message % args
            except TypeError:
                pass
            
        # Build the structured payload
        payload = {
            "message": message,
            "severity": logging.getLevelName(level),
            "connector_id": connector_id_var.get(),
            "request_id": request_id_var.get(),
            "correlation_id": correlation_id_var.get(),
            "session_id": session_id_var.get(),
            "capability_namespace": capability_namespace_var.get(),
        }
        
        # Merge explicitly passed kwargs
        payload.update(kwargs)
        
        # Filter out None values to keep logs clean
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Output as JSON string
        self._logger.log(level, json.dumps(payload))

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, *args, **kwargs)

def get_logger(name: str) -> StructuredConnectorLogger:
    """Factory function to get a structured logger instance."""
    return StructuredConnectorLogger(name)

def set_logging_context(
    connector_id: Optional[str] = None,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    capability_namespace: Optional[str] = None
) -> Dict[str, contextvars.Token]:
    """
    Sets the logging context variables for the current execution thread/task.
    Returns the context tokens so they can be reset later.
    """
    tokens = {}
    if connector_id is not None:
        tokens['connector_id'] = connector_id_var.set(connector_id)
    if request_id is not None:
        tokens['request_id'] = request_id_var.set(request_id)
    if correlation_id is not None:
        tokens['correlation_id'] = correlation_id_var.set(correlation_id)
    if session_id is not None:
        tokens['session_id'] = session_id_var.set(session_id)
    if capability_namespace is not None:
        tokens['capability_namespace'] = capability_namespace_var.set(capability_namespace)
    return tokens

def reset_logging_context(tokens: Dict[str, contextvars.Token]) -> None:
    """Resets the context variables back to their previous states using the tokens."""
    if 'connector_id' in tokens:
        connector_id_var.reset(tokens['connector_id'])
    if 'request_id' in tokens:
        request_id_var.reset(tokens['request_id'])
    if 'correlation_id' in tokens:
        correlation_id_var.reset(tokens['correlation_id'])
    if 'session_id' in tokens:
        session_id_var.reset(tokens['session_id'])
    if 'capability_namespace' in tokens:
        capability_namespace_var.reset(tokens['capability_namespace'])
