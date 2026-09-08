import logging
import re
from typing import Any, Dict, List, Optional
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

# Phase 47.9 (U8): file-ownership contract. CodeGenerationEngine owns page
# modules and the application entry; the rendering provider owns every other
# scaffold file it emits. Exactly one owner per generated file.
CODE_GENERATION_OWNED_PATHS = ("src/App.jsx",)
CODE_GENERATION_OWNED_PREFIXES = ("src/pages/",)

_SPLINE_URL_PATTERN = re.compile(
    r'(?:https://[^\s"\'<>]+\.(?:splinecode|spline)\b|[A-Za-z0-9_\-./]+\.splinecode\b)'
)


def client_api_binding(artifact: WebsiteGenerationArtifact) -> Dict[str, Any]:
    """Phase 47.36: deterministic frontend↔Client-API binding contract.

    Derived ONLY from the Phase 47.32 Project Capability Contract on the
    artifact (platform-owned, no LLM): a binding is emitted for exactly the
    capabilities the Phase 47.35 Client API supports (`products`, `leads`).
    Pure transport — this engine only moves the artifact's existing
    capability decision to the rendering provider through the established
    process_blueprint kwargs→output_config path (spline_scene_url precedent).
    """
    capabilities = list(getattr(artifact.requirements, 'capabilities', None) or [])
    binding = {
        'enabled': False,
        'products': 'products' in capabilities,
        'leads': 'leads' in capabilities,
    }
    binding['enabled'] = bool(binding['products'] or binding['leads'])
    return binding


