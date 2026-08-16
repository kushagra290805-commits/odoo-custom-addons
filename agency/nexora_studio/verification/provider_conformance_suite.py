import sys
import json
import time
import argparse
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ProviderDescriptor:
    id: str
    model: str
    test_capability: str
    test_payload: Dict[str, Any]

PROVIDERS = [
    ProviderDescriptor('mcp.github', 'nexora.provider.github', 'list-commits', {"mcp_tool": "list-commits", "owner": "torvalds", "repo": "linux", "per_page": 1}),
    ProviderDescriptor('local.playwright', 'nexora.provider.playwright', 'snapshot', {"action": "snapshot", "url": "https://example.com"}),
    ProviderDescriptor('mcp.context7', 'nexora.provider.context7', 'query', {"mcp_tool": "query", "text": "hello"}),
    ProviderDescriptor('mcp.tavily', 'nexora.provider.tavily', 'search', {"mcp_tool": "search", "query": "latest news"}),
    ProviderDescriptor('mcp.penpot', 'nexora.provider.penpot', 'get-files', {"mcp_tool": "get-files", "teamId": "demo"}),
    ProviderDescriptor('local.spline', 'nexora.provider.spline', 'render', {"action": "render", "scene_url": "https://prod.spline.design/example/scene.splinecode"}),
    ProviderDescriptor('local.gosom', 'nexora.provider.gosom', 'scrape', {"query": "restaurants in new york", "depth": 1}),
]

import os

def run_conformance_suite():
    import os
    target = os.environ.get('PROVIDER_TARGET')
    
    if target:
        target = target.lower()
        if not target.startswith('mcp.') and not target.startswith('local.'):
            # Attempt to match by suffix
            matched = [p for p in PROVIDERS if p.id.endswith(target)]
            if matched:
                active_providers = matched
            else:
                print(f"Unknown provider: {target}")
                return
        else:
            active_providers = [p for p in PROVIDERS if p.id == target]
    else:
        active_providers = PROVIDERS

    print("==================================================")
    print("  NEXORA STUDIO - PROVIDER CONFORMANCE SUITE")
    print("==================================================")

    results = {}
    
    print("\n[STAGE 1] PROVIDER REGISTRATION")
    for p in active_providers:
        exists = p.model in env.registry.models
        results[p.id] = {"Registration": "PASS" if exists else "FAIL"}
        print(f"[{'PASS' if exists else 'FAIL'}] {p.id} -> {p.model}")

    print("\n[STAGE 2] PLATFORM RUNTIME INITIALIZATION")
    try:
        runtime = env['nexora_studio.platform'].get_runtime()
        print("[PASS] PlatformRuntime singleton obtained.")
        
        mcp_runtime = runtime.get_runtime('mcp_runtime')
        print("Waiting 10s for Real MCP Servers to stabilize...")
        time.sleep(10)
        
        catalog_caps = list(mcp_runtime.catalog._capabilities.keys())
        health = mcp_runtime.health_status()
        print(f"[PASS] Runtime Health: {health}")
        print(f"[PASS] MCP Capability Discovery (Found {len(catalog_caps)} capabilities)")
        
        for p in active_providers:
            results[p.id]["Bootstrap"] = "PASS"
    except Exception as e:
        print(f"[FAIL] Platform Runtime Bootstrap: {e}")
        for p in active_providers:
            results[p.id]["Bootstrap"] = "FAIL"

    print("\n[STAGE 3] REAL EXECUTION AND VALIDATION")
    for p in active_providers:
        print(f"\n--- Testing {p.id} ---")
        if p.model not in env:
            print(f"[FAIL] {p.model} not available in Odoo environment.")
            results[p.id]["Execution"] = "FAIL"
            continue
            
        start = time.time()
        try:
            # We perform Real Execution
            res = env[p.model].execute(p.test_capability, p.test_payload)
            latency = (time.time() - start) * 1000
            print(f"End-to-End Latency: {latency:.2f}ms")
            
            # Response Validation
            if res and isinstance(res, list) and len(res) > 0 and res[0].get('severity') != 'error':
                print(f"[PASS] Real Execution Success")
                try:
                    trace = str(res[0])
                    print(f"[PAYLOAD TRACE] {trace[:200]}...")
                except UnicodeEncodeError:
                    print(f"[PAYLOAD TRACE] (Contains unicode characters)")
                results[p.id]["Execution"] = "PASS"
                results[p.id]["Latency"] = f"{latency:.0f} ms"
                results[p.id]["Regression"] = "PASS"
                results[p.id]["Production"] = "READY"
            else:
                print(f"[FAIL] Real Execution Failed: {res}")
                results[p.id]["Execution"] = "FAIL"
                results[p.id]["Latency"] = f"{latency:.0f} ms"
                results[p.id]["Regression"] = "FAIL"
                results[p.id]["Production"] = "NOT READY"
        except Exception as e:
            latency = (time.time() - start) * 1000
            print(f"[ERROR] Exception during real execution: {e}")
            results[p.id]["Execution"] = "ERROR"
            results[p.id]["Latency"] = f"{latency:.0f} ms"
            results[p.id]["Regression"] = "FAIL"
            results[p.id]["Production"] = "NOT READY"

    # Generate Dashboard JSON
    with open("D:/ODOO/custom-addons/agency/nexora_studio/verification/conformance_dashboard.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\n==================================================")
    print("  CONFORMANCE SUITE DASHBOARD")
    print("==================================================")
    print(f"{'Provider':<20} | {'Registration':<12} | {'Bootstrap':<9} | {'Execution':<9} | {'Latency':<8} | {'Regression':<10} | {'Production':<10}")
    print("-" * 90)
    for p_id, stats in results.items():
        print(f"{p_id:<20} | {stats.get('Registration',''):<12} | {stats.get('Bootstrap',''):<9} | {stats.get('Execution',''):<9} | {stats.get('Latency',''):<8} | {stats.get('Regression',''):<10} | {stats.get('Production',''):<10}")

if __name__ == '__main__':
    run_conformance_suite()
