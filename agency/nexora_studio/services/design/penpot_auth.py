# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging

_logger = logging.getLogger(__name__)

class PenpotAuthenticator(ABC):
    """
    Abstract interface for Penpot authentication mechanisms.
    
    Supports multiple authentication strategies (PAT, OAuth, Session Cookies) without
    coupling the DesignProvider or API client to a specific auth protocol.
    """
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Return HTTP headers required for authenticated requests."""
        pass

    @abstractmethod
    def authenticate(self, client: Any) -> bool:
        """Validate credentials against the live server using the provided client."""
        pass


class PATAuthenticator(PenpotAuthenticator):
    """
    Personal Access Token (PAT) Authenticator implementation for Penpot.
    
    Generates 'Authorization: Token <token>' headers and validates credentials
    via the live '/api/rpc/command/get-profile' endpoint.
    """
    def __init__(self, token: str):
        if not token:
            raise ValueError("PATAuthenticator requires a non-empty access token.")
        self.token = token

    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def authenticate(self, client: Any) -> bool:
        try:
            profile = client.rpc_call("get-profile", {})
            if profile and isinstance(profile, dict) and "id" in profile:
                _logger.info("Successfully authenticated with Penpot as profile: %s (%s)", profile.get("fullname", "Unknown"), profile.get("id"))
                return True
            return False
        except Exception as e:
            _logger.warning("PAT authentication failed against live Penpot server: %s", str(e))
            return False


class SessionAuthenticator(PenpotAuthenticator):
    """
    Architectural stub for Session Cookie or OAuth-based authentication.
    
    Provides extensibility for enterprise SSO or web-login workflows.
    """
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id

    def get_headers(self) -> Dict[str, str]:
        if not self.session_id:
            return {"Content-Type": "application/json", "Accept": "application/json"}
        return {
            "Cookie": f"penpot-session={self.session_id}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def authenticate(self, client: Any) -> bool:
        if not self.session_id:
            raise NotImplementedError("SessionAuthenticator is defined as an architectural stub. Explicit session_id is required.")
        try:
            profile = client.rpc_call("get-profile", {})
            return bool(profile and "id" in profile)
        except Exception as e:
            _logger.warning("Session authentication failed: %s", str(e))
            return False


def get_authenticator(config: Dict[str, Any], env: Optional[Any] = None) -> Optional[PenpotAuthenticator]:
    """
    Factory helper to resolve and instantiate the appropriate PenpotAuthenticator
    using configuration precedence:
    1. Explicit config dict ('token', 'access_token', 'session_id')
    2. Odoo system parameter ('nexora.penpot_token')
    3. OS environment variables ('PENPOT_ACCESS_TOKEN', 'PENPOT_TOKEN')
    """
    # 1. Explicit config
    token = config.get("token") or config.get("access_token")
    if token:
        return PATAuthenticator(token)
    session_id = config.get("session_id")
    if session_id:
        return SessionAuthenticator(session_id)

    # 2. Odoo system parameter
    if env and hasattr(env, 'get'):
        try:
            param_token = env['ir.config_parameter'].sudo().get_param('nexora.penpot_token')
            if param_token:
                return PATAuthenticator(param_token)
        except Exception as e:
            _logger.debug("Could not resolve Odoo system parameter 'nexora.penpot_token': %s", str(e))

    # 3. Environment variable
    env_token = os.environ.get("PENPOT_ACCESS_TOKEN") or os.environ.get("PENPOT_TOKEN")
    if env_token:
        return PATAuthenticator(env_token)

    return None
