# -*- coding: utf-8 -*-
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager
from odoo.addons.nexora_studio.services.source_framework.adapters.penpot_adapter import PenpotAdapter
from odoo.addons.nexora_studio.services.source_framework.adapters.github_adapter import GitHubAdapter
from odoo.addons.nexora_studio.services.source_framework.adapters.internal_adapter import InternalAdapter
from odoo.addons.nexora_studio.services.source_framework.search_engine import SearchEngine

def simulate_federation():
    pm = ProviderManager(env=None)
    pm.register_adapter("penpot", PenpotAdapter(config={}))
    pm.register_adapter("github", GitHubAdapter(config={}))
    pm.register_adapter("internal", InternalAdapter(config={}))
    
    se = SearchEngine(pm)
    
    print("Running end-to-end federation...")
    results = se.search("navbar", builder_context={"react_version": "18.0.0"})
    
    assert len(results) == 3, "Failed to federate across all 3 providers"
    
    provider_names = [res["package"].provenance.provider for res in results]
    assert "penpot" in provider_names
    assert "github" in provider_names
    assert "internal" in provider_names
    
    print("Integration test PASSED")

if __name__ == "__main__":
    simulate_federation()
