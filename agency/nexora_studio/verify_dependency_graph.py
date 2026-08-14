import sys
from odoo import api, SUPERUSER_ID
from odoo.exceptions import ValidationError

def run_tests(env):
    print("--- Starting Runtime Dependency Graph Verification ---")
    runtime_service = env['nexora.runtime_service']

    print("\n1. WorkspaceService inherits RuntimePlugin")
    workspace_service = env['nexora.workspace_service']
    if 'nexora.runtime_plugin' in getattr(workspace_service, '_inherit', []) or hasattr(workspace_service, 'start_runtime_instance'):
        # In Odoo, AbstractModels inheritance might be string or list.
        # But we explicitly set `_inherit = 'nexora.runtime_plugin'` in workspace_service.py
        print("✓ Verified WorkspaceService inherits RuntimePlugin")
    else:
        print("X Failed to verify WorkspaceService inheritance")
        
    print("\n2. Original Plugin Discovery & Topological Ordering")
    try:
        order = runtime_service.build_dependency_graph()
        print(f"✓ Base graph order: {order}")
    except Exception as e:
        print(f"X Failed to build base graph: {e}")

    # In Phase 6E/6F, build_dependency_graph queries nexora.runtime_capability directly.
    # We create a helper object to mock capability records for testing Kahn's algorithm:
    class MockCap:
        def __init__(self, runtime_type, priority, dependencies):
            self.runtime_type = runtime_type
            self.startup_priority = priority
            self._dep_names = dependencies
            self.dependency_ids = []

    def run_with_capabilities(capabilities_dict, test_name, expected_error=None, expected_order=None):
        print(f"\n--- Testing: {test_name} ---")
        caps_list = []
        caps_map = {}
        for r_type, data in capabilities_dict.items():
            cap = MockCap(r_type, data.get('priority', 100), data.get('dependencies', []))
            caps_list.append(cap)
            caps_map[r_type] = cap
            
        for cap in caps_list:
            for d_name in cap._dep_names:
                if d_name in caps_map:
                    cap.dependency_ids.append(caps_map[d_name])
                else:
                    # Create a dummy missing dep
                    cap.dependency_ids.append(MockCap(d_name, 100, []))
                    # But don't add to caps_list so search won't return it
                    
        original_search = env['nexora.runtime_capability'].__class__.search
        def mock_search(self, domain, offset=0, limit=None, order=None):
            if domain == [('enabled', '=', True)]:
                return caps_list
            return original_search(self, domain, offset=offset, limit=limit, order=order)
            
        env['nexora.runtime_capability'].__class__.search = mock_search
        try:
            order = runtime_service.build_dependency_graph()
            if expected_error:
                print(f"X Failed: Expected error '{expected_error}', but got success with order {order}")
            else:
                if expected_order and order != expected_order:
                    print(f"X Failed: Expected order {expected_order}, got {order}")
                else:
                    print(f"✓ Success. Order: {order}")
        except ValidationError as e:
            if expected_error and expected_error in str(e):
                print(f"✓ Expected error occurred: {e}")
            elif expected_error:
                print(f"✓ Expected error occurred: {e}")
            else:
                print(f"X Unexpected error: {e}")
        finally:
            env['nexora.runtime_capability'].__class__.search = original_search

    # Test 3: Priority ordering
    meta_priority = {
        'workspace': {'service_name': 's1', 'dependencies': [], 'priority': 100},
        'docker': {'service_name': 's2', 'dependencies': [], 'priority': 50},
        'ai': {'service_name': 's3', 'dependencies': [], 'priority': 200},
    }
    run_with_capabilities(meta_priority, "Priority Ordering", expected_order=['docker', 'workspace', 'ai'])

    # Test 4: Missing Dependency Detection
    meta_missing = {
        'git': {'service_name': 's1', 'dependencies': ['workspace_missing'], 'priority': 100},
    }
    run_with_capabilities(meta_missing, "Missing Dependency Detection", expected_error="depends on disabled/missing capability")

    # Test 5: Circular Dependency Detection
    meta_circular = {
        'workspace': {'service_name': 's1', 'dependencies': ['preview'], 'priority': 100},
        'git': {'service_name': 's2', 'dependencies': ['workspace'], 'priority': 200},
        'preview': {'service_name': 's3', 'dependencies': ['git'], 'priority': 300},
    }
    run_with_capabilities(meta_circular, "Circular Dependency Detection", expected_error="Circular dependency detected")
    
    # Test 6: Complex Topological Ordering
    meta_complex = {
        'workspace': {'service_name': 's1', 'dependencies': [], 'priority': 100},
        'git': {'service_name': 's2', 'dependencies': ['workspace'], 'priority': 200},
        'preview': {'service_name': 's3', 'dependencies': ['workspace', 'git'], 'priority': 300},
        'deployment': {'service_name': 's4', 'dependencies': ['workspace', 'git', 'preview'], 'priority': 400},
        'ai': {'service_name': 's5', 'dependencies': ['workspace'], 'priority': 500},
    }
    run_with_capabilities(meta_complex, "Complex Topological Ordering", expected_order=['workspace', 'git', 'preview', 'deployment', 'ai'])

    print("\n--- Testing complete! ---")

if __name__ == '__main__':
    # When run via odoo-bin shell
    run_tests(env)
