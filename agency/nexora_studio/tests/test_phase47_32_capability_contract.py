# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, r'D:\ODOO\community\odoo')
from odoo.tools import config
import odoo.modules.module as m
config.parse_config(['-c', r'D:\ODOO\configs\dev.conf'])
m.initialize_sys_path()

import unittest
from unittest.mock import MagicMock, patch
from odoo.addons.nexora_studio.services.design.capability_policy import (
    infer_capabilities,
    backend_required,
    CAPABILITY_VOCABULARY,
    BACKEND_REQUIRED_CAPABILITIES,
    SERVICE_TO_CAPABILITY,
)


class TestCapabilityVocabulary(unittest.TestCase):
    def test_vocabulary_contains_expected_keys(self):
        expected = {
            "products", "customers", "orders", "payments", "inventory",
            "appointments", "bookings", "subscriptions", "memberships",
            "leads", "contacts", "invoicing", "website_content", "forms"
        }
        self.assertEqual(set(CAPABILITY_VOCABULARY.keys()), expected)

    def test_backend_required_mapping_consistent(self):
        for key in CAPABILITY_VOCABULARY:
            self.assertIn(key, BACKEND_REQUIRED_CAPABILITIES)


class TestInferCapabilities(unittest.TestCase):
    def test_infer_from_business_category(self):
        caps = infer_capabilities(
            business_category="ecommerce store",
            services=[],
            features=[],
            goals=[],
            raw_input=""
        )
        self.assertIn("orders", caps)

    def test_infer_from_services(self):
        caps = infer_capabilities(
            business_category="",
            services=["online booking", "payment processing"],
            features=[],
            goals=[],
            raw_input=""
        )
        self.assertIn("bookings", caps)
        self.assertIn("payments", caps)

    def test_infer_from_features(self):
        caps = infer_capabilities(
            business_category="",
            services=[],
            features=["customer portal", "inventory management"],
            goals=[],
            raw_input=""
        )
        self.assertIn("customers", caps)
        self.assertIn("inventory", caps)

    def test_infer_from_goals(self):
        caps = infer_capabilities(
            business_category="",
            services=[],
            features=[],
            goals=["sell subscriptions", "manage memberships"],
            raw_input=""
        )
        self.assertIn("subscriptions", caps)
        self.assertIn("memberships", caps)

    def test_infer_from_raw_input(self):
        caps = infer_capabilities(
            business_category="",
            services=[],
            features=[],
            goals=[],
            raw_input="Need a product catalog with lead capture forms."
        )
        self.assertIn("products", caps)
        self.assertIn("leads", caps)
        self.assertIn("forms", caps)

    def test_no_duplicate_capabilities(self):
        caps = infer_capabilities(
            business_category="orders and order management",
            services=["order"],
            features=[],
            goals=[],
            raw_input=""
        )
        self.assertEqual(caps.count("orders"), 1)

    def test_unknown_terms_ignored(self):
        caps = infer_capabilities(
            business_category="",
            services=["something obscure"],
            features=[],
            goals=[],
            raw_input=""
        )
        self.assertEqual(caps, [])


class TestBackendRequired(unittest.TestCase):
    def test_static_site_false(self):
        caps = []
        self.assertFalse(backend_required(caps))

    def test_ecommerce_true(self):
        caps = ["orders", "payments"]
        self.assertTrue(backend_required(caps))

    def test_booking_true(self):
        caps = ["bookings"]
        self.assertTrue(backend_required(caps))

    def test_customer_accounts_true(self):
        caps = ["customers"]
        self.assertTrue(backend_required(caps))

    def test_marketing_site_false(self):
        caps = ["website_content"]  # even dynamic content might need backend
        self.assertTrue(backend_required(caps))  # website_content is marked True

    def test_only_forms_true(self):
        caps = ["forms"]
        self.assertTrue(backend_required(caps))

    def test_unknown_capability_false(self):
        caps = ["unknown"]
        self.assertFalse(backend_required(caps))


class TestServiceToCapabilityMapping(unittest.TestCase):
    def test_all_mappings_have_known_capability(self):
        for service, cap in SERVICE_TO_CAPABILITY.items():
            self.assertIn(cap, CAPABILITY_VOCABULARY)


class TestIntegrationWithRequirementEngine(unittest.TestCase):
    def test_requirement_engine_populates_capabilities(self):
        from odoo.addons.nexora_studio.services.generation.core.generation_context import (
            WebsiteGenerationArtifact,
            RequirementModel,
        )
        from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
            RequirementEngine,
        )
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(raw_input="ecommerce with products and payments")
        )
        runtime = MagicMock()
        engine = RequirementEngine(MagicMock())
        result = engine.execute(artifact, runtime)
        self.assertTrue(result.success)
        req = result.artifact.requirements
        self.assertIn("products", req.capabilities)
        self.assertIn("payments", req.capabilities)
        self.assertTrue(req.backend_required)

    def test_static_marketing_site(self):
        from odoo.addons.nexora_studio.services.generation.core.generation_context import (
            WebsiteGenerationArtifact,
            RequirementModel,
        )
        from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
            RequirementEngine,
        )
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(raw_input="Marketing agency landing page")
        )
        runtime = MagicMock()
        engine = RequirementEngine(MagicMock())
        result = engine.execute(artifact, runtime)
        req = result.artifact.requirements
        self.assertEqual(req.capabilities, [])
        self.assertFalse(req.backend_required)

    def test_restaurant_booking(self):
        from odoo.addons.nexora_studio.services.generation.core.generation_context import (
            WebsiteGenerationArtifact,
            RequirementModel,
        )
        from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import (
            RequirementEngine,
        )
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(raw_input="Restaurant with online reservations")
        )
        runtime = MagicMock()
        engine = RequirementEngine(MagicMock())
        result = engine.execute(artifact, runtime)
        req = result.artifact.requirements
        self.assertIn("bookings", req.capabilities)
        self.assertTrue(req.backend_required)


if __name__ == "__main__":
    unittest.main(verbosity=2)