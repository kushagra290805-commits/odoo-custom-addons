# -*- coding: utf-8 -*-
import urllib.request
import urllib.error
import json
import time
import os
import logging
from typing import Dict, Any, Optional, Union
from .penpot_auth import PenpotAuthenticator, get_authenticator

_logger = logging.getLogger(__name__)

class PenpotAPIClient:
    """
    Production-ready HTTP client for the self-hosted Penpot instance.
    
    Encapsulates:
    - 4-tier Configuration Precedence (Explicit, Odoo SysParam, OS Env, Default)
    - Authentication via PenpotAuthenticator abstraction
    - Exponential backoff retry engine for transient HTTP/network errors
    - Connection and health validation
    - Structured logging
    """
    
    DEFAULT_URL = "http://localhost:9001"
    DEFAULT_CONNECT_TIMEOUT = 5.0
    DEFAULT_READ_TIMEOUT = 15.0

    def __init__(self, config: Optional[Dict[str, Any]] = None, env: Optional[Any] = None, authenticator: Optional[PenpotAuthenticator] = None):
        self.config = config or {}
        self.env = env
        self.base_url = self._resolve_url()
        self.connect_timeout, self.read_timeout = self._resolve_timeouts()
        self.authenticator = authenticator or get_authenticator(self.config, self.env)
        
        _logger.info("Initialized PenpotAPIClient targeted at: %s (connect_timeout=%.1fs, read_timeout=%.1fs, auth=%s)", 
                     self.base_url, self.connect_timeout, self.read_timeout, 
                     type(self.authenticator).__name__ if self.authenticator else "None")

    def _resolve_url(self) -> str:
        # 1. Explicit config
        url = self.config.get("url") or self.config.get("public_uri") or self.config.get("base_url")
        if url:
            return str(url).rstrip('/')
            
        # 2. Odoo system parameter
        if self.env and hasattr(self.env, 'get'):
            try:
                param_url = self.env['ir.config_parameter'].sudo().get_param('nexora.penpot_url') or \
                            self.env['ir.config_parameter'].sudo().get_param('nexora.penpot_public_uri')
                if param_url:
                    return str(param_url).rstrip('/')
            except Exception as e:
                _logger.debug("Could not resolve Odoo sysparam for penpot_url: %s", str(e))
                
        # 3. OS Environment variable
        env_url = os.environ.get("PENPOT_PUBLIC_URI") or os.environ.get("PENPOT_URL")
        if env_url:
            return str(env_url).rstrip('/')
            
        # 4. Default
        return self.DEFAULT_URL

    def _resolve_timeouts(self):
        c_timeout = self.config.get("connect_timeout", self.DEFAULT_CONNECT_TIMEOUT)
        r_timeout = self.config.get("read_timeout", self.DEFAULT_READ_TIMEOUT)
        if self.env and hasattr(self.env, 'get'):
            try:
                c_param = self.env['ir.config_parameter'].sudo().get_param('nexora.penpot_connect_timeout')
                r_param = self.env['ir.config_parameter'].sudo().get_param('nexora.penpot_read_timeout')
                if c_param:
                    c_timeout = float(c_param)
                if r_param:
                    r_timeout = float(r_param)
            except Exception:
                pass
        return float(c_timeout), float(r_timeout)

    def set_authenticator(self, authenticator: PenpotAuthenticator):
        self.authenticator = authenticator
        _logger.debug("Updated PenpotAPIClient authenticator to: %s", type(authenticator).__name__)

    def rpc_call(self, command: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 3) -> Any:
        """
        Execute an RPC command against the Penpot server with automatic retry handling.
        """
        url = f"{self.base_url}/api/rpc/command/{command}"
        payload = json.dumps(params or {}).encode('utf-8')
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.authenticator:
            headers.update(self.authenticator.get_headers())
            
        attempt = 0
        backoff = 0.5
        
        while attempt <= max_retries:
            attempt += 1
            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=self.read_timeout) as response:
                    res_body = response.read().decode('utf-8')
                    if not res_body or res_body.strip() == "":
                        return {}
                    return json.loads(res_body)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='ignore')
                status_code = e.code
                
                # Transient 5xx server errors warrant a retry
                if status_code in (500, 502, 503, 504) and attempt <= max_retries:
                    _logger.warning("Penpot RPC '%s' encountered HTTP %d on attempt %d/%d. Retrying in %.1fs...", 
                                    command, status_code, attempt, max_retries, backoff)
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                
                # Permanent errors (400, 401, 403, 404) or exhausted retries
                _logger.error("Penpot RPC '%s' failed with HTTP %d: %s", command, status_code, err_body[:200])
                raise RuntimeError(f"Penpot API Error HTTP {status_code} for command '{command}': {err_body}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt <= max_retries:
                    _logger.warning("Penpot RPC '%s' network/timeout error on attempt %d/%d: %s. Retrying in %.1fs...", 
                                    command, attempt, max_retries, str(e), backoff)
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                _logger.error("Penpot RPC '%s' failed after %d attempts due to network error: %s", command, attempt, str(e))
                raise ConnectionError(f"Failed to connect to Penpot server at {self.base_url}: {str(e)}") from e
                
        raise RuntimeError(f"Exhausted retries executing Penpot RPC command: {command}")

    def validate_connection(self) -> Dict[str, Any]:
        """
        Validate live server reachability and authentication status.
        """
        try:
            profile = self.rpc_call("get-profile", {}, max_retries=1)
            is_authenticated = bool(profile and isinstance(profile, dict) and "id" in profile and profile.get("fullname") != "Anonymous User")
            if not is_authenticated and self.authenticator:
                # If we passed an auth token but got anonymous or 401
                is_authenticated = self.authenticator.authenticate(self)
                
            return {
                "status": "ok",
                "reachable": True,
                "authenticated": is_authenticated,
                "url": self.base_url,
                "profile": profile
            }
        except Exception as e:
            _logger.error("Connection validation failed for Penpot at %s: %s", self.base_url, str(e))
            return {
                "status": "error",
                "reachable": False,
                "authenticated": False,
                "url": self.base_url,
                "error": str(e)
            }
