import logging
import os
from datetime import datetime, timezone
from typing import Any, List, Dict
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, ValidationReport

from odoo.addons.nexora_studio.services.design.design_blueprint import DesignBlueprint

_logger = logging.getLogger(__name__)

# Phase 47.13 (U9.4): per-route issue caps so a noisy page cannot explode the
# validation report; the full uncapped evidence is always preserved in the
# browser_validation evidence dict.
_BROWSER_ISSUE_CAP = 10


class ValidationEngine(BaseGenerationEngine):
    def __init__(self, orchestrator, phase: str = 'full'):
        super().__init__(orchestrator)
        # Phase 47.13 (U9.4): the SAME validation owner runs twice in the
        # pipeline. 'full' (pre-preview): design / SEO / dynamic / build
        # acceptance. 'browser' (post-preview, after PREVIEW_READY): browser
        # validation through the canonical nexora.provider.playwright owner.
        # No second validation engine class exists.
        if phase not in ('full', 'browser'):
            raise ValueError(f"Unknown ValidationEngine phase: {phase}")
        self.phase = phase

    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        if self.phase == 'browser':
            return self._execute_browser_validation(artifact, runtime)
        _logger.info("Executing ValidationEngine (Delegating to DesignOrchestrator)...")
        
        issues = []
        a11y_score = 100
        seo_score = 100
        perf_score = 100
        
        # 1. Orchestrate Design Validation
        try:
            # We convert our Blueprint payload into a DesignBlueprint for the validator
            bp_dict = {
                "project_name": artifact.requirements.domain or 'unknown',
                "project_id": artifact.requirements.domain or 'unknown',
                "pages": []
            }
            component_hierarchy = artifact.architecture.component_hierarchy if hasattr(artifact.architecture, "component_hierarchy") else {}
            for comp_id, comp_data in component_hierarchy.items():
                if comp_data.get("type") != "page": continue
                path = comp_data.get("path", "/")
                sections = comp_data.get("sections", ["Hero", "Content"])
                
                page_dict = {
                    "path": path,
                    "title": path.strip('/') or 'Home',
                    "sections": []
                }
                for sec in sections:
                    page_dict["sections"].append({
                        "id": f"sec_{sec}",
                        "name": sec,
                        "components": [{"id": f"comp_{sec}", "name": sec, "category": sec}]
                    })
                bp_dict["pages"].append(page_dict)
                
            bp = DesignBlueprint.from_dict(bp_dict)
            
            # Delegate to canonical orchestrator
            design_val = runtime.env['nexora.design_orchestrator'].validate_design(bp)
            
            issues.extend(design_val.get("issues", []))
            scores = design_val.get("scores", {})
            a11y_score = scores.get("accessibility", a11y_score)
            perf_score = scores.get("performance", perf_score)
            
        except Exception as e:
            _logger.error(f"Design Validation integration failed: {e}")
            issues.append({"type": "error", "message": f"Design validation failed: {str(e)}", "category": "system"})

        # 2. Basic SEO Validation
        for path, page in artifact.content.pages.items():
            seo = page.get("seo", {})
            if not seo.get("title"):
                issues.append({"type": "error", "message": f"Page {path} is missing SEO title.", "category": "seo"})
                seo_score -= 15
            if not seo.get("description"):
                issues.append({"type": "error", "message": f"Page {path} is missing SEO description.", "category": "seo"})
                seo_score -= 15
        # 3. Dynamic Validation (via Capability Router)
        workspace_path = artifact.workspace.project_path
        if workspace_path and os.path.exists(workspace_path):
            try:
                _logger.info("Running dynamic validation pipeline...")
                if hasattr(runtime, 'orchestrator'):
                    context_overrides = {
                        "shared_variables": {"workspace_path": workspace_path},
                        "artifacts": {"landing_page_html": artifact.content.pages.get("/", {}).get("html", "")}
                    }
                    
                    trace = runtime.orchestrator.execute_plan(
                        "Validate the generated website workspace",
                        target_outputs=["validation_report"],
                        context_overrides=context_overrides
                    )
                    
                    if trace.steps_failed:
                        issues.append({"type": "error", "message": f"Dynamic validation step(s) failed: {trace.steps_failed}", "category": "validation"})
                else:
                    _logger.warning("Production orchestrator not available for dynamic validation.")
            except Exception as e:
                issues.append({"type": "error", "message": f"Dynamic validation execution failed: {e}", "category": "validation"})
                
        # 4. Build Acceptance (Phase 47.11 / U9.2)
        # Project dependency installation + authoritative production build, run
        # inside the managed workspace through the canonical install/build owner.
        # A failed install/build is a failed validation/build stage: it is never
        # converted into success. When no real workspace was materialized (e.g.
        # mock-driven pipeline tests) the step is skipped, not failed.
        build_evidence = self._run_build_acceptance(artifact, runtime, issues)

        a11y_score = max(0, a11y_score)
        seo_score = max(0, seo_score)
        perf_score = max(0, perf_score)

        passed = len([i for i in issues if i["type"] == "error"]) == 0

        model = ValidationReport(
            passed=passed,
            accessibility_score=a11y_score,
            seo_score=seo_score,
            performance_score=perf_score,
            issues=issues,
            build_acceptance=build_evidence
        )
        metadata = {
            "validation_issues_count": len(issues),
            "build_acceptance": build_evidence,
        }
        # Phase 47.40: the ThemeEngine visual fingerprint rides the
        # existing validation evidence path (QA/reproducibility) — no
        # separate registry, no arbitrary diversity score.
        fingerprint = (getattr(artifact, 'generation_metadata', None)
                       or {}).get('visual_fingerprint')
        if isinstance(fingerprint, dict):
            metadata["visual_fingerprint"] = dict(fingerprint)
        if build_evidence.get("failed"):
            return EngineExecutionResult(
                success=False,
                artifact=artifact.evolve(validation=model),
                metadata=metadata,
                error=build_evidence.get("error") or "Build acceptance failed",
            )
        return EngineExecutionResult(success=True, artifact=artifact.evolve(validation=model), metadata=metadata, error=None)

    def _run_build_acceptance(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime', issues: List[Dict]):
        """Phase 47.11 / U9.2: install + production build acceptance.

        Returns a structured evidence dict:
          ran, skipped, skip_reason, install, build, failed, error,
          build_output_path, exit_code.
        On install/build failure an error issue is appended so the validation
        report is marked failed, and ``failed`` is set so the owning stage fails.
        """
        evidence = {
            "ran": False,
            "skipped": False,
            "skip_reason": None,
            "install": None,
            "build": None,
            "failed": False,
            "error": None,
            "build_output_path": None,
            "exit_code": None,
        }
        workspace_path = getattr(artifact.workspace, "project_path", None)
        if not workspace_path or not os.path.isdir(workspace_path):
            evidence["skipped"] = True
            evidence["skip_reason"] = "no_materialized_workspace"
            return evidence

        try:
            installer = runtime.env["nexora.dependency_installer_service"]
        except Exception as e:
            evidence["failed"] = True
            evidence["error"] = f"Build owner unavailable: {e}"
            issues.append({"type": "error", "message": evidence["error"], "category": "build"})
            return evidence

        evidence["ran"] = True

        install_res = installer.install_project(workspace_path)
        evidence["install"] = install_res
        evidence["exit_code"] = install_res.get("exit_code")
        if not install_res.get("success"):
            evidence["failed"] = True
            evidence["error"] = (
                f"Dependency installation failed (exit={install_res.get('exit_code')}, "
                f"error={install_res.get('error')}): {str(install_res.get('stderr') or '')[:600]}"
            )
            issues.append({"type": "error", "message": evidence["error"], "category": "build"})
            return evidence

        build_res = installer.build_project(workspace_path)
        evidence["build"] = build_res
        evidence["exit_code"] = build_res.get("exit_code")
        evidence["build_output_path"] = build_res.get("dist_path")
        if not build_res.get("success"):
            evidence["failed"] = True
            evidence["error"] = (
                f"Production build failed (exit={build_res.get('exit_code')}, "
                f"error={build_res.get('error')}, dist_present={build_res.get('dist_present')}): "
                f"{str(build_res.get('stderr') or '')[:600]}"
            )
            issues.append({"type": "error", "message": evidence["error"], "category": "build"})
        return evidence

    # =================================================================
    # Phase 47.13 (U9.4) — Browser validation (post-preview pass)
    #
    # Ownership contract:
    #   PreviewService            -> preview process / URL / health
    #   nexora.provider.playwright -> browser process / navigation / console /
    #                                 network / screenshots
    #   ValidationEngine (here)   -> validation interpretation, issues and
    #                                 acceptance metadata
    # The browser is never launched before preview health succeeds, and the
    # preview URL is always consumed from the existing U9.3 preview metadata
    # contract (nexora.preview_runtime) — never reconstructed, hardcoded or
    # served from a second process.
    # =================================================================

    def _execute_browser_validation(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ValidationEngine browser phase (Phase 47.13 / U9.4)...")
        prior_report = artifact.validation
        prior_issues = list(prior_report.issues or [])
        issues = list(prior_issues)

        evidence = {
            "ran": False,
            "skipped": False,
            "skip_reason": None,
            "failed": False,
            "error": None,
            "status": None,
            "preview_url": None,
            "preview_launcher": None,
            "preview_health": None,
            "preview_process_id": None,
            "preview_allocated_port": None,
            "routes": [],
            "console_errors": [],
            "console_warnings": [],
            "console_messages": [],
            "page_errors": [],
            "network_failures": [],
            "http_errors": [],
            "navigation_errors": [],
            "screenshots": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        def _finish(success: bool):
            # Phase 47.15 (U9.6): when browser validation was genuinely
            # attempted (ran=True), the FINAL ACCEPTANCE decision is computed
            # from the existing evidence and becomes authoritative — the stage
            # succeeds only if the final gate accepts. Skip paths (mock
            # pipelines) never compute a final decision.
            final = None
            final_success = success
            if evidence.get("ran"):
                blocking = [i for i in issues if i["type"] == "error"]
                warnings = [i for i in issues if i["type"] == "warning"]
                final = self._compute_final_acceptance(
                    prior_report.build_acceptance or {}, evidence, renderer_id,
                    renderer_identity_raw, blocking, warnings)
                evidence["final_acceptance"] = final
                final_success = bool(final["accepted"])
                if not final_success:
                    evidence["failed"] = True
                    if evidence.get("status") != "failed":
                        evidence["status"] = "failed"
                    if not evidence.get("error"):
                        evidence["error"] = "Final acceptance failed"
            passed = final_success
            model = ValidationReport(
                passed=passed,
                accessibility_score=prior_report.accessibility_score,
                seo_score=prior_report.seo_score,
                performance_score=prior_report.performance_score,
                issues=issues,
                build_acceptance=prior_report.build_acceptance,
                browser_validation=evidence,
                final_acceptance=final or {},
            )
            metadata = {
                "validation_issues_count": len(issues),
                "build_acceptance": prior_report.build_acceptance,
                "browser_validation": evidence,
                "final_acceptance": final or {},
            }
            return EngineExecutionResult(
                success=final_success,
                artifact=artifact.evolve(validation=model),
                metadata=metadata,
                error=evidence.get("error"),
            )

        def _skip(reason: str):
            evidence["skipped"] = True
            evidence["skip_reason"] = reason
            return _finish(True)

        def _fail(error: str):
            evidence["failed"] = True
            evidence["error"] = error
            evidence["status"] = "failed"
            issues.append({"type": "error", "message": error, "category": "browser"})
            return _finish(False)

        # --- Guards: mock pipelines (no env/session/workspace) skip, they
        # never fail. Real generation failures below always fail. ---
        try:
            env = getattr(runtime, "env", None)
        except Exception:
            env = None
        if env is None:
            return _skip("no_odoo_env")

        build_acceptance = prior_report.build_acceptance or {}
        if build_acceptance.get("failed"):
            return _skip("build_acceptance_failed")
        if not build_acceptance.get("ran"):
            return _skip(
                "build_acceptance_skipped"
                if build_acceptance.get("skipped")
                else "build_acceptance_not_ran"
            )

        workspace_path = getattr(getattr(artifact, "workspace", None), "project_path", None)
        if not workspace_path or not os.path.isdir(workspace_path):
            return _skip("no_materialized_workspace")

        session = self._resolve_session(env, runtime)
        if session is None:
            return _skip("no_session")

        # Past this point browser validation is genuinely attempted (ran=True):
        # any failure below is a real, machine-readable browser-validation
        # failure — never a silent skip and never a false success.
        evidence["ran"] = True

        # --- Phase 47.14 (U9.5): renderer identity comes from the EXISTING
        # artifact.design provider contract (set by DesignOrchestrationEngine
        # from the canonical RenderingProviderRegistry identity). Never
        # inferred from file names, package names or source inspection.
        # Unknown/missing identity -> not applicable for the renderer probe
        # (U9.5); the U9.6 final acceptance gate fails on it (no guessing).
        design = getattr(artifact, "design", None) or {}
        renderer_id = str(design.get("provider") or "").strip()
        # Keep the raw identity for the final gate: an absent value is
        # renderer_identity_missing, an unknown non-empty value is
        # renderer_identity_unknown. Never guessed either way.
        renderer_identity_raw = renderer_id
        if renderer_id not in ("react", "react_three_fiber", "spline"):
            renderer_id = None

        # --- Precondition: a REAL healthy preview from the existing U9.3
        # preview metadata contract. No healthy preview => browser validation
        # fails clearly and the browser provider is never launched. ---
        preview_service = env["nexora.preview_service"]
        runtime_rec = env["nexora.runtime"].search([
            ("builder_session_id", "=", session.id),
            ("runtime_type", "=", "preview"),
        ], limit=1)
        preview_rt = None
        if runtime_rec:
            preview_rt = env["nexora.preview_runtime"].search(
                [("runtime_id", "=", runtime_rec.id)], limit=1)
        preview_url = getattr(preview_rt, "preview_url", None) if preview_rt else None
        process_id = getattr(preview_rt, "process_id", 0) if preview_rt else 0
        if not runtime_rec or not preview_rt or not preview_url or not process_id or process_id <= 0:
            return _fail("preview_unavailable")
        evidence["preview_url"] = preview_url
        evidence["preview_launcher"] = preview_rt.launcher_type
        evidence["preview_process_id"] = getattr(preview_rt, "process_id", None)
        evidence["preview_allocated_port"] = getattr(preview_rt, "allocated_port", None)

        health = preview_service.check_health(runtime_rec)
        evidence["preview_health"] = health
        if health != "healthy":
            return _fail(f"preview_unhealthy (health={health})")

        # --- Routes: reuse existing generated route metadata (architecture
        # page components + content pages). No second route registry. ---
        routes = self._collect_routes(artifact)

        # --- Browser validation through the canonical provider abstraction.
        # ValidationEngine never touches Playwright or raw process calls directly. ---
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest
        evidence_dir = os.path.join(workspace_path, ".nexora", "browser_evidence")
        payload = {
            "action": "validate",
            "url": preview_url,
            "routes": routes,
            "timeout_ms": 30000,
            "evidence_dir": evidence_dir,
        }
        if renderer_id:
            # U9.5 renderer runtime probe through the SAME validate action.
            payload["renderer"] = renderer_id
        request = ProviderExecutionRequest(
            namespace="nexora.provider.playwright",
            payload=payload,
            timeout=180.0,
        )
        try:
            provider = env["nexora.provider.playwright"]
            result = provider.execute(request)
        except Exception as e:
            return _fail(f"Browser validation execution failed: {e}")

        data = result.data if isinstance(result.data, dict) else {}
        evidence["routes"] = data.get("routes") or []
        evidence["console_errors"] = data.get("console_errors") or []
        evidence["console_warnings"] = data.get("console_warnings") or []
        evidence["console_messages"] = data.get("console_messages") or []
        evidence["page_errors"] = data.get("page_errors") or []
        evidence["network_failures"] = data.get("network_failures") or []
        evidence["http_errors"] = data.get("http_errors") or []
        evidence["navigation_errors"] = data.get("navigation_errors") or []
        evidence["screenshots"] = data.get("screenshots") or []

        # --- Phase 47.14 (U9.5): renderer runtime evidence lives INSIDE the
        # existing browser_validation contract. React / unknown identity ->
        # not applicable. R3F/Spline REQUIRE provider probe evidence; a
        # missing evidence document is a real failure — never a silent pass.
        renderer_ev = data.get("renderer_runtime")
        if renderer_id in (None, "react"):
            evidence["renderer_runtime"] = {
                "provider": renderer_id,
                "status": "not_applicable",
                "reason": (
                    "react_has_no_renderer_runtime_contract"
                    if renderer_id == "react"
                    else "renderer_identity_unavailable"
                ),
            }
        elif isinstance(renderer_ev, dict):
            evidence["renderer_runtime"] = renderer_ev
        else:
            evidence["renderer_runtime"] = {
                "provider": renderer_id,
                "status": "failed",
                "errors": ["renderer_runtime_evidence_missing"],
                "runtime_marker": None,
                "diagnostics": {},
            }

        # --- Phase 47.19 (Part D): bounded mobile-viewport validation.
        # Opt-in via the requirement model: when the brief declares a
        # responsive/mobile expectation (requirements.mobile_expected), the
        # same provider/validate contract runs once more for the home route
        # at a mobile viewport. Mobile evidence is OBSERVABLE-only: it lives
        # inside evidence["mobile"] and never produces acceptance issues (the
        # U9.6 technical acceptance contract on the desktop path is untouched).
        mobile_required = bool(getattr(artifact.requirements, "mobile_expected", False))
        if mobile_required and result.success:
            mobile_request = ProviderExecutionRequest(
                namespace="nexora.provider.playwright",
                payload={
                    "action": "validate",
                    "url": preview_url,
                    "routes": ["/"],
                    "timeout_ms": 20000,
                    "evidence_dir": evidence_dir,
                    "viewport": {"width": 375, "height": 812},
                },
                timeout=90.0,
            )
            try:
                mobile_result = provider.execute(mobile_request)
                mobile_data = mobile_result.data if isinstance(mobile_result.data, dict) else {}
                evidence["mobile"] = {
                    "ran": True,
                    "viewport": {"width": 375, "height": 812},
                    "success": bool(mobile_result.success),
                    "error": str(mobile_result.error)[:200] if mobile_result.error else None,
                    "status": mobile_data.get("status"),
                    "route_success": bool(
                        mobile_data.get("routes")
                        and (mobile_data["routes"] or [{}])[0].get("success")),
                    "console_errors": len(mobile_data.get("console_errors") or []),
                    "network_failures": len(mobile_data.get("network_failures") or []),
                    "http_errors": len(mobile_data.get("http_errors") or []),
                }
            except Exception as e:
                evidence["mobile"] = {
                    "ran": True,
                    "viewport": {"width": 375, "height": 812},
                    "success": False,
                    "error": str(e)[:200],
                }
        if not mobile_required:
            evidence.setdefault("mobile", {"ran": False,
                                           "reason": "mobile_not_requested"})

        if not result.success:
            diagnostics = data.get("error") or ""
            error = f"Browser validation failed: {result.error or 'unknown error'}"
            if diagnostics and str(diagnostics) not in error:
                error += f" | {str(diagnostics)[:400]}"
            return _fail(error)

        # --- Interpretation through the EXISTING validation severity
        # contract: type=error issues block, type=warning issues are
        # observable and never block by themselves. No second severity model.
        self._map_browser_issues(issues, evidence)
        self._map_renderer_issues(issues, evidence)

        blocking = [i for i in issues if i["type"] == "error" and i.get("category") == "browser"]
        if blocking:
            evidence["failed"] = True
            evidence["status"] = "failed"
            evidence["error"] = (
                f"Browser validation failed with {len(blocking)} blocking browser issue(s): "
                f"{blocking[0]['message'][:300]}"
            )
            return _finish(False)

        evidence["status"] = "healthy"
        return _finish(True)

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

    @staticmethod
    def _collect_routes(artifact: WebsiteGenerationArtifact) -> List[str]:
        """Reuse existing generated route metadata: architecture page
        components and content page paths. Home route always first."""
        routes = ["/"]

        def _add(path):
            p = str(path or "").strip()
            if not p:
                return
            if not p.startswith("/"):
                p = "/" + p
            p = p.rstrip("/") or "/"
            if p not in routes:
                routes.append(p)

        try:
            for path in (getattr(artifact.content, "pages", None) or {}):
                _add(path)
        except Exception:
            pass
        try:
            hierarchy = getattr(artifact.architecture, "component_hierarchy", None) or {}
            for _comp_id, comp in hierarchy.items():
                if isinstance(comp, dict) and comp.get("type") == "page":
                    _add(comp.get("path"))
        except Exception:
            pass
        return routes

    @staticmethod
    def _map_browser_issues(issues: List[Dict], evidence: Dict):
        """Map browser evidence into the existing validation issue contract.

        Blocking (type=error):
          * navigation failure / timeout / non-successful route
          * uncaught page exceptions
          * console errors
          * transport (requestfailed) network failures
          * HTTP >= 500 responses and main-document HTTP >= 400
        Observable, non-blocking (type=warning):
          * console warnings
          * sub-resource HTTP 4xx responses
        Warnings never fail validation by themselves.
        """
        def _capped(items):
            return list(items)[:_BROWSER_ISSUE_CAP]

        for route_ev in evidence.get("routes") or []:
            route = route_ev.get("route")
            if route_ev.get("error"):
                issues.append({
                    "type": "error",
                    "message": (
                        f"Browser navigation failed for route '{route}' "
                        f"(status={route_ev.get('status')}): {route_ev.get('error')}"
                    )[:600],
                    "category": "browser",
                })
            for page_error in _capped(route_ev.get("page_errors") or []):
                issues.append({
                    "type": "error",
                    "message": f"Uncaught page exception on route '{route}': {page_error}"[:600],
                    "category": "browser",
                })
            for console_error in _capped(route_ev.get("console_errors") or []):
                issues.append({
                    "type": "error",
                    "message": f"Browser console error on route '{route}': {console_error.get('text')}"[:600],
                    "category": "browser",
                })
            for console_warning in _capped(route_ev.get("console_warnings") or []):
                issues.append({
                    "type": "warning",
                    "message": f"Browser console warning on route '{route}': {console_warning.get('text')}"[:600],
                    "category": "browser",
                })
            for net_failure in _capped(route_ev.get("network_failures") or []):
                issues.append({
                    "type": "error",
                    "message": (
                        f"Network request failed on route '{route}': "
                        f"{net_failure.get('url')} ({net_failure.get('failure')})"
                    )[:600],
                    "category": "browser",
                })
            for http_error in _capped(route_ev.get("http_errors") or []):
                status = http_error.get("status") or 0
                is_document = http_error.get("resource_type") in ("document", None)
                if status >= 500 or (is_document and status >= 400):
                    issues.append({
                        "type": "error",
                        "message": f"HTTP {status} response on route '{route}': {http_error.get('url')}"[:600],
                        "category": "browser",
                    })
                else:
                    issues.append({
                        "type": "warning",
                        "message": f"HTTP {status} response on route '{route}': {http_error.get('url')}"[:600],
                        "category": "browser",
                    })

    @staticmethod
    def _map_renderer_issues(issues: List[Dict], evidence: Dict):
        """Phase 47.14 (U9.5): map renderer runtime failures into the EXISTING
        validation issue contract (type=error -> blocking, category=browser).

        Renderer runtime failure (missing canvas, zero-size canvas, WebGL
        unavailable, R3F/Spline initialization failure, scene not loaded)
        blocks browser validation. SwiftShader / performance warnings are
        already observable console warnings under U9.4 semantics and never
        block by themselves. ``not_applicable`` (react / unknown identity)
        never produces an issue.
        """
        renderer_ev = evidence.get("renderer_runtime") or {}
        if renderer_ev.get("status") != "failed":
            return
        provider = renderer_ev.get("provider") or "unknown"
        for err in (renderer_ev.get("errors") or [])[:_BROWSER_ISSUE_CAP]:
            issues.append({
                "type": "error",
                "message": f"Renderer runtime validation failed ({provider}): {err}"[:600],
                "category": "browser",
            })

    @staticmethod
    def _compute_final_acceptance(
            build_acceptance: Dict,
            evidence: Dict,
            renderer_id: str,
            renderer_identity_raw: str,
            blocking_issues: List[Dict],
            warnings: List[Dict]) -> Dict[str, Any]:
        """Phase 47.15 (U9.6): ONE deterministic final acceptance decision.

        Pure / stateless: consumes ONLY existing evidence (build acceptance
        from the prior validation report, preview/browser/renderer evidence
        from this browser phase) and never executes infrastructure (no npm,
        no build, no preview start/stop, no Playwright launch, no connector /
        DB writes). Running it twice over the same evidence yields the same
        decision. The decision is reproducible from the stored evidence.

        Acceptance rule (spec §6 / §7):
          * build acceptance must pass (ran + not failed);
          * preview runtime must be healthy;
          * browser validation must pass;
          * renderer runtime must pass when renderer != react;
          * renderer == react is not_applicable and never blocks;
          * any existing blocking error issue fails final acceptance;
          * warnings never fail final acceptance;
          * missing/unknown renderer identity fails (never guessed).
        """
        final = {
            "status": "failed",
            "accepted": False,
            "build": {"status": "missing", "reason": "build_acceptance_missing"},
            "preview": {"status": "missing", "reason": "preview_evidence_missing"},
            "browser": {"status": "missing", "reason": "browser_validation_not_executed"},
            "renderer": {"status": "not_applicable", "reason": None},
            "blocking_issues": [],
            "warnings": [],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        gate_blocking: List[Dict] = []

        def _block(code: str, category: str, message: str):
            gate_blocking.append({
                "type": "error", "category": category, "code": code,
                "message": message[:600],
            })

        # --- Build acceptance (U9.2 evidence) ---------------------------
        ba = build_acceptance or {}
        if ba.get("failed"):
            final["build"] = {"status": "failed", "reason": "build_acceptance_failed",
                              "error": ba.get("error")}
            _block("build_acceptance_failed", "build",
                   ba.get("error") or "Build acceptance failed")
        elif not ba.get("ran"):
            final["build"] = {"status": "missing", "reason": "build_acceptance_not_ran"}
            _block("build_acceptance_not_ran", "build",
                   "Build acceptance was not executed (missing evidence)")
        else:
            final["build"] = {"status": "passed"}

        # --- Preview acceptance (U9.3 evidence recorded in this phase) ---
        preview_health = evidence.get("preview_health")
        if (not evidence.get("preview_url")
                or not evidence.get("preview_process_id")
                or preview_health != "healthy"):
            final["preview"] = {
                "status": "failed",
                "reason": "preview_acceptance_failed",
                "health": preview_health,
                "error": evidence.get("error"),
            }
            _block("preview_acceptance_failed", "preview",
                   evidence.get("error") or "Preview is not healthy or available")
        else:
            final["preview"] = {
                "status": "passed",
                "url": evidence.get("preview_url"),
                "launcher": evidence.get("preview_launcher"),
                "health": preview_health,
            }

        # --- Browser acceptance (U9.4 evidence) -------------------------
        if not evidence.get("ran"):
            final["browser"] = {"status": "missing",
                                "reason": "browser_validation_not_executed"}
            _block("browser_validation_not_executed", "browser",
                   "Browser validation was not executed")
        elif evidence.get("failed") or evidence.get("status") != "healthy":
            final["browser"] = {"status": "failed",
                                "reason": "browser_acceptance_failed",
                                "error": evidence.get("error")}
            _block("browser_acceptance_failed", "browser",
                   evidence.get("error") or "Browser validation failed")
        else:
            final["browser"] = {"status": "passed"}

        # --- Renderer acceptance (U9.5 evidence; identity from design) ---
        rr = evidence.get("renderer_runtime") or {}
        if renderer_id == "react":
            final["renderer"] = {
                "status": "not_applicable",
                "reason": "react_has_no_renderer_runtime_contract",
            }
        elif renderer_id == "react_three_fiber":
            r3f_ok = (
                isinstance(rr, dict)
                and rr.get("status") == "healthy"
                and rr.get("initialized") is True
                and rr.get("canvas_present") is True
                and bool(rr.get("canvas_width")) and rr.get("canvas_width") > 0
                and bool(rr.get("canvas_height")) and rr.get("canvas_height") > 0
                and rr.get("webgl_available") is True
            )
            if r3f_ok:
                final["renderer"] = {"status": "passed", "evidence_status": "healthy"}
            else:
                final["renderer"] = {
                    "status": "failed",
                    "reason": "renderer_acceptance_failed",
                    "evidence_status": (rr or {}).get("status"),
                    "errors": (rr or {}).get("errors"),
                }
                _block("renderer_acceptance_failed", "renderer",
                       "R3F renderer runtime was not accepted")
        elif renderer_id == "spline":
            spline_ok = (
                isinstance(rr, dict)
                and rr.get("status") == "healthy"
                and rr.get("initialized") is True
                and rr.get("scene_loaded") is True
            )
            if spline_ok:
                final["renderer"] = {"status": "passed", "evidence_status": "healthy"}
            else:
                final["renderer"] = {
                    "status": "failed",
                    "reason": "renderer_acceptance_failed",
                    "evidence_status": (rr or {}).get("status"),
                    "errors": (rr or {}).get("errors"),
                }
                _block("renderer_acceptance_failed", "renderer",
                       "Spline renderer runtime was not accepted")
        else:
            # Missing / unknown renderer identity -> fail; never guess and
            # never convert missing evidence into not_applicable.
            reason = ("renderer_identity_unknown" if renderer_identity_raw
                      else "renderer_identity_missing")
            final["renderer"] = {"status": "failed", "reason": reason}
            _block(reason, "renderer",
                   "Renderer identity is missing or unknown; cannot accept")

        # --- Aggregate blocking issues from the ACCEPTANCE layers only.
        # The final gate gates on build / preview / browser / renderer. Other
        # validation dimensions (seo / design / dynamic validation) remain
        # observable in the report but never gate acceptance — preserving the
        # pre-U9.6 pipeline behaviour where only build/browser gated.
        acceptance_blocking = [
            i for i in blocking_issues
            if i.get("category") in ("build", "preview", "browser", "renderer")
        ]
        final["blocking_issues"] = list(acceptance_blocking) + gate_blocking
        final["warnings"] = list(warnings)
        final["accepted"] = len(final["blocking_issues"]) == 0
        final["status"] = "accepted" if final["accepted"] else "failed"
        return final
