# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
import time
import json
import os
import tempfile

_logger = logging.getLogger(__name__)

# Phase 47.13 (U9.4): browser-validation script template for the canonical
# Playwright provider. Parameters are injected by replacing the single
# __U94_PARAMS_JSON__ sentinel with a repr-escaped JSON literal — never via
# str.format / f-string interpolation — so the many Python braces in the
# script are untouched and the generated script is deterministic and
# injection-safe. The script:
#   * launches headless Chromium (browser lifecycle owned here, closed in
#     finally on success, navigation failure, timeout and unexpected error);
#   * navigates each requested route against the supplied preview URL;
#   * captures console messages (type + text, error/warning/log/info/debug
#     kept distinct), uncaught page exceptions, transport request failures
#     and HTTP >= 400 responses per route;
#   * records navigation status, final URL, title and a screenshot per route;
#   * prints ONE JSON evidence document on stdout in every case (diagnostics
#     survive failure) and exits non-zero only for browser-level failures.
# Interpretation (severity / blocking) belongs to the ValidationEngine, not
# to this provider.
_VALIDATE_SCRIPT = '''
import json
import os
import sys
import tempfile
import time

PARAMS = json.loads(__U94_PARAMS_JSON__)


def _on_console(msg, ev):
    entry = {"type": msg.type, "text": msg.text[:500]}
    try:
        loc = msg.location
        if loc:
            location = {}
            if loc.get("url"):
                location["url"] = str(loc.get("url"))[:300]
            if loc.get("lineNumber") is not None:
                location["lineNumber"] = loc.get("lineNumber")
            if location:
                entry["location"] = location
    except Exception:
        pass
    entry["timestamp"] = time.time()
    ev["console_messages"].append(entry)
    if msg.type == "error":
        ev["console_errors"].append(entry)
    elif msg.type == "warning":
        ev["console_warnings"].append(entry)


def _on_response(resp, ev):
    try:
        if resp.status >= 400:
            ev["http_errors"].append({
                "url": resp.url[:500],
                "status": resp.status,
                "resource_type": resp.request.resource_type,
            })
    except Exception:
        pass


def _probe_renderer_runtime(page, provider, deadline):
    """Phase 47.14 (U9.5): browser-side renderer runtime probe.

    Reads the PROVIDER-OWNED window.__NEXORA_RENDERER_RUNTIME__ marker
    (set truthfully by the R3F onCreated / Spline onLoad lifecycles) with a
    bounded wait - never infinite polling - plus independent DOM/canvas/
    WebGL facts evaluated inside the actual page. The probe only READS
    runtime state; it never fabricates success. SwiftShader/software WebGL
    counts as functional WebGL availability.
    """
    result = {
        "provider": provider,
        "status": "not_probed",
        "initialized": None,
        "canvas_present": None,
        "canvas_width": None,
        "canvas_height": None,
        "webgl_available": None,
        "scene_loaded": None,
        "runtime_marker": None,
        "errors": [],
        "diagnostics": {},
    }
    if provider == "react":
        result["status"] = "not_applicable"
        return result

    # Bounded wait for the provider-owned runtime marker.
    marker = None
    remaining_s = max(0.0, deadline - time.time())
    wait_s = min(8.0, remaining_s)
    poll_deadline = time.time() + wait_s
    while time.time() < poll_deadline:
        try:
            marker = page.evaluate("() => (window.__NEXORA_RENDERER_RUNTIME__ || null)")
        except Exception:
            marker = None
        if marker:
            break
        time.sleep(0.25)
    if isinstance(marker, dict):
        result["runtime_marker"] = marker
        result["initialized"] = marker.get("initialized")
        result["scene_loaded"] = marker.get("scene_loaded")
    else:
        result["errors"].append("runtime_marker_missing")

    # Independent DOM / canvas / WebGL facts.
    facts = {}
    try:
        facts = page.evaluate(
            "() => {"
            "  const canvases = Array.from(document.querySelectorAll('canvas'));"
            "  const live = canvases.filter(function(c){return c.isConnected;});"
            "  const sized = live.filter(function(c){return c.width > 0 && c.height > 0;});"
            "  const c = sized[0] || live[0] || null;"
            "  let webgl = false;"
            "  try {"
            "    const probe = document.createElement('canvas');"
            "    webgl = !!(probe.getContext('webgl2') || probe.getContext('webgl'));"
            "  } catch (e) { webgl = false; }"
            "  return {"
            "    canvas_count: canvases.length,"
            "    live_canvas_count: live.length,"
            "    canvas_present: !!(c && c.isConnected),"
            "    canvas_width: c ? c.width : null,"
            "    canvas_height: c ? c.height : null,"
            "    webgl_available: webgl,"
            "  };"
            "}"
        ) or {}
    except Exception as e:
        result["errors"].append("renderer_probe_failed: " + str(e)[:300])
    result["diagnostics"] = facts
    result["canvas_present"] = facts.get("canvas_present")
    result["canvas_width"] = facts.get("canvas_width")
    result["canvas_height"] = facts.get("canvas_height")
    result["webgl_available"] = facts.get("webgl_available")

    if provider == "react_three_fiber":
        if result["canvas_present"] is not True:
            result["errors"].append("r3f_canvas_missing")
        if not (isinstance(result["canvas_width"], int) and result["canvas_width"] > 0):
            result["errors"].append("r3f_canvas_zero_width")
        if not (isinstance(result["canvas_height"], int) and result["canvas_height"] > 0):
            result["errors"].append("r3f_canvas_zero_height")
        if result["webgl_available"] is not True:
            result["errors"].append("webgl_unavailable")
        if isinstance(marker, dict):
            if marker.get("provider") != "react_three_fiber":
                result["errors"].append("runtime_marker_provider_mismatch")
            if marker.get("initialized") is not True:
                result["errors"].append("r3f_runtime_not_initialized")
            if marker.get("canvas") is not True:
                result["errors"].append("r3f_marker_canvas_false")
            if marker.get("webgl") is not True:
                result["errors"].append("r3f_marker_webgl_false")
    elif provider == "spline":
        if isinstance(marker, dict):
            if marker.get("provider") != "spline":
                result["errors"].append("runtime_marker_provider_mismatch")
            if marker.get("initialized") is not True:
                result["errors"].append("spline_runtime_not_initialized")
            if marker.get("scene_loaded") is not True:
                result["errors"].append("spline_scene_not_loaded")

    result["status"] = "failed" if result["errors"] else "healthy"
    return result


def capture_route(context, base_url, route, timeout_ms, evidence_dir, deadline, renderer=None, is_first_route=False, viewport=None):
    url = base_url + (route if route.startswith("/") else "/" + route)
    ev = {
        "route": route,
        "requested_url": url,
        "final_url": None,
        "status": None,
        "title": None,
        "success": False,
        "error": None,
        "console_messages": [],
        "console_errors": [],
        "console_warnings": [],
        "page_errors": [],
        "network_failures": [],
        "http_errors": [],
        "screenshot_captured": False,
        "screenshot_path": None,
        "timestamp": time.time(),
    }
    page = context.new_page()
    # Phase 47.19 (Part D): optional viewport simulation for mobile QA.
    # Default behavior is unchanged (default desktop viewport applies) when
    # no viewport override is requested.
    if viewport:
        try:
            width = int(viewport.get('width'))
            height = int(viewport.get('height'))
            if width > 0 and height > 0:
                page.set_viewport_size({'width': width, 'height': height})
                ev['viewport'] = {'width': width, 'height': height}
        except Exception:
            # An invalid viewport must not corrupt the validation result;
            # fall back to the default desktop viewport.
            pass
    try:
        page.on("console", lambda m: _on_console(m, ev))
        page.on("pageerror", lambda e: ev["page_errors"].append(str(e)[:500]))
        page.on("requestfailed", lambda r: ev["network_failures"].append({
            "url": r.url[:500],
            "failure": (r.failure or "")[:200] if r.failure else None,
            "resource_type": r.resource_type,
        }))
        page.on("response", lambda resp: _on_response(resp, ev))

        remaining_ms = max(1000, int((deadline - time.time()) * 1000))
        nav_timeout = min(timeout_ms, remaining_ms)
        try:
            resp = page.goto(url, wait_until="load", timeout=nav_timeout)
            ev["status"] = resp.status if resp is not None else None
        except Exception as e:
            ev["error"] = "navigation_failed: " + str(e)[:400]

        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        time.sleep(1.5)

        try:
            ev["final_url"] = page.url
        except Exception:
            pass
        try:
            ev["title"] = page.title()
        except Exception:
            pass

        try:
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in route.strip("/")) or "home"
            shot_path = os.path.join(evidence_dir, "route_" + safe_name + ".png")
            page.screenshot(type="png", path=shot_path)
            ev["screenshot_captured"] = True
            ev["screenshot_path"] = shot_path
        except Exception:
            ev["screenshot_captured"] = False

        # Phase 47.14 (U9.5): renderer runtime probe on the FIRST route -
        # under the existing engine route contract the home route is always
        # first, and the home route owns the renderer mount in every
        # generated app.
        if renderer and is_first_route:
            if ev["error"] is None:
                try:
                    ev["renderer_runtime"] = _probe_renderer_runtime(page, renderer, deadline)
                except Exception as e:
                    ev["renderer_runtime"] = {
                        "provider": renderer,
                        "status": "failed",
                        "errors": ["renderer_probe_error: " + str(e)[:300]],
                        "runtime_marker": None,
                        "diagnostics": {},
                    }
            else:
                ev["renderer_runtime"] = {
                    "provider": renderer,
                    "status": "failed",
                    "errors": ["renderer_probe_skipped_navigation_failed"],
                    "runtime_marker": None,
                    "diagnostics": {},
                }

        if ev["error"] is None:
            if ev["status"] is not None and ev["status"] < 400:
                ev["success"] = True
            elif ev["status"] is not None:
                ev["error"] = "http_status_" + str(ev["status"])
            else:
                ev["error"] = "no_navigation_response"
    finally:
        try:
            page.close()
        except Exception:
            pass
    return ev


def main():
    base_url = str(PARAMS.get("url") or "").rstrip("/")
    routes = PARAMS.get("routes") or ["/"]
    timeout_ms = int(PARAMS.get("timeout_ms") or 30000)
    budget_s = float(PARAMS.get("budget_s") or 120.0)
    renderer = str(PARAMS.get("renderer") or "").strip() or None
    # Phase 47.19 (Part D): optional viewport dict ({width, height}). Absent
    # => unchanged default desktop behavior.
    viewport = PARAMS.get("viewport") if isinstance(PARAMS.get("viewport"), dict) else None
    evidence_dir = PARAMS.get("evidence_dir") or tempfile.mkdtemp(prefix="nexora-u94-browser-")
    try:
        os.makedirs(evidence_dir, exist_ok=True)
    except Exception:
        evidence_dir = tempfile.mkdtemp(prefix="nexora-u94-browser-")

    out = {
        "action": "validate",
        "status": "completed",
        "base_url": base_url,
        "routes": [],
        "evidence_dir": evidence_dir,
        "timestamp": time.time(),
        "error": None,
    }
    deadline = time.time() + budget_s

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        out["status"] = "failed"
        out["error"] = "playwright_unavailable: " + str(e)[:300]
        print(json.dumps(out))
        sys.exit(1)

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                out["status"] = "failed"
                out["error"] = "browser_launch_failed: " + str(e)[:300]
                print(json.dumps(out))
                sys.exit(1)
            context = None
            try:
                context = browser.new_context()
                for route_idx, route in enumerate(routes):
                    if time.time() >= deadline:
                        out["routes"].append({
                            "route": route,
                            "requested_url": base_url + (route if route.startswith("/") else "/" + route),
                            "success": False,
                            "error": "budget_exceeded",
                        })
                        continue
                    out["routes"].append(
                        capture_route(
                            context, base_url, str(route), timeout_ms,
                            evidence_dir, deadline,
                            renderer if route_idx == 0 else None,
                            route_idx == 0, viewport,
                        )
                    )
            finally:
                if context is not None:
                    try:
                        context.close()
                    except Exception:
                        pass
                try:
                    browser.close()
                except Exception:
                    pass
                # Allow OS time to reap the browser process tree on Windows.
                time.sleep(1.0)
    except SystemExit:
        raise
    except Exception as e:
        out["status"] = "failed"
        out["error"] = "browser_error: " + str(e)[:300]
        print(json.dumps(out))
        # Allow OS time to reap any browser processes on Windows.
        time.sleep(1.0)
        sys.exit(1)

    console_errors = []
    console_warnings = []
    console_messages = []
    page_errors = []
    network_failures = []
    http_errors = []
    navigation_errors = []
    screenshots = []
    for route_ev in out["routes"]:
        console_errors.extend(route_ev.get("console_errors") or [])
        console_warnings.extend(route_ev.get("console_warnings") or [])
        console_messages.extend(route_ev.get("console_messages") or [])
        page_errors.extend(route_ev.get("page_errors") or [])
        network_failures.extend(route_ev.get("network_failures") or [])
        http_errors.extend(route_ev.get("http_errors") or [])
        if route_ev.get("error"):
            navigation_errors.append({
                "route": route_ev.get("route"),
                "error": route_ev.get("error"),
                "status": route_ev.get("status"),
            })
        if route_ev.get("screenshot_path"):
            screenshots.append(route_ev.get("screenshot_path"))

    out["console_errors"] = console_errors
    out["console_warnings"] = console_warnings
    out["console_messages"] = console_messages
    out["page_errors"] = page_errors
    out["network_failures"] = network_failures
    out["http_errors"] = http_errors
    out["navigation_errors"] = navigation_errors
    out["screenshots"] = screenshots

    # Phase 47.14 (U9.5): aggregate the renderer runtime probe from the first
    # (home) route evidence. Only present when a renderer was requested -
    # U9.4-only callers see the exact same output shape as before.
    if renderer:
        renderer_runtime = None
        for route_ev in out["routes"]:
            if isinstance(route_ev, dict) and route_ev.get("renderer_runtime"):
                renderer_runtime = route_ev["renderer_runtime"]
                break
        if renderer_runtime is None:
            if renderer == "react":
                renderer_runtime = {"provider": "react", "status": "not_applicable"}
            else:
                renderer_runtime = {
                    "provider": renderer,
                    "status": "failed",
                    "errors": ["renderer_probe_route_missing"],
                    "runtime_marker": None,
                    "diagnostics": {},
                }
        out["renderer_runtime"] = renderer_runtime
    out["success"] = bool(out["routes"]) and all(r.get("success") for r in out["routes"])
    print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
'''


