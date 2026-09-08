import logging
import os
import json
import base64
import uuid
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, PreviewArtifacts

_logger = logging.getLogger(__name__)

class PreviewEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing PreviewEngine (Canonical UCEL Architecture)...")
        
        # 1. Compile real component payload for the Preview Engine
        # We will pass the structured tree to be encoded for preview consumption.
        preview_payload = {
            "theme": artifact.theme.design_tokens if hasattr(artifact.theme, 'design_tokens') else {},
            "colors": artifact.theme.colors if hasattr(artifact.theme, 'colors') else {},
            "components": artifact.component_tree.nodes if hasattr(artifact.component_tree, 'nodes') else [],
            "content": artifact.content.pages if hasattr(artifact.content, 'pages') else []
        }
        
        # Serialize to JSON for preview injection
        preview_data = json.dumps(preview_payload)
        
        # 2. Generate multi-device base64 URIs natively to avoid provider bypass
        def _generate_b64_url(component_code: str, device: str) -> str:
            device_widths = {"desktop": "100%", "tablet": "768px", "mobile": "375px"}
            width = device_widths.get(device, "100%")
            html_wrapper = f"<html><body style='margin:0;padding:0;width:{width};'>{component_code}</body></html>"
            encoded = base64.b64encode(html_wrapper.encode('utf-8')).decode('utf-8')
            return f"data:text/html;base64,{encoded}"
        
        desktop_url = _generate_b64_url(preview_data, "desktop")
        tablet_url = _generate_b64_url(preview_data, "tablet")
        mobile_url = _generate_b64_url(preview_data, "mobile")
        
        model = PreviewArtifacts(
            desktop_url=desktop_url,
            tablet_url=tablet_url,
            mobile_url=mobile_url,
            dom_snapshot=preview_data
        )

        # 3. Development preview runtime (Phase 47.12 / U9.3)
        # Real preview startup belongs to the canonical nexora.preview_service
        # owner; this engine only consumes its truthful result after build
        # acceptance. The existing base64 preview-artifact behavior above is
        # preserved unchanged.
        preview_evidence = self._run_preview_runtime(artifact, runtime)
        metadata = {"preview_runtime": preview_evidence}
        if preview_evidence.get("failed"):
            return EngineExecutionResult(
                success=False,
                artifact=artifact.evolve(previews=model),
                metadata=metadata,
                error=preview_evidence.get("error") or "Preview startup failed",
            )
        return EngineExecutionResult(success=True, artifact=artifact.evolve(previews=model), metadata=metadata, error=None)

    def _run_preview_runtime(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime'):
        """Phase 47.12 / U9.3: start the real development preview through the
        canonical preview owner, only after build acceptance succeeded.

        Ordering guarantee: the pipeline runs ValidationEngine (install +
        production build + build-output verification) before this engine, and a
        failed build acceptance aborts the pipeline. As an explicit guard this
        engine never starts a preview unless the validation stage recorded
        truthful build-acceptance evidence that ran and did not fail.
        Unrelated validation issues (e.g. dynamic web-search steps) do not
        gate the preview; only build acceptance does.

        Evidence keys: ran, skipped, skip_reason, failed, error,
        preview_status, preview_launcher, preview_url, preview_host,
        preview_port, preview_pid, preview_health.
        """
        evidence = {
            "ran": False,
            "skipped": False,
            "skip_reason": None,
            "failed": False,
            "error": None,
            "preview_status": None,
            "preview_launcher": None,
            "preview_url": None,
            "preview_host": None,
            "preview_port": None,
            "preview_pid": None,
            "preview_health": None,
        }

        validation = getattr(artifact, "validation", None)
        build_acceptance = getattr(validation, "build_acceptance", None) or {}
        if build_acceptance.get("failed"):
            evidence["skipped"] = True
            evidence["skip_reason"] = "build_acceptance_failed"
            return evidence
        if not build_acceptance.get("ran"):
            evidence["skipped"] = True
            evidence["skip_reason"] = (
                "build_acceptance_skipped"
                if build_acceptance.get("skipped")
                else "build_acceptance_not_ran"
            )
            return evidence

        workspace_path = getattr(getattr(artifact, "workspace", None), "project_path", None)
        if not workspace_path or not os.path.isdir(workspace_path):
            evidence["skipped"] = True
            evidence["skip_reason"] = "no_materialized_workspace"
            return evidence

        try:
            env = getattr(runtime, "env", None)
        except Exception:
            env = None
        if env is None:
            evidence["skipped"] = True
            evidence["skip_reason"] = "no_odoo_env"
            return evidence

        session = PreviewEngine._resolve_session(env, runtime)
        if session is None:
            evidence["skipped"] = True
            evidence["skip_reason"] = "no_session"
            return evidence

        try:
            preview_service = env["nexora.preview_service"]
        except Exception as e:
            evidence["failed"] = True
            evidence["error"] = f"Preview owner unavailable: {e}"
            return evidence

        evidence["ran"] = True
        try:
            result = preview_service.start_workspace_preview(session, workspace_path)
        except Exception as e:
            evidence["failed"] = True
            evidence["error"] = f"Preview startup failed: {e}"
            return evidence

        evidence["preview_status"] = result.get("status")
        evidence["preview_launcher"] = result.get("launcher")
        evidence["preview_url"] = result.get("url")
        evidence["preview_host"] = result.get("host")
        evidence["preview_port"] = result.get("port")
        evidence["preview_pid"] = result.get("pid")
        evidence["preview_health"] = result.get("health")

        if result.get("status") != "healthy" or result.get("error"):
            evidence["failed"] = True
            evidence["error"] = result.get("error") or "Preview health check failed"
            diagnostics = result.get("diagnostics")
            if diagnostics:
                evidence["error"] += f" | {str(diagnostics)[:400]}"
        return evidence

    @staticmethod
    def _resolve_session(env, runtime):
        try:
            metadata = getattr(runtime, "metadata", None)
            session_id = int(str(getattr(metadata, "session_id", "") or ""))
        except (TypeError, ValueError):
            return None
        try:
            session = env["nexora.builder_session"].browse(session_id)
            return session if session.exists() else None
        except Exception:
            return None
