# -*- coding: utf-8 -*-
import sys
import os

sys.path.append("D:\\ODOO\\community\\odoo")
import odoo
import odoo.addons
odoo.addons.__path__.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from odoo.addons.nexora_studio.services.source_framework.domain_models import ComponentPackage
from odoo.addons.nexora_studio.services.source_framework.adapters.base_adapter import BaseProviderAdapter
from odoo.addons.nexora_studio.services.source_framework.adapters.penpot_adapter import PenpotAdapter
from odoo.addons.nexora_studio.services.source_framework.adapters.github_adapter import GitHubAdapter
from odoo.addons.nexora_studio.services.source_framework.adapters.internal_adapter import InternalAdapter
from odoo.addons.nexora_studio.services.source_framework.provider_health_monitor import ProviderHealthMonitor
from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager
from odoo.addons.nexora_studio.services.source_framework.metadata_normalizer import MetadataNormalizer
from odoo.addons.nexora_studio.services.source_framework.dependency_resolver import DependencyResolver
from odoo.addons.nexora_studio.services.source_framework.compatibility_checker import CompatibilityChecker
from odoo.addons.nexora_studio.services.source_framework.quality_scorer import QualityScorer
from odoo.addons.nexora_studio.services.source_framework.search_engine import SearchEngine

def test_health_monitor():
    hm = ProviderHealthMonitor()
    assert hm.check_health("test_provider") == True
    hm.record_failure("test_provider")
    hm.record_failure("test_provider")
    hm.record_failure("test_provider")
    assert hm.check_health("test_provider") == True
    hm.record_failure("test_provider")
    assert hm.check_health("test_provider") == False
    print("test_health_monitor PASSED")

def test_provider_manager():
    pm = ProviderManager(env=None)
    penpot = PenpotAdapter(config={})
    pm.register_adapter("penpot", penpot)
    
    capable = pm.get_capable_providers("SEARCH")
    assert "penpot" in capable
    
    capable = pm.get_capable_providers("DOWNLOAD")
    assert "penpot" not in capable
    
    res = pm.route_request("penpot", "search", "button")
    assert len(res) == 1
    assert res[0].name == "Penpot Node search_res_button"
    print("test_provider_manager PASSED")
    
def test_search_engine():
    pm = ProviderManager(env=None)
    pm.register_adapter("github", GitHubAdapter(config={}))
    pm.register_adapter("internal", InternalAdapter(config={}))
    
    se = SearchEngine(pm)
    results = se.search("card", builder_context={"react_version": "18.0.0"})
    
    assert len(results) == 2
    assert "score" in results[0]
    assert results[0]["package"].compatibility_report["is_compatible"] == True
    print("test_search_engine PASSED")

if __name__ == "__main__":
    test_health_monitor()
    test_provider_manager()
    test_search_engine()
