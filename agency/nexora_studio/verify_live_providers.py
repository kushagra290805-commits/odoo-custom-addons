# -*- coding: utf-8 -*-
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from odoo.addons.nexora_studio.services.source_framework.transport.mock_transport import MockTransport
from odoo.addons.nexora_studio.services.source_framework.adapters.penpot_adapter import PenpotAdapter
from odoo.addons.nexora_studio.services.source_framework.adapters.github_adapter import GitHubAdapter

def test_penpot_live_payloads():
    # Simulate correct payload
    def penpot_search_mock(args):
        return {
            "nodes": [
                {
                    "id": "123:456",
                    "name": "Primary Button",
                    "tokens": {
                        "colors": {"bg": "#000"},
                        "typography": {"label": "Inter"}
                    }
                },
                "malformed_node_string", # Should be skipped
                {"id_missing": True} # Should be skipped
            ]
        }
        
    def penpot_timeout_mock(args):
        raise TimeoutError("MCP Server timed out")

    transport = MockTransport({"penpot_search": penpot_search_mock})
    adapter = PenpotAdapter(transport=transport, config={})
    
    # Test valid and malformed parsing
    packages = adapter.search("button")
    assert len(packages) == 1
    assert packages[0].component_id == "123:456"
    assert packages[0].design_tokens.colors["bg"] == "#000"
    print("Penpot schema mapping & malformed rejection: PASSED")
    
    # Test timeout isolation
    timeout_transport = MockTransport({"penpot_search": penpot_timeout_mock})
    adapter.transport = timeout_transport
    empty = adapter.search("button")
    assert len(empty) == 0
    print("Penpot timeout propagation: PASSED")

def test_github_live_payloads():
    def github_read_mock(args):
        if args["path"] == "package.json":
            return {"content": '{"dependencies": {"react": "^18.0.0"}}'}
        elif args["path"] == "README.md":
            return {"content": "# Hello World"}
        raise ValueError("File not found")
        
    transport = MockTransport({
        "github_read_file": github_read_mock
    })
    
    adapter = GitHubAdapter(transport=transport, config={})
    
    deps = adapter.get_dependencies("test/repo")
    assert len(deps) == 1
    assert deps[0]["package"] == "react"
    
    readme = adapter.get_installation_guide("test/repo")
    assert readme == "# Hello World"
    print("GitHub dependencies & README parsing: PASSED")

if __name__ == "__main__":
    test_penpot_live_payloads()
    test_github_live_payloads()
