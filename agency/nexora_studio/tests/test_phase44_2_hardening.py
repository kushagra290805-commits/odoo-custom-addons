# -*- coding: utf-8 -*-
"""
Phase 44.2 — MCP Platform Hardening Regression Suite
=====================================================
Guards the correctness, security, and architectural invariants implemented in
Phase 44.2 (ADR-0068). Pure unit tests — no database, no live MCP servers.

Classification: UNIT. Runs under the standard Odoo test runner.

Covered invariants:
  W3  — Reserved protocol namespace contract (verbatim match before shorthand)
  W5  — Truthful health model (unknown default; degraded is health, not lifecycle)
  W6  — request_context propagation + allowlist-gated MCP meta
  W7  — SessionTransportPool hard max_size bound with LRU eviction
  W8  — timeout_seconds / working_directory plumbed into McpConfiguration
  W9  — Credential fail-closed (G-12), declared-only injection (G-21),
        exact composite-key validate (G-52)
  W11 — Non-destructive capability discovery (failure preserves prior rows)
  W14 — No silent failure surfaces (malformed allowlist JSON → visible fallback)
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.addons.nexora_studio.services.connector.domain.models import (
    ConnectorHealth,
    ConnectorHealthStatus,
    ConnectorCredentialReference,
    CredentialType,
    is_reserved_protocol_namespace,
    RESERVED_PROTOCOL_NAMESPACES,
)


# ---------------------------------------------------------------------------
# W3 — Namespace contract
# ---------------------------------------------------------------------------

class TestNamespaceContract(unittest.TestCase):
    def test_reserved_namespaces_are_exactly_six(self):
        self.assertEqual(RESERVED_PROTOCOL_NAMESPACES, frozenset({
            "tools.list", "tools.call", "resources.list",
            "resources.read", "prompts.list", "prompts.get",
        }))

    def test_reserved_detection(self):
        for ns in RESERVED_PROTOCOL_NAMESPACES:
            self.assertTrue(is_reserved_protocol_namespace(ns))
        self.assertFalse(is_reserved_protocol_namespace("penpot.export"))
        self.assertFalse(is_reserved_protocol_namespace("tools.listx"))

    def test_executor_reserved_passthrough(self):
        from odoo.addons.nexora_studio.services.connector.integration.connector_executor import (
            ConnectorExecutionTarget,
        )
        target = ConnectorExecutionTarget(connector_runtime=MagicMock())
        req = target._build_request({
            "namespace": "tools.call",
            "inputs": {"name": "search", "arguments": {"q": "x"}},
            "context": {"connector_id": "tavily_mcp"},
        })
        # Reserved namespace must pass through untouched (no shorthand split).
        self.assertEqual(req.capability_namespace, "tools.call")
        self.assertEqual(req.payload, {"name": "search", "arguments": {"q": "x"}})
        self.assertEqual(req.context.connector_id, "tavily_mcp")

    def test_executor_dynamic_shorthand_rewrite(self):
        from odoo.addons.nexora_studio.services.connector.integration.connector_executor import (
            ConnectorExecutionTarget,
        )
        target = ConnectorExecutionTarget(connector_runtime=MagicMock())
        req = target._build_request({
            "namespace": "penpot_mcp.export_board",
            "inputs": {"board": "b1"},
        })
        # Non-reserved dotted namespace is the {connector_id}.{tool_name} shorthand.
        self.assertEqual(req.capability_namespace, "tools.call")
        self.assertEqual(req.context.connector_id, "penpot_mcp")
        self.assertEqual(req.payload, {"name": "export_board", "arguments": {"board": "b1"}})


# ---------------------------------------------------------------------------
# W5 — Truthful health model
# ---------------------------------------------------------------------------

class TestTruthfulHealth(unittest.TestCase):
    def test_default_is_unknown(self):
        health = ConnectorHealth(connector_id="c")
        self.assertEqual(health.status, ConnectorHealthStatus.UNKNOWN)
        self.assertFalse(health.is_healthy())

    def test_success_marks_healthy(self):
        health = ConnectorHealth(connector_id="c")
        health.record_success(latency_ms=12.0)
        self.assertEqual(health.status, ConnectorHealthStatus.HEALTHY)
        self.assertTrue(health.is_healthy())

    def test_degraded_then_failed(self):
        health = ConnectorHealth(connector_id="c")
        health.record_failure("boom")
        self.assertEqual(health.status, ConnectorHealthStatus.DEGRADED)
        self.assertTrue(health.is_degraded())
        health.record_failure("boom2")
        health.record_failure("boom3")
        self.assertEqual(health.status, ConnectorHealthStatus.FAILED)

    def test_degraded_is_not_a_lifecycle_state(self):
        from odoo.addons.nexora_studio.services.connector.domain.models import (
            ConnectorLifecycleState,
        )
        # 'degraded' must exist only as a health status, never a lifecycle state.
        self.assertNotIn("degraded", [s.value for s in ConnectorLifecycleState])


# ---------------------------------------------------------------------------
# W7 — SessionTransportPool bound
# ---------------------------------------------------------------------------

class TestSessionTransportPoolBound(unittest.TestCase):
    def _make_pool(self):
        from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import (
            McpConfiguration,
        )
        from odoo.addons.nexora_studio.services.connector.connectors.mcp.pool import (
            SessionTransportPool,
        )
        config = McpConfiguration(
            command="http://localhost/sse", transport="sse",
            session_binding="user", session_binding_field="userToken",
        )
        return SessionTransportPool(config)

    def test_max_size_bound(self):
        pool = self._make_pool()
        self.assertEqual(pool.max_size, 100)

    def test_lru_eviction_at_capacity(self):
        pool = self._make_pool()
        pool.max_size = 2  # shrink for the test

        created = []

        class FakeTransport:
            def __init__(self, *a, **k):
                created.append(self)
                self.disconnected = False
            def is_connected(self):
                return True
            def connect(self):
                pass
            def disconnect(self):
                self.disconnected = True

        with patch(
            "odoo.addons.nexora_studio.services.connector.connectors.mcp.pool.McpTransport",
            FakeTransport,
        ):
            t1 = pool.get_transport("session-a")
            t2 = pool.get_transport("session-b")
            # Pool is at capacity (2). Adding a third must evict the LRU (t1).
            t3 = pool.get_transport("session-c")

        self.assertEqual(len(pool._pool), 2)
        self.assertTrue(t1.disconnected, "LRU transport must be evicted and disconnected")
        self.assertIsNotNone(t3)


# ---------------------------------------------------------------------------
# W8 — Config plumbing
# ---------------------------------------------------------------------------

class TestConfigPlumbing(unittest.TestCase):
    def _service(self, resolved_secrets):
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import (
            McpOnboardingService,
        )
        service = McpOnboardingService(MagicMock(), MagicMock(), MagicMock())
        service._resolver = MagicMock()
        service._resolver.resolve_all_for_connector.return_value = resolved_secrets
        return service

    def _config_record(self, **overrides):
        base = dict(
            transport_type="stdio",
            command="npx",
            get_env_vars_dict=lambda: {},
            get_args_list=lambda: ["-y", "some-mcp"],
            authentication_location="none",
            authentication_name="",
            authentication_scheme="none",
            credential_key="",
            session_binding="none",
            session_binding_field="",
            session_binding_location="query",
            allowed_request_context_fields_json="[]",
            timeout_seconds=90,
            working_directory="/srv/mcp",
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_timeout_and_cwd_plumbed(self):
        service = self._service({})
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        cfg = service._build_mcp_configuration(connector, self._config_record())
        self.assertEqual(cfg.timeout_seconds, 90)
        self.assertEqual(cfg.working_directory, "/srv/mcp")

    def test_timeout_defaults_when_unset(self):
        service = self._service({})
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        cfg = service._build_mcp_configuration(
            connector, self._config_record(timeout_seconds=0, working_directory=""))
        self.assertEqual(cfg.timeout_seconds, 60)
        self.assertIsNone(cfg.working_directory)


# ---------------------------------------------------------------------------
# W9 — Credential fail-closed, declared-only injection, exact-key validate
# ---------------------------------------------------------------------------

class TestCredentialHardening(unittest.TestCase):
    def _service(self, resolved_secrets):
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import (
            McpOnboardingService,
        )
        service = McpOnboardingService(MagicMock(), MagicMock(), MagicMock())
        service._resolver = MagicMock()
        service._resolver.resolve_all_for_connector.return_value = resolved_secrets
        return service

    def _config_record(self, **overrides):
        base = dict(
            transport_type="stdio",
            command="npx",
            get_env_vars_dict=lambda: {},
            get_args_list=lambda: [],
            authentication_location="none",
            authentication_name="",
            authentication_scheme="none",
            credential_key="",
            session_binding="none",
            session_binding_field="",
            session_binding_location="query",
            allowed_request_context_fields_json="[]",
            timeout_seconds=60,
            working_directory="",
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_g12_unresolved_auth_credential_fails_closed(self):
        from odoo.addons.nexora_studio.services.connector.sdk.exceptions import (
            ConnectorConfigurationError,
        )
        service = self._service({})  # no secrets resolvable
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        rec = self._config_record(
            transport_type="sse", command="http://x/sse",
            authentication_location="header", authentication_name="Authorization",
            credential_key="API_TOKEN",
        )
        with self.assertRaises(ConnectorConfigurationError) as ctx:
            service._build_mcp_configuration(connector, rec)
        self.assertEqual(ctx.exception.error_code, "CREDENTIAL_UNRESOLVED")

    def test_g12_no_auth_configured_is_legitimate(self):
        service = self._service({})
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        cfg = service._build_mcp_configuration(connector, self._config_record())
        self.assertEqual(cfg.auth_secret, "")

    def test_g21_declared_only_injection(self):
        PH = "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__"
        service = self._service({"API_KEY": "secret-val", "OTHER": "other-val"})
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        rec = self._config_record(
            get_env_vars_dict=lambda: {"API_KEY": PH, "PLAIN": "literal"},
        )
        cfg = service._build_mcp_configuration(connector, rec)
        # Only the declared key is injected; OTHER (undeclared) must NOT leak.
        self.assertEqual(cfg.env.get("API_KEY"), "secret-val")
        self.assertEqual(cfg.env.get("PLAIN"), "literal")
        self.assertNotIn("OTHER", cfg.env)

    def test_g21_declared_unresolvable_fails_closed(self):
        from odoo.addons.nexora_studio.services.connector.sdk.exceptions import (
            ConnectorConfigurationError,
        )
        PH = "__INJECT_VIA_NEXORA_MCP_CREDENTIAL__"
        service = self._service({})  # nothing resolvable
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        rec = self._config_record(get_env_vars_dict=lambda: {"API_KEY": PH})
        with self.assertRaises(ConnectorConfigurationError) as ctx:
            service._build_mcp_configuration(connector, rec)
        self.assertEqual(ctx.exception.error_code, "CREDENTIAL_UNRESOLVED")

    def test_g21_backward_compat_wholesale_injection(self):
        # No declarations → legacy wholesale injection preserved.
        service = self._service({"API_KEY": "secret-val"})
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        rec = self._config_record(get_env_vars_dict=lambda: {"PLAIN": "literal"})
        cfg = service._build_mcp_configuration(connector, rec)
        self.assertEqual(cfg.env.get("API_KEY"), "secret-val")
        self.assertEqual(cfg.env.get("PLAIN"), "literal")

    def test_g52_validate_requires_connector_scope(self):
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_credential_resolver import (
            OdooCredentialResolver,
        )
        resolver = OdooCredentialResolver.__new__(OdooCredentialResolver)
        resolver._secrets = MagicMock()
        resolver._secrets.has_secret.return_value = True
        ref = ConnectorCredentialReference(
            credential_key="API_TOKEN", credential_type=CredentialType.API_KEY,
            display_name="API Token",
        )
        # Without a connector scope, validation must fail closed.
        result = resolver.validate(ref)
        self.assertFalse(result.valid)
        self.assertIn("connector scope", result.error)

    def test_g52_validate_exact_composite_key(self):
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_credential_resolver import (
            OdooCredentialResolver,
        )
        resolver = OdooCredentialResolver.__new__(OdooCredentialResolver)
        resolver._secrets = MagicMock()
        seen_keys = []
        resolver._secrets.has_secret.side_effect = lambda k: (seen_keys.append(k), k == "c1:API_TOKEN")[1]
        ref = ConnectorCredentialReference(
            credential_key="API_TOKEN", credential_type=CredentialType.API_KEY,
            display_name="API Token",
        )
        result = resolver.validate(ref, connector_id="c1")
        self.assertTrue(result.valid)
        # Must check the exact composite key — no suffix scan.
        self.assertEqual(seen_keys, ["c1:API_TOKEN"])


# ---------------------------------------------------------------------------
# W6 — request_context propagation + allowlist-gated meta
# ---------------------------------------------------------------------------

class TestRequestContextPropagation(unittest.TestCase):
    def test_executor_carries_request_context(self):
        from odoo.addons.nexora_studio.services.connector.integration.connector_executor import (
            ConnectorExecutionTarget,
        )
        target = ConnectorExecutionTarget(connector_runtime=MagicMock())
        req = target._build_request({
            "namespace": "tools.list",
            "context": {"connector_id": "penpot_mcp"},
            "request_context": {"userToken": "tok-123"},
        })
        self.assertEqual(req.context.request_context, {"userToken": "tok-123"})

    def test_transport_meta_allowlist_intersection(self):
        from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import (
            McpConfiguration,
        )
        from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import (
            McpTransport,
        )
        config = McpConfiguration(
            command="http://x/sse", transport="sse",
            allowed_request_context_fields=["userToken"],
        )
        transport = McpTransport(config)
        transport._session = MagicMock()

        with patch.object(McpTransport, "is_connected", return_value=True), \
             patch.object(McpTransport, "_run_sync", return_value="ok") as run_sync:
            transport.call_tool("t", {"a": 1}, request_context={
                "userToken": "tok", "secret_field": "must-not-pass",
            })

        # Only allowlisted fields cross into MCP meta.
        call = transport._session.call_tool.call_args
        meta = call.kwargs.get("meta")
        self.assertEqual(meta, {"userToken": "tok"})
        self.assertNotIn("secret_field", meta or {})

    def test_transport_no_meta_when_no_intersection(self):
        from odoo.addons.nexora_studio.services.connector.connectors.mcp.configuration import (
            McpConfiguration,
        )
        from odoo.addons.nexora_studio.services.connector.connectors.mcp.transport import (
            McpTransport,
        )
        config = McpConfiguration(
            command="http://x/sse", transport="sse",
            allowed_request_context_fields=["userToken"],
        )
        transport = McpTransport(config)
        transport._session = MagicMock()

        with patch.object(McpTransport, "is_connected", return_value=True), \
             patch.object(McpTransport, "_run_sync", return_value="ok"):
            transport.call_tool("t", {}, request_context={"other": "x"})

        call = transport._session.call_tool.call_args
        # No allowlisted field present → call without meta kwarg.
        self.assertNotIn("meta", call.kwargs)


# ---------------------------------------------------------------------------
# W11 — Non-destructive capability discovery
# ---------------------------------------------------------------------------

class _FakeRecord:
    def __init__(self, tool_name):
        self.tool_name = tool_name
        self.written = None
        self.unlinked = False
    def write(self, vals):
        self.written = vals
    def unlink(self):
        self.unlinked = True


class _FakeRecordSet(list):
    def filtered(self, fn):
        return _FakeRecordSet([r for r in self if fn(r)])
    def unlink(self):
        for r in self:
            r.unlinked = True


class _FakeModel:
    def __init__(self, existing=None):
        self.existing = _FakeRecordSet(existing or [])
        self.created = []
    def search(self, domain):
        # Return only rows matching the discovery_source in the domain.
        source = None
        for d in domain:
            if d[0] == "discovery_source":
                source = d[2]
        if source is None:
            return self.existing
        return _FakeRecordSet([r for r in self.existing if getattr(r, "_source", source) == source])
    def create(self, vals_list):
        self.created.extend(vals_list)
        return vals_list


class TestNonDestructiveDiscovery(unittest.TestCase):
    def _service(self, model):
        from odoo.addons.nexora_studio.services.connector.onboarding.capability_discovery import (
            McpCapabilityDiscoveryService,
        )
        env = MagicMock()
        env.__getitem__.side_effect = lambda key: (
            model if key == "nexora.mcp_discovered_tool" else MagicMock()
        )
        service = McpCapabilityDiscoveryService(MagicMock(), env)
        return service

    def test_failed_source_preserves_rows(self):
        existing = [_FakeRecord("old_tool")]
        existing[0]._source = "tools"  # row belongs to the 'tools' source
        model = _FakeModel(existing)
        service = self._service(model)
        connector = SimpleNamespace(id=1, connector_id="c1")
        # tools=None (failed), resources=[], prompts=[]
        persisted = service._upsert_discovered_tools(connector, None, [], [])
        self.assertTrue(persisted)
        # The failed 'tools' source must NOT have wiped the existing row.
        self.assertFalse(existing[0].unlinked)

    def test_all_sources_failed_skips_persistence(self):
        existing = [_FakeRecord("old_tool")]
        existing[0]._source = "tools"
        model = _FakeModel(existing)
        service = self._service(model)
        connector = SimpleNamespace(id=1, connector_id="c1")
        persisted = service._upsert_discovered_tools(connector, None, None, None)
        self.assertFalse(persisted)
        self.assertFalse(existing[0].unlinked)
        self.assertEqual(model.created, [])

    def test_successful_source_upserts_and_prunes(self):
        keep = _FakeRecord("tool_a")
        stale = _FakeRecord("tool_gone")
        # Tag rows so the fake search can filter by source.
        keep._source = "tools"
        stale._source = "tools"
        model = _FakeModel([keep, stale])
        service = self._service(model)
        connector = SimpleNamespace(id=1, connector_id="c1")
        tools = [
            {"name": "tool_a", "description": "updated", "inputSchema": {}},
            {"name": "tool_new", "description": "new", "inputSchema": {}},
        ]
        service._upsert_discovered_tools(connector, tools, None, None)
        # tool_a updated in place, tool_gone pruned, tool_new created.
        self.assertIsNotNone(keep.written)
        self.assertTrue(stale.unlinked)
        self.assertEqual([v["tool_name"] for v in model.created], ["tool_new"])


# ---------------------------------------------------------------------------
# W14 — No silent failure surfaces
# ---------------------------------------------------------------------------

class TestNoSilentFailures(unittest.TestCase):
    def test_malformed_allowlist_json_falls_back_visibly(self):
        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import (
            McpOnboardingService,
        )
        service = McpOnboardingService(MagicMock(), MagicMock(), MagicMock())
        service._resolver = MagicMock()
        service._resolver.resolve_all_for_connector.return_value = {}
        connector = SimpleNamespace(id=1, connector_id="c1", name="C1")
        rec = SimpleNamespace(
            transport_type="sse", command="http://x/sse",
            get_env_vars_dict=lambda: {}, get_args_list=lambda: [],
            authentication_location="none", authentication_name="",
            authentication_scheme="none", credential_key="",
            session_binding="none", session_binding_field="",
            session_binding_location="query",
            allowed_request_context_fields_json="{not-valid-json",
            timeout_seconds=60, working_directory="",
        )
        # Must not raise; must fall back to an empty allowlist.
        cfg = service._build_mcp_configuration(connector, rec)
        self.assertEqual(cfg.allowed_request_context_fields, [])


if __name__ == "__main__":
    unittest.main()