class PlaywrightProvider(models.AbstractModel):
    _name = 'nexora.provider.playwright'
    _description = 'Canonical Playwright Provider'

    @api.model
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start_time = time.time()
        """
        Canonical execution interface for Playwright capabilities.
        Executes exclusively through ExecutionSandboxService.

        Supported actions:
          * snapshot  — existing single-page snapshot/screenshot contract.
          * validate  — Phase 47.13 (U9.4): multi-route browser validation
                        with console / page-error / network / HTTP-status
                        evidence against a supplied preview URL.
                        Phase 47.14 (U9.5): optional payload key
                        ``renderer`` ('react' | 'react_three_fiber' |
                        'spline') extends the SAME validate action with a
                        bounded browser-side renderer runtime probe that
                        reads the provider-owned
                        window.__NEXORA_RENDERER_RUNTIME__ marker plus
                        DOM/canvas/WebGL facts. React -> not_applicable.
        """
        try:
            sandbox = self.env['nexora.execution_sandbox_service']
        except KeyError:
            return ProviderExecutionResult(success=False, data=None, error=f"{self._description} failed: Sandbox Runtime unavailable.", execution_ms=(time.time()-start_time)*1000)
            
        action = request.payload.get('action')
        url = request.payload.get('url')
        
        if not action or not url:
            return ProviderExecutionResult(success=False, data=None, error="Playwright requires 'action' and 'url' arguments.", execution_ms=(time.time()-start_time)*1000)

        if action == 'validate':
            return self._execute_validate(sandbox, request, url, start_time)

        # Create a temporary python script to run playwright in the sandbox
        # This eliminates raw subprocess usage outside of the canonical sandbox layer.
        script_content = f'''
import sys
import json
import base64
from playwright.sync_api import sync_playwright

def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("{url}")
            
            result = {{}}
            if "{action}" == "snapshot":
                page.wait_for_load_state("networkidle", timeout=10000)
                
                content = page.content()
                title = page.title()
                current_url = page.url
                
                screenshot_bytes = page.screenshot(type="png")
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                result["status"] = "snapshot_taken"
                result["title"] = title
                result["url"] = current_url
                result["content_length"] = len(content)
                result["screenshot_base64_prefix"] = screenshot_b64[:30] + "... (truncated for logging)"
                result["screenshot_captured"] = True
            else:
                result["status"] = "unknown_action"
                
            browser.close()
            print(json.dumps(result))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        return self._run_script(sandbox, script_content, request, start_time)

    @api.model
    def _execute_validate(self, sandbox, request: ProviderExecutionRequest, url: str, start_time: float) -> ProviderExecutionResult:
        """Phase 47.13 (U9.4): browser validation through the same canonical
        sandbox boundary. The generated script owns the Chromium lifecycle;
        this provider never launches a browser directly."""
        routes = request.payload.get('routes') or ['/']
        routes = [str(r) for r in routes if str(r).strip()]
        if not routes:
            routes = ['/']
        timeout_ms = int(request.payload.get('timeout_ms') or 30000)
        sandbox_timeout = int(getattr(request, 'timeout', 0) or 120)
        sandbox_timeout = max(60, min(sandbox_timeout, 600))
        params = {
            'url': url,
            'routes': routes,
            'timeout_ms': timeout_ms,
            'budget_s': max(30.0, float(sandbox_timeout) - 10.0),
            'evidence_dir': request.payload.get('evidence_dir'),
            # Phase 47.14 (U9.5): optional renderer identity for the
            # browser-side runtime probe ('react' | 'react_three_fiber' |
            # 'spline'). Absent -> U9.4-only navigation/console/network.
            'renderer': request.payload.get('renderer'),
            # Phase 47.19 (Part D): optional viewport dict for mobile QA.
            # Absent -> unchanged default desktop viewport behavior.
            'viewport': request.payload.get('viewport'),
        }
        script_content = _VALIDATE_SCRIPT.replace('__U94_PARAMS_JSON__', repr(json.dumps(params)))
        return self._run_script(sandbox, script_content, request, start_time, timeout=sandbox_timeout)

    @api.model
    def _run_script(self, sandbox, script_content: str, request: ProviderExecutionRequest, start_time: float, timeout: int = 30) -> ProviderExecutionResult:
        fd, script_path = tempfile.mkstemp(suffix=".py")
        try:
            # Explicit UTF-8: the sandboxed script must be readable by Python
            # regardless of the Windows locale default (cp1252).
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(script_content)
                
            # Execute EXCLUSIVELY through ExecutionSandboxService
            cmd = ["python", script_path]
            res = sandbox.execute_local(cmd, timeout=timeout)
            
            stdout = res.get('stdout') or ''
            parsed = None
            try:
                parsed = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else None
            except Exception:
                parsed = None

            if res.get('success'):
                result = parsed if isinstance(parsed, dict) else {"output": stdout}
                return ProviderExecutionResult(success=True, data=result, error=None, execution_ms=(time.time()-start_time)*1000)
            else:
                # Diagnostics survive failure: the validate script prints its
                # JSON evidence even when the browser-level run fails, so the
                # caller receives structured evidence alongside the error.
                error_text = res.get('stderr') or res.get('error') or "Sandbox execution failed."
                if isinstance(parsed, dict):
                    parsed_error = parsed.get('error')
                    if parsed_error:
                        error_text = f"{error_text} | {parsed_error}"
                    return ProviderExecutionResult(success=False, data=parsed, error=str(error_text)[:2000], execution_ms=(time.time()-start_time)*1000)
                raise Exception(error_text)
                
        except Exception as e:
            _logger.error(f"{self._description} execution error: {e}")
            return ProviderExecutionResult(success=False, data=None, error=f"{self._description} error: {str(e)}", execution_ms=(time.time()-start_time)*1000)
        finally:
            if 'script_path' in locals() and os.path.exists(script_path):
                os.remove(script_path)
