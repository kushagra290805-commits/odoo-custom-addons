# -*- coding: utf-8 -*-
"""
React Three Fiber Rendering Provider — Phase 37.1 / Phase 47.9 (U8).

Canonical WebGL/R3F renderer provider. Phase 47.9 (U8) closes this provider
into a real renderer: in addition to the inherited React scaffold it emits the
minimum valid R3F application structure (three + @react-three/fiber
dependencies, a Canvas scene entry with camera and lighting) and consumes the
selected ComponentTree information already produced by the U6/U7 pipeline.

Ownership contract (ADR-0074):
- this provider owns the renderer scaffold, renderer dependencies and the
  scene entry (src/scene/Scene.jsx, src/components/three/*);
- CodeGenerationEngine owns pages and enriches them by referencing the scene
  component; it never regenerates this scaffold;
- component sources come exclusively from the existing ComponentTree — no
  GitHub queries, no pmndrs client, no parallel component source.

Runtime marker contract (Phase 47.14 / U9.5):
- the generated Scene.jsx sets ``window.__NEXORA_RENDERER_RUNTIME__`` from
  the R3F Canvas ``onCreated`` lifecycle callback ONLY - never
  unconditionally - with the shape
  ``{provider, initialized, canvas, webgl}``;
- ``initialized`` is true only after R3F has actually created its
  WebGLRenderer (canvas mounted, render loop started);
- the marker is read only by the existing Playwright provider's browser
  runtime probe; the ValidationEngine interprets the probe evidence
  through the existing issue contract.
"""
import re
from typing import Dict, Any, List, Optional
import logging
from .react_provider import ReactRenderingProvider
from .rendering_provider import ProviderMetadata, RenderingContext

_logger = logging.getLogger(__name__)

# Renderer dependency versions are defined by this provider contract.
_R3F_CORE_DEPENDENCIES = {
    "three": "^0.169.0",
    "@react-three/fiber": "^8.17.10",
}
_R3F_DREI_DEPENDENCY = {"@react-three/drei": "^9.114.3"}


def _js_identifier(raw: str, fallback: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '_', str(raw or '')).strip('_')
    if not slug:
        return fallback
    parts = [p for p in slug.split('_') if p]
    name = ''.join(p.capitalize() for p in parts)
    if name[0].isdigit():
        name = 'Three' + name
    return name


def _is_r3f_component(node: Dict[str, Any]) -> bool:
    """Deterministic qualification: a ComponentTree node is an R3F component
    when its provenance/metadata/code identify it as three.js/R3F content.
    Visual complexity alone never qualifies a component."""
    metadata = node.get('metadata') or {}
    if not metadata.get('from_source'):
        return False
    haystack = ' '.join([
        str(metadata.get('semantic', '')),
        str(metadata.get('source_identifier', '')),
        str(node.get('component_id', '')),
    ]).lower()
    if any(token in haystack for token in ('3d', 'three', 'r3f', 'webgl', 'threed')):
        return True
    code = str(node.get('code') or '').lower()
    return '@react-three/fiber' in code or "from 'three'" in code or 'from "three"' in code


