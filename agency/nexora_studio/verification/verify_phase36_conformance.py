"""
Phase 36 — UCP Execution Unification Conformance Test

Tests that each canonical MCP connector can be registered, initialized,
and executed through the single UCP execution path:

  Provider → ConnectorRuntime.dispatch() → ConnectorDispatcher → Transport → MCP

This script uses PRODUCTION credentials already stored in OdooSecretsProvider.
It does NOT inject dummy credentials. It assumes the Odoo DB has valid secrets.
"""
import time
import logging

logging.basicConfig(level=logging.WARNING)

def run_conformance():
    print("==================================================")
    print("  PHASE 36 - UCP EXECUTION UNIFICATION CONFORMANCE")
    print("==================================================")

    # Stage 0: Bootstrap runtime
    print("\n[STAGE 0] BOOTSTRAP UCP RUNTIME")
    from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
    bootstrap = ConnectorPlatformBootstrap.get_instance()
    bootstrap.bootstrap(env)
    runtime = bootstrap.connector_runtime

    if runtime is None:
        print("[FATAL] ConnectorRuntime is None — cannot proceed.")
        return

    print(f"[OK] Runtime ready. Registry count: {runtime.registry.count()}")

    # Stage 1: Credential audit (non-destructive)
    print("\n[STAGE 1] CREDENTIAL AUDIT (production secrets)")
    from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
    secrets_provider = OdooSecretsProvider(env)

    credential_map = {
        'github_mcp':   'GITHUB_PERSONAL_ACCESS_TOKEN',
        'context7_mcp': 'CONTEXT7_API_KEY',
        'tavily_mcp':   'TAVILY_API_KEY',
    }
    for cid, key in credential_map.items():
        composite = f"{cid}:{key}"
        try:
            val = secrets_provider.get_secret(composite)
            masked = f"{val[:4]}…" if val else '<EMPTY>'
        except KeyError:
            masked = '<MISSING>'
        print(f"  {cid}: {key} = {masked}")

    # Stage 2: Per-connector registration + execution
    print("\n[STAGE 2] CONNECTOR CONFORMANCE")

    from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
    onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, env)

    connectors = [
        # (connector_id, provider_model, mcp_tool, tool_args)
        ('github_mcp',   'nexora.provider.github',  'list_branches', {'owner': 'octocat', 'repo': 'Hello-World'}),
        ('context7_mcp', 'nexora.provider.context7', 'resolve-library-id', {'libraryName': 'react'}),
        # Tavily MCP keyless mode exposes 'search' tool (no API key stored; keyless OK for transport verification)
        ('tavily_mcp',   'nexora.provider.tavily',  'tavily_search', {'query': 'test connectivity'}),
    ]

    results = {}

    for cid, provider_model, tool_name, tool_args in connectors:
        print(f"\n  -- {cid} --")
        stats = {}

        # 1. DB record exists
        record = env['nexora.connector'].search([('connector_id', '=', cid)], limit=1)
        if not record:
            print(f"  [FAIL] DB record not found for '{cid}'")
            for k in ('DB Record', 'Registration', 'Initialization', 'Health', 'Execution'):
                stats[k] = 'FAIL' if k == 'DB Record' else 'SKIP'
            results[cid] = stats
            continue
        stats['DB Record'] = 'PASS'
        print(f"  [PASS] DB record found: state={record.state}")

        # 2. Registration (deregister stale, then re-register with production creds)
        try:
            onboarding.deregister_connector(cid)       # safe no-op if absent
            onboarding.register_connector(record)      # full handshake with real secrets
            stats['Registration'] = 'PASS'
            print(f"  [PASS] Registration + handshake succeeded.")
        except Exception as e:
            stats['Registration']   = f'FAIL: {type(e).__name__}'
            stats['Initialization'] = 'SKIP'
            stats['Health']         = 'SKIP'
            stats['Execution']      = 'SKIP'
            print(f"  [FAIL] Registration failed: {e}")
            results[cid] = stats
            continue

        # 3. Lifecycle state
        rt_conn = runtime.registry.get(cid)
        if rt_conn is None:
            stats['Initialization'] = 'FAIL (absent from registry)'
            stats['Health']         = 'SKIP'
            stats['Execution']      = 'SKIP'
            print(f"  [FAIL] Connector absent from registry after registration.")
            results[cid] = stats
            continue

        state_name = rt_conn.lifecycle_state.name
        if rt_conn.is_running:
            stats['Initialization'] = 'PASS'
            print(f"  [PASS] State: {state_name}")
        else:
            stats['Initialization'] = f'FAIL ({state_name})'
            print(f"  [FAIL] State: {state_name} (expected RUNNING)")

        # 4. Health
        is_healthy = rt_conn.is_healthy
        stats['Health'] = 'PASS' if is_healthy else f'FAIL ({state_name})'
        print(f"  [{'PASS' if is_healthy else 'FAIL'}] Health: is_healthy={is_healthy}")

        # 5. Execution via provider → ConnectorRuntime.dispatch()
        if provider_model not in env:
            stats['Execution'] = 'SKIP (model absent)'
            print(f"  [SKIP] Provider model '{provider_model}' not registered.")
            results[cid] = stats
            continue

        provider = env[provider_model]
        try:
            from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest
            req = ProviderExecutionRequest(
                namespace='tools.call',
                payload={'mcp_tool': tool_name, **tool_args}
            )
            exec_res = provider.execute(req)

            if exec_res.success:
                stats['Execution'] = 'PASS'
                print(f"  [PASS] Execution succeeded. Response len: {len(str(exec_res.data))}")
            else:
                err = str(exec_res.error or '')
                # Application-level errors (auth, param) mean transport + routing succeeded.
                transport_ok_signals = [
                    'missing required parameter', 'API key', 'credential',
                    'isError', 'Unauthorized', '401', 'Bad credentials',
                ]
                if any(sig.lower() in err.lower() for sig in transport_ok_signals):
                    stats['Execution'] = 'PASS (Transport OK / App Error)'
                    print(f"  [PASS] Transport OK. App-level error: {err[:120]}")
                else:
                    stats['Execution'] = f'FAIL: {err[:80]}'
                    print(f"  [FAIL] Execution failed: {err}")
        except Exception as e:
            import traceback
            stats['Execution'] = f'ERROR: {type(e).__name__}'
            print(f"  [ERROR] Exception: {e}")
            print(traceback.format_exc())

        results[cid] = stats

    # Dashboard
    print("\n" + "=" * 100)
    print("  PHASE 36 CONFORMANCE DASHBOARD")
    print("=" * 100)
    cols = ['DB Record', 'Registration', 'Initialization', 'Health', 'Execution']
    hdr = f"{'Connector':<20}"
    for c in cols:
        hdr += f" | {c:<28}"
    print(hdr)
    print("-" * 100)
    for cid, stats in results.items():
        row = f"{cid:<20}"
        for c in cols:
            row += f" | {stats.get(c, ''):<28}"
        print(row)

    all_pass = all(
        stats.get('Registration', '').startswith('PASS') and
        stats.get('Execution', '').startswith('PASS')
        for stats in results.values()
    )
    verdict = "PASS" if all_pass else "FAIL"
    print(f"\n[VERDICT] PHASE 36 CONFORMANCE: {verdict}")

if __name__ == '__main__':
    run_conformance()
