# -*- coding: utf-8 -*-
"""
Spline Rendering Provider — Phase 37.2

Canonical Spline 3D rendering provider for Nexora Studio.
Generates and validates React project artifacts that embed Spline scenes
via the official @splinetool/react-spline package.

This provider does NOT execute Node.js, spawn processes, or invoke the
Spline runtime from the backend. It generates declarative React components
that reference Spline scenes by validated URL. The browser-side React
application is responsible for rendering.
"""

import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from .react_provider import ReactRenderingProvider
from .rendering_provider import ProviderMetadata, RenderingContext

_logger = logging.getLogger(__name__)

# Approved Spline host domains for scene URL validation
_APPROVED_SPLINE_HOSTS = frozenset({
    "prod.spline.design",
    "draft.spline.design",
    "app.spline.design",
    "my.spline.design",
})

# Approved Spline scene file extensions
_APPROVED_SPLINE_EXTENSIONS = frozenset({
    ".splinecode",
    ".spline",
})


def validate_spline_scene_url(url: str) -> Dict[str, Any]:
    """
    Validate a Spline scene URL against the security policy.

    Accepts:
      - HTTPS URLs to approved Spline hosting domains with valid extensions
      - Relative paths to local .splinecode assets (for self-hosted scenes)

    Rejects:
      - javascript: URIs
      - data: URIs
      - HTTP (non-TLS) remote URLs
      - Hosts outside the approved domain set (for remote URLs)
      - URLs without valid Spline extensions (for remote URLs)
    """
    if not url or not isinstance(url, str):
        return {"valid": False, "error": "Scene URL is empty or not a string."}

    url_stripped = url.strip()

    # Block dangerous URI schemes
    lower_url = url_stripped.lower()
    if lower_url.startswith("javascript:") or lower_url.startswith("data:"):
        return {"valid": False, "error": f"Dangerous URI scheme rejected: {url_stripped[:30]}..."}

    # Allow relative paths to local .splinecode assets
    if not url_stripped.startswith("http://") and not url_stripped.startswith("https://"):
        # Relative path — validate extension only
        if any(url_stripped.endswith(ext) for ext in _APPROVED_SPLINE_EXTENSIONS):
            return {"valid": True, "source_type": "local_asset"}
        return {"valid": False, "error": f"Local scene path must end with {_APPROVED_SPLINE_EXTENSIONS}: {url_stripped}"}

    # Remote URL validation
    if url_stripped.startswith("http://"):
        return {"valid": False, "error": "Spline scene URLs must use HTTPS."}

    try:
        parsed = urlparse(url_stripped)
    except Exception as e:
        return {"valid": False, "error": f"Malformed URL: {e}"}

    if parsed.hostname not in _APPROVED_SPLINE_HOSTS:
        return {"valid": False, "error": f"Spline scene host '{parsed.hostname}' is not in the approved domain set."}

    path_lower = parsed.path.lower()
    if not any(path_lower.endswith(ext) for ext in _APPROVED_SPLINE_EXTENSIONS):
        return {"valid": False, "error": f"Spline scene URL path must end with {_APPROVED_SPLINE_EXTENSIONS}."}

    return {"valid": True, "source_type": "remote_url"}


class SplineRenderingProvider(ReactRenderingProvider):
    """
    Canonical Spline 3D rendering provider.

    Extends ReactRenderingProvider to generate React project artifacts
    that embed Spline scenes via @splinetool/react-spline. Validates
    Spline-specific dependencies, scene source URLs, and project structure.

    This provider is a PEER to ReactThreeFiberProvider under the
    RenderingProviderRegistry. Both may coexist in a single generated project.
    """

    def get_metadata(self) -> ProviderMetadata:
        from .provider_registry import RenderingProviderRegistry
        return RenderingProviderRegistry.get_provider_metadata("spline")

    def validate_project(self, context: RenderingContext, project_structure: Dict[str, str]) -> Dict[str, Any]:
        """
        Extends the standard React validate_project with Spline-specific checks.

        Validates:
        - Standard React project structure (via super())
        - Presence of @splinetool/react-spline in package.json
        - Rejection of unapproved 3D engines (playcanvas, babylon)
        - Scene URL safety in component source code
        """
        # Run the base React validation (mode-aware — spline provider_id
        # will bypass the 'three' and '@splinetool' restrictions)
        base_result = super().validate_project(context, project_structure)
        errors = base_result.get("errors", [])

        # Check package.json for required Spline dependency
        pkg_json = project_structure.get('package.json', '')
        if pkg_json and '"@splinetool/react-spline"' not in pkg_json:
            errors.append("package.json is missing required Spline dependency '@splinetool/react-spline'.")

        # Scan source files for Spline-specific validation
        for filepath, code in project_structure.items():
            if not (filepath.endswith('.jsx') or filepath.endswith('.js')):
                continue

            code_lower = code.lower()

            # Reject unapproved 3D engines (peers like R3F are allowed)
            if "playcanvas" in code_lower or "babylon" in code_lower:
                errors.append(f"Unapproved 3D dependency found in {filepath}. "
                              f"Only @splinetool/react-spline and @splinetool/runtime are permitted in Spline mode.")

            # Validate Spline scene URLs found in source
            # Pattern: scene="..." or scene='...'
            scene_urls = re.findall(r'scene\s*=\s*["\']([^"\']+)["\']', code)
            for scene_url in scene_urls:
                result = validate_spline_scene_url(scene_url)
                if not result["valid"]:
                    errors.append(f"Invalid Spline scene URL in {filepath}: {result['error']}")

        return {
            "valid": len(errors) == 0,
            "files_checked": len(project_structure),
            "errors": errors,
        }
