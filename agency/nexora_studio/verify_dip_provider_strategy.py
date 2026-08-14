# -*- coding: utf-8 -*-
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from odoo.addons.nexora_studio.services.source_framework.transport.mock_transport import MockTransport
from odoo.addons.nexora_studio.services.source_framework.adapters.penpot_adapter import PenpotAdapter

def test_transport_independence():
    mock_responses = {
        "penpot_get_node": lambda args: {
            "node": {
                "id": args.get("node_id", "test_node_123"),
                "name": "Test Penpot Node",
                "tokens": {
                    "colors": {"primary": "#FF0000"},
                    "typography": {"h1": "24px"},
                    "grids": {"main": "12-column"}
                }
            }
        },
        "penpot_search": lambda args: {"nodes": []}
    }
    
    transport = MockTransport(mock_responses)
    adapter = PenpotAdapter(transport=transport, config={})
    
    package = adapter.get_component("test_node_123")
    
    assert package.design_tokens.colors["primary"] == "#FF0000"
    assert package.design_tokens.typography["h1"] == "24px"
    
    print("Transport Independence Test PASSED")
    
if __name__ == "__main__":
    test_transport_independence()
