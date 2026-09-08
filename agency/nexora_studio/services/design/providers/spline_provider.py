# -*- coding: utf-8 -*-
"""
Spline Rendering Provider — Phase 37.2 / Phase 47.9 (U8).

Canonical Spline 3D rendering provider for Nexora Studio.
Generates and validates React project artifacts that embed Spline scenes
via the official @splinetool/react-spline package.

This provider does NOT execute Node.js, spawn processes, or invoke the
Spline runtime from the backend. It generates declarative React components
that reference Spline scenes by validated URL. The browser-side React
application is responsible for rendering.

Phase 47.9 (U8) closes this provider into a real renderer: it emits the
Spline integration structure (dependency + SplineScene component) for an
explicit Spline requirement with a validated scene reference. It never
fabricates a scene: a missing or unsafe scene reference fails generation.
No Spline connector, Spline MCP, Spline source row, or direct Spline API
access exists or is introduced.

Runtime marker contract (Phase 47.14 / U9.5):
- the generated SplineScene.jsx sets ``window.__NEXORA_RENDERER_RUNTIME__``
  from the Spline component's ``onLoad`` callback ONLY - never
  unconditionally - with the shape
  ``{provider, initialized, scene_loaded, scene_status}``;
- ``initialized`` is true once the Spline React integration initialized;
- ``scene_loaded`` is derived from the actual scene-resource response
  (``fetch`` + ``response.ok``) because the Spline runtime resolves load()
  even for invalid scene data - a broken scene must never report
  ``scene_loaded`` as true;
- the marker is read only by the existing Playwright provider's browser
  runtime probe; the ValidationEngine interprets the probe evidence
  through the existing issue contract.
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

# Renderer dependency version defined by this provider contract.
# NOTE: @splinetool/runtime is pinned to the 1.x line deliberately.
# react-spline declares peerDep "@splinetool/runtime": "*", and npm >=7
# auto-installs peer deps at the latest version; runtime 2.0.x depends on
# "@splinetool/animation-core", which is not published to npm (E404 upstream),
# breaking every fresh install. The 1.x line is the last published, complete
# runtime and matches the version contract used by this addon.
_SPLINE_DEPENDENCIES = {
    "@splinetool/react-spline": "^4.1.0",
    "@splinetool/runtime": "^1.12.98",
}


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

    # ------------------------------------------------------------------
    # Renderer dependency contract
    # ------------------------------------------------------------------

    def _extra_dependencies(self, context: RenderingContext) -> Dict[str, str]:
        return dict(_SPLINE_DEPENDENCIES)

    # ------------------------------------------------------------------
    # Renderer scaffold synthesis
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_spline_scene_jsx(scene_url: str) -> str:
        # Phase 47.14 (U9.5): onLoad alone is NOT sufficient proof that the
        # scene loaded - the Spline runtime resolves load() (and fires onLoad)
        # even when the scene data is invalid; broken scenes surface later as
        # uncaught render errors. The marker therefore verifies the scene
        # resource itself is actually retrievable (fetch + response.ok)
        # before claiming scene_loaded. It is never set unconditionally, and
        # the existing Playwright provider's browser runtime probe only READS
        # it.
        return f'''import React from 'react';
import Spline from '@splinetool/react-spline';

export default function SplineScene() {{
  return (
    <div className="spline-scene-container" style={{{{ width: '100%', height: '60vh' }}}}>
      <Spline
        scene="{scene_url}"
        onLoad={{() => {{
          fetch('{scene_url}')
            .then((r) => {{
              window.__NEXORA_RENDERER_RUNTIME__ = {{
                provider: 'spline',
                initialized: true,
                scene_loaded: r.ok,
                scene_status: r.status,
              }};
            }})
            .catch((e) => {{
              window.__NEXORA_RENDERER_RUNTIME__ = {{
                provider: 'spline',
                initialized: true,
                scene_loaded: false,
                error: String(e),
              }};
            }});
        }}}}
      />
    </div>
  );
}}'''

    def generate_project(self, context: RenderingContext) -> Dict[str, Any]:
        # An explicit Spline requirement must carry a scene reference already
        # present in the requirements/design artifact. The provider never
        # invents a scene URL: missing or unsafe references fail generation.
        scene_url = str((context.output_config or {}).get('spline_scene_url') or '').strip()
        url_check = validate_spline_scene_url(scene_url)
        if not url_check.get("valid"):
            return {
                "status": "error",
                "provider": self.get_metadata().provider_id,
                "project_structure": {},
                "dependencies": {},
                "validation": {"valid": False, "errors": [url_check.get("error", "Invalid Spline scene reference.")]},
                "errors": [
                    f"Spline scene reference rejected: {url_check.get('error', 'invalid reference')}. "
                    "An explicit Spline requirement must provide a validated scene URL "
                    "(HTTPS on an approved Spline host, or a local .splinecode asset)."
                ],
            }

        result = super().generate_project(context)
        if result.get("status") != "success":
            return result

        project_structure: Dict[str, str] = dict(result.get("project_structure") or {})
        project_structure['src/components/SplineScene.jsx'] = self._generate_spline_scene_jsx(scene_url)

        # Re-validate the final structure including the Spline integration.
        val_res = self.validate_project(context, project_structure)

        try:
            import json as _json
            dependencies = _json.loads(project_structure.get('package.json', '{}')).get('dependencies', {})
        except Exception:
            dependencies = {}

        if not val_res.get("valid", False):
            return {
                "status": "error",
                "provider": self.get_metadata().provider_id,
                "project_structure": project_structure,
                "dependencies": dependencies,
                "validation": val_res,
                "errors": val_res.get("errors", []),
            }

        result["project_structure"] = project_structure
        result["dependencies"] = dependencies
        result["validation"] = val_res
        metadata = dict(result.get("metadata") or {})
        metadata["renderer_strategy"] = "spline"
        metadata["spline_scene_url"] = scene_url
        metadata["spline_scene_source_type"] = url_check.get("source_type")
        metadata["spline_integration_entry"] = "src/components/SplineScene.jsx"
        result["metadata"] = metadata
        return result

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
        errors = list(base_result.get("errors", []))

        # Check package.json for required Spline dependency
        pkg_json = project_structure.get('package.json', '')
        if pkg_json and '"@splinetool/react-spline"' not in pkg_json:
            errors.append("package.json is missing required Spline dependency '@splinetool/react-spline'.")

        # Scan source files for Spline-specific validation
        for filepath, code in project_structure.items():
            if not filepath.endswith(self._source_extensions):
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