class DesignOrchestrationEngine(BaseGenerationEngine):
    """
    Phase 47.9 (U8): pipeline-to-renderer bridge and renderer-selection owner.

    Receives the existing design/rendering blueprint, resolves the rendering
    provider through the canonical RenderingProviderRegistry via the existing
    DesignOrchestrator, executes the provider through the unified
    process_blueprint contract, validates the provider result contract, and
    stores provider identity/output in artifact.design.

    Ownership (ADR-0074): RenderingProviderRegistry / DesignOrchestrator own
    renderer selection, renderer scaffold, renderer dependencies and renderer
    validation. CodeGenerationEngine enriches pages but never regenerates the
    renderer scaffold. WorkspaceGeneratorEngine materializes provider output.
    """

    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing DesignOrchestrationEngine (renderer ownership bridge)...")

        modular_blueprint_dict = artifact.generation_metadata.get("modular_blueprint", {})

        from odoo.addons.nexora_studio.services.design.providers.provider_registry import RenderingProviderRegistry

        # 1. Determine the renderer through the canonical existing registry.
        strategy = str(
            (modular_blueprint_dict.get("rendering") or {}).get("strategy", "none")
        ).lower().strip() or "none"
        provider_id = RenderingProviderRegistry.resolve_provider_id(strategy)

        env = getattr(runtime, "env", None)
        if env is None:
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                metadata={"rendering_provider": provider_id, "rendering_strategy": strategy},
                error="DesignOrchestrationEngine requires an explicit Odoo environment to route through nexora.design_orchestrator.",
            )

        # 2. Collect provider inputs from existing artifact structures only.
        selected_components = self._collect_selected_components(artifact)
        spline_scene_url = self._resolve_spline_scene_url(artifact)
        # Phase 47.36: transport the capability-derived Client API binding
        # contract to the provider (same kwargs→output_config precedent).
        client_api = client_api_binding(artifact)
        renderer_assets = self._collect_renderer_assets(artifact)

        # Phase 47.23 (ADR-0075): the ThemeEngine output (semantic palette +
        # webfonts) reaches the rendering provider through the SAME
        # blueprint this bridge already dispatches — the provider's
        # token_set contract. ThemeEngine remains the palette owner; this
        # engine only transports it.
        blueprint = dict(modular_blueprint_dict)
        blueprint['token_set'] = self._theme_token_set(artifact, blueprint)

        # 3. Call the existing DesignOrchestrator (canonical routing layer),
        #    which resolves the provider via RenderingProviderRegistry and
        #    dispatches the unified process_blueprint contract.
        try:
            design_orchestrator = env['nexora.design_orchestrator']
            provider_result = design_orchestrator.execute_operation(
                'process_blueprint',
                provider_name=provider_id,
                blueprint=blueprint,
                rendering_strategy=strategy,
                selected_components=selected_components,
                spline_scene_url=spline_scene_url,
                renderer_assets=renderer_assets,
                client_api=client_api,
            )
        except Exception as e:
            _logger.error("DesignOrchestrationEngine provider execution failed: %s", e, exc_info=True)
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                metadata={"rendering_provider": provider_id, "rendering_strategy": strategy},
                error=f"Design orchestration failed for provider '{provider_id}': {e}",
            )

        # 4. Validate the provider result contract.
        contract_error = self._validate_provider_result(provider_result, provider_id)
        if contract_error:
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                metadata={"rendering_provider": provider_id, "rendering_strategy": strategy},
                error=contract_error,
            )

        # 5. Store provider identity/output in the existing artifact.design
        #    structure, preserving dependencies and project structure.
        project_structure = provider_result.get("project_structure") or {}
        provider_owned = [
            path for path in sorted(project_structure)
            if path not in CODE_GENERATION_OWNED_PATHS
            and not path.startswith(CODE_GENERATION_OWNED_PREFIXES)
        ]
        design_payload: Dict[str, Any] = {
            "status": "completed",
            "provider": provider_id,
            "strategy": strategy,
            "project_structure": project_structure,
            "dependencies": provider_result.get("dependencies") or {},
            "validation": provider_result.get("validation") or {},
            "provider_metadata": provider_result.get("metadata") or {},
            "file_ownership": {
                "provider": provider_id,
                "provider_owned_files": provider_owned,
                "code_generation_owned": list(CODE_GENERATION_OWNED_PATHS) + ["src/pages/*"],
            },
            "blueprint": modular_blueprint_dict,
        }

        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(design=design_payload),
            metadata={
                "design_orchestrator": "executed",
                "rendering_provider": provider_id,
                "rendering_strategy": strategy,
                "rendering_files_generated": len(project_structure),
            },
            error=None,
        )

    # ------------------------------------------------------------------
    # Input collection (existing artifact structures only)
    # ------------------------------------------------------------------

    @staticmethod
    def _theme_token_set(artifact: WebsiteGenerationArtifact,
                         blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 47.23 (ADR-0075): transport the ThemeEngine palette/fonts
        into the provider's token_set contract (the dict RenderProject
        already maps). Preserves any existing token content; theme tokens
        are additive so deterministic provider defaults only apply when the
        theme is absent."""
        token_set = dict(blueprint.get('token_set') or {})
        try:
            tokens = list(token_set.get('tokens') or [])
        except Exception:
            tokens = []
        theme = getattr(artifact, 'theme', None)
        if theme is not None:
            serif_hint = 'Georgia, serif' if any(
                kw in str(getattr(theme, 'font_heading', 'Inter')).lower()
                for kw in ('playfair', 'lora', 'cormorant')
            ) else 'system-ui, sans-serif'
            for key, name, ttype, value in (
                ('background', 'background', 'color', None),
                ('foreground', 'foreground', 'color', None),
                ('primary', 'primary', 'color', None),
                ('primary_foreground', 'primary-foreground', 'color', None),
                ('secondary', 'secondary', 'color', None),
                ('accent', 'accent', 'color', None),
                ('border', 'border', 'color', None),
                ('muted', 'muted', 'color', None),
                ('card', 'card', 'color', None),
            ):
                color = (getattr(theme, 'colors', None) or {}).get(key)
                if color:
                    tokens.append({
                        'name': name, 'token_type': ttype,
                        'value': str(color), 'category': 'color',
                    })
            # Legacy alias so existing scaffold consumers resolve.
            fg = (getattr(theme, 'colors', None) or {}).get('foreground')
            if fg:
                tokens.append({'name': 'text', 'token_type': 'color',
                               'value': str(fg), 'category': 'color'})
            font_heading = str(getattr(theme, 'font_heading', '') or 'Inter').strip() or 'Inter'
            font_body = str(getattr(theme, 'font_body', '') or 'Inter').strip() or 'Inter'
            tokens.append({'name': 'heading', 'token_type': 'font',
                           'value': "'%s', %s" % (font_heading, serif_hint),
                           'category': 'typography'})
            tokens.append({'name': 'body', 'token_type': 'font',
                           'value': "'%s', system-ui, sans-serif" % font_body,
                           'category': 'typography'})
        token_set['tokens'] = tokens
        return token_set

    @staticmethod
    def _collect_selected_components(artifact: WebsiteGenerationArtifact) -> List[Dict[str, Any]]:
        """Source-backed ComponentTree nodes produced by the U6/U7 path."""
        nodes = []
        for node in getattr(artifact.component_tree, "nodes", []) or []:
            if not isinstance(node, dict):
                continue
            metadata = node.get('metadata') or {}
            if metadata.get('from_source'):
                nodes.append(node)
        return nodes

    @staticmethod
    def _resolve_spline_scene_url(artifact: WebsiteGenerationArtifact) -> str:
        """Deterministic scene-reference extraction from existing requirement
        text or an explicit generation_metadata override. Never fabricated."""
        explicit = str(artifact.generation_metadata.get('spline_scene_url') or '').strip()
        if explicit:
            return explicit
        raw_input = str(getattr(artifact.requirements, 'raw_input', '') or '')
        match = _SPLINE_URL_PATTERN.search(raw_input)
        return match.group(0) if match else ''

    @staticmethod
    def _collect_renderer_assets(artifact: WebsiteGenerationArtifact) -> List[Dict[str, Any]]:
        """Flatten existing DesignAsset-contract buckets (U7) for renderer use.
        U8 only represents references already present in the artifact — no
        asset acquisition happens here."""
        assets: List[Dict[str, Any]] = []
        for bucket in ('images', 'icons', 'fonts'):
            for entry in getattr(artifact.assets, bucket, []) or []:
                if isinstance(entry, dict):
                    assets.append(entry)
        return assets

    # ------------------------------------------------------------------
    # Provider result contract validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_provider_result(provider_result: Any, provider_id: str) -> Optional[str]:
        if not isinstance(provider_result, dict):
            return f"Provider '{provider_id}' returned an invalid result contract (expected dict)."
        if provider_result.get("status") != "success":
            errors = provider_result.get("errors") or []
            detail = ' | '.join(str(e) for e in errors) if errors else 'unknown provider error'
            return f"Provider '{provider_id}' generation failed: {detail}"
        project_structure = provider_result.get("project_structure")
        if not isinstance(project_structure, dict) or not project_structure:
            return f"Provider '{provider_id}' produced no project structure."
        if str(provider_result.get("provider") or '') != provider_id:
            return (
                f"Provider identity mismatch: expected '{provider_id}', "
                f"got '{provider_result.get('provider')}'."
            )
        validation = provider_result.get("validation") or {}
        if validation and not validation.get("valid", False):
            errors = validation.get("errors") or []
            detail = ' | '.join(str(e) for e in errors) if errors else 'invalid provider output'
            return f"Provider '{provider_id}' output failed validation: {detail}"
        return None