class ReactThreeFiberProvider(ReactRenderingProvider):
    """
    Renders React Three Fiber projects. Extends the standard React provider
    with the R3F renderer scaffold, renderer dependencies, ComponentTree
    consumption and strict R3F validations.
    """

    def get_metadata(self) -> ProviderMetadata:
        from .provider_registry import RenderingProviderRegistry
        # Retrieve the pre-defined metadata stub for react_three_fiber
        return RenderingProviderRegistry.get_provider_metadata("react_three_fiber")

    # ------------------------------------------------------------------
    # Renderer dependency contract
    # ------------------------------------------------------------------

    def _selected_r3f_components(self, context: RenderingContext) -> List[Dict[str, Any]]:
        selected = (context.output_config or {}).get('selected_components') or []
        return [n for n in selected if isinstance(n, dict) and _is_r3f_component(n)]

    def _gltf_assets(self, context: RenderingContext) -> List[Dict[str, Any]]:
        """Actual existing asset references only — never fabricated."""
        assets = (context.output_config or {}).get('renderer_assets') or []
        gltf = []
        for a in assets:
            url = str((a or {}).get('url') or '').strip()
            if url.lower().endswith(('.glb', '.gltf')):
                gltf.append(a)
        return gltf

    def _requires_drei(self, context: RenderingContext) -> bool:
        if self._gltf_assets(context):
            return True  # useGLTF is a drei helper
        for node in self._selected_r3f_components(context):
            blob = ' '.join([
                str(node.get('code') or ''),
                str((node.get('metadata') or {})),
            ]).lower()
            if '@react-three/drei' in blob:
                return True
        return False

    def _extra_dependencies(self, context: RenderingContext) -> Dict[str, str]:
        deps = dict(_R3F_CORE_DEPENDENCIES)
        if context is not None and self._requires_drei(context):
            deps.update(_R3F_DREI_DEPENDENCY)
        return deps

    # ------------------------------------------------------------------
    # Renderer scaffold synthesis
    # ------------------------------------------------------------------

    def _generate_scene_component_files(self, context: RenderingContext) -> Dict[str, str]:
        files: Dict[str, str] = {}
        for node in self._selected_r3f_components(context):
            code = str(node.get('code') or '').strip()
            if not code:
                continue
            name = _js_identifier(node.get('component_id') or node.get('name'), 'ThreeSceneObject')
            path = f"src/components/three/{name}.jsx"
            if path in files:
                continue
            if 'export default' not in code:
                code = code + f"\n\nexport default {name}\n"
            files[path] = code
        return files

    def _generate_scene_jsx(self, context: RenderingContext, component_files: Dict[str, str]) -> str:
        imports = [
            "import React from 'react'",
            "import { Canvas } from '@react-three/fiber'",
        ]
        body_tags: List[str] = []

        for path in sorted(component_files):
            name = path.rsplit('/', 1)[-1].split('.jsx')[0]
            rel = '../components/three/' + name + '.jsx'
            imports.append(f"import {name} from '{rel}'")
            body_tags.append(f"        <{name} />")

        gltf_assets = self._gltf_assets(context)
        if gltf_assets:
            imports.append("import { useGLTF } from '@react-three/drei'")
            for idx, asset in enumerate(gltf_assets):
                url = str(asset.get('url'))
                model_name = f"GltfModel{idx + 1}"
                body_tags.append(f"        <{model_name} />")
            model_defs = []
            for idx, asset in enumerate(gltf_assets):
                url = str(asset.get('url'))
                model_name = f"GltfModel{idx + 1}"
                model_defs.append(
                    f"function {model_name}() {{\n"
                    f"  const {{ scene }} = useGLTF('{url}')\n"
                    f"  return <primitive object={{scene}} />\n"
                    f"}}"
                )
            imports.append("")
            imports.extend(model_defs)

        if not body_tags:
            # Minimal valid fallback scene. No provenance is claimed for this
            # generated code — it is recorded as a generated fallback.
            body_tags = [
                "        <mesh rotation={[0.4, 0.2, 0]}>",
                "          <boxGeometry args={[1.5, 1.5, 1.5]} />",
                "          <meshStandardMaterial color=\"#3b82f6\" />",
                "        </mesh>",
            ]

        scene_body = "\n".join(body_tags)
        imports_block = "\n".join(imports)
        # Phase 47.14 (U9.5): the Canvas onCreated lifecycle callback is the
        # canonical, truthful R3F runtime signal. The marker is set ONLY when
        # R3F has actually created its WebGLRenderer — it is never set
        # unconditionally — and carries the canvas attachment + WebGL-context
        # facts read from the live renderer. The existing Playwright provider
        # (U9.5 browser runtime probe) only READS this marker; it never
        # fabricates runtime state.
        return f'''{imports_block}

export default function Scene() {{
  return (
    <div className="r3f-scene-container" style={{{{ width: '100%', height: '60vh' }}}}>
      <Canvas
        camera={{{{ position: [0, 2, 6], fov: 50 }}}}
        onCreated={{(state) => {{
          try {{
            const canvas = state.gl ? state.gl.domElement : null;
            const gl = state.gl ? state.gl.getContext() : null;
            window.__NEXORA_RENDERER_RUNTIME__ = {{
              provider: 'react_three_fiber',
              initialized: true,
              canvas: !!(canvas && canvas.isConnected),
              webgl: !!gl,
            }};
          }} catch (e) {{
            window.__NEXORA_RENDERER_RUNTIME__ = {{
              provider: 'react_three_fiber',
              initialized: false,
              error: String(e),
            }};
          }}
        }}}}
      >
        <ambientLight intensity={{0.6}} />
        <directionalLight position={{[5, 5, 5]}} intensity={{1}} />
{scene_body}
      </Canvas>
    </div>
  )
}}'''

    def generate_project(self, context: RenderingContext) -> Dict[str, Any]:
        # Build the base React structure without the final validation gate,
        # extend it with the R3F renderer scaffold, then validate the final
        # composition exactly once.
        project_structure, library_files = self._synthesize_structure(context)

        component_files = self._generate_scene_component_files(context)
        project_structure.update(component_files)
        project_structure['src/scene/Scene.jsx'] = self._generate_scene_jsx(context, component_files)

        selected_nodes = self._selected_r3f_components(context)
        consumed = [
            {
                "component_id": n.get('component_id'),
                "source_identifier": (n.get('metadata') or {}).get('source_identifier'),
                "provenance": "component_tree",
            }
            for n in selected_nodes if str(n.get('code') or '').strip()
        ]
        scene_provenance = "component_tree" if consumed else "generated-fallback"

        self.validate_manifest(context)
        val_res = self.validate_project(context, project_structure)

        extra_metadata = {
            "renderer_strategy": (context.output_config or {}).get("rendering_strategy", "webgl"),
            "scene_entry": "src/scene/Scene.jsx",
            "scene_provenance": scene_provenance,
            "r3f_components_consumed": consumed,
            "gltf_assets_referenced": [a.get('url') for a in self._gltf_assets(context)],
        }
        return self._build_result(context, project_structure, library_files, val_res, extra_metadata)

    def validate_project(self, context: RenderingContext, project_structure: Dict[str, str]) -> Dict[str, Any]:
        """
        Extends the standard React validate_project to ensure R3F compliance.
        """
        # First, run the base React validation (which now checks the provider mode)
        base_result = super().validate_project(context, project_structure)
        errors = list(base_result.get("errors", []))

        # Verify valid R3F imports, reject invalid ones
        for filepath, code in project_structure.items():
            if not filepath.endswith(self._source_extensions):
                continue

            code_lower = code.lower()
            if "import " in code_lower:
                # Safeguard: reject known unapproved 3D engines (peers like Spline are allowed)
                if "playcanvas" in code_lower or "babylon" in code_lower:
                    errors.append(f"Unapproved 3D dependency found in {filepath}. Only three, @react-three/fiber, @react-three/drei are permitted in R3F mode.")

        # In R3F mode, we expect at least some 3D dependencies to be present in package.json or source
        pkg_json = project_structure.get('package.json', '')
        if pkg_json and ('"three"' not in pkg_json and '"@react-three/fiber"' not in pkg_json):
            errors.append("package.json is missing required R3F dependencies ('three' or '@react-three/fiber').")

        # Phase 47.9 (U8): a Canvas render entry must exist in the scaffold.
        has_canvas = any(
            '<canvas' in str(code).lower()
            for filepath, code in project_structure.items()
            if filepath.endswith(self._source_extensions)
        )
        if not has_canvas:
            errors.append("R3F project is missing a Canvas render entry (<Canvas> from @react-three/fiber).")

        return {
            "valid": len(errors) == 0,
            "files_checked": len(project_structure),
            "errors": errors,
        }
