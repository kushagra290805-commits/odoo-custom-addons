# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.nexora_studio.services.builder_intelligence.intelligence_engine import IntelligenceEngine
from odoo.addons.nexora_studio.services.builder_intelligence.change_planning_engine import ChangePlanningEngine
from odoo.addons.nexora_studio.services.builder_intelligence.safe_execution_engine import SafeExecutionEngine
from odoo.addons.nexora_studio.services.builder_intelligence.difference_engine import DifferenceEngine
from odoo.addons.nexora_studio.services.builder_intelligence.builder_chat_engine import BuilderChatEngine
from odoo.addons.nexora_studio.services.builder_intelligence.workspace_graph_service import WorkspaceGraphService

import json

@tagged('phase17_intelligence_hardening', 'post_install', '-at_install')
class TestPhase17BuilderIntelligenceHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['nexora.builder_configuration'].create({'name': 'Test Config'})
        self.session = self.env['nexora.builder_session'].create({
            'name': 'Test Session',
            'builder_configuration_id': self.config.id,
            'status': 'draft',
            'runtime_state': 'stopped'
        })
        self.version_1 = self.env['nexora.builder.workspace.version'].create({
            'name': 'v1',
            'session_id': self.session.id,
            'component_tree_data': json.dumps({"nodes": [{"id": "hero_1", "component_id": "hero_shadcn", "parent_id": "root"}, {"id": "root", "type": "page"}], "dependencies": ["react"]}),
            'theme_data': json.dumps({"colors": {"primary": "#000000"}})
        })
        self.session.write({'active_version_id': self.version_1.id})
        
        class MockOrchestrator:
            def execute(self, category, operation, payload, features, session=None):
                class Res:
                    def __init__(self, s, d):
                        self.success = s
                        self.data = d
                if operation == "search_components":
                    return Res(True, {"components": [{"component_id": "new_hero", "score": 95, "tags": ["react", "tailwind"], "package": type('obj', (object,), {'download_count': 100, 'last_updated': '2026-07-28', 'github_stars': 50})()}]})
                if operation == "import_component":
                    return Res(True, {"code": "export const Hero = () => <div/>;"})
                if operation == "generate_structured_data":
                    prompt = payload.get("prompt", "")
                    if "malformed" in prompt:
                        return Res(False, {})
                    if "ambiguous" in prompt:
                        return Res(True, {"json": {"affected_pages": [], "affected_components": [], "theme_modifications": False, "layout_modifications": False, "asset_modifications": False, "dependency_changes": False, "ambiguity_detected": True, "missing_information": ["Target component"], "complexity": "low", "estimated_cost": 0.0}})
                    return Res(True, {"json": {"affected_pages": ["/"], "affected_components": ["hero_shadcn"], "theme_modifications": True, "layout_modifications": False, "asset_modifications": False, "dependency_changes": False, "ambiguity_detected": False, "complexity": "medium", "estimated_cost": 0.1}})
                return Res(False, {})
        self.orchestrator = MockOrchestrator()

    # --- Scenario 1: AI Intent Parsing (Valid) ---
    def test_01_intent_parsing_valid(self):
        engine = IntelligenceEngine(self.orchestrator)
        impact = engine.analyze_instruction("Update the hero component theme", self.version_1, self.session)
        self.assertIn("hero_shadcn", impact["affected_components"])
        self.assertTrue(impact["theme_changes"])
        self.assertFalse(impact.get("ambiguity_detected", False))

    # --- Scenario 2: AI Intent Parsing (Malformed handling) ---
    def test_02_intent_parsing_malformed(self):
        engine = IntelligenceEngine(self.orchestrator)
        with self.assertRaises(ValueError):
            engine.analyze_instruction("malformed trigger", self.version_1, self.session)

    # --- Scenario 3: AI Intent Parsing (Ambiguity) ---
    def test_03_intent_parsing_ambiguity(self):
        engine = IntelligenceEngine(self.orchestrator)
        impact = engine.analyze_instruction("ambiguous instruction", self.version_1, self.session)
        self.assertEqual(len(impact["affected_components"]), 0)

    # --- Scenario 4: Change Planning ---
    def test_04_execution_planning(self):
        engine = BuilderChatEngine(self.orchestrator)
        plan = engine.process_chat_request("Update the hero", self.session)
        self.assertIsNotNone(plan)
        payload = json.loads(plan.plan_payload)
        self.assertTrue(any(s.get("action") == "update_theme" for s in payload.get("steps", [])))

    # --- Scenario 5: Difference Engine Diffs ---
    def test_05_workspace_diff(self):
        diff = DifferenceEngine()
        proposed = {
            "component_tree_data": json.dumps({"nodes": [{"id": "hero_1", "component_id": "hero_shadcn"}, {"id": "footer_1", "component_id": "footer_ui"}]}),
            "theme_data": json.dumps({"colors": {"primary": "#ffffff"}})
        }
        res = diff.generate_changeset(self.version_1, proposed)
        self.assertIn("footer_ui", res["changeset"]["added_components"])
        self.assertTrue(res["changeset"]["theme_changed"])
        self.assertIn("Added 1 components", res["summary"])

    # --- Scenario 6: Graph Traversal - Parent Lookup ---
    def test_06_graph_parent_lookup(self):
        graph = WorkspaceGraphService(self.version_1)
        parent = graph.get_parent("hero_1")
        self.assertIsNotNone(parent)
        self.assertEqual(parent["id"], "root")

    # --- Scenario 7: Graph Traversal - Child Lookup ---
    def test_07_graph_child_lookup(self):
        graph = WorkspaceGraphService(self.version_1)
        children = graph.get_children("root")
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["id"], "hero_1")

    # --- Scenario 8: Graph Traversal - Subtree ---
    def test_08_graph_subtree(self):
        graph = WorkspaceGraphService(self.version_1)
        nodes = graph.traverse_subtree("root")
        self.assertEqual(len(nodes), 1)

    # --- Scenario 9: Safe Execution (Success) ---
    def test_09_execution_success(self):
        plan = self.env['nexora.builder.execution_plan'].create({
            'name': 'Test Plan',
            'session_id': self.session.id,
            'plan_payload': json.dumps({"instruction": "test", "steps": [{"action": "update_theme"}, {"action": "replace_component"}]}),
            'status': 'draft'
        })
        executor = SafeExecutionEngine(self.orchestrator)
        new_version = executor.execute_plan(plan, self.session)
        self.assertIsNotNone(new_version)
        self.assertEqual(plan.status, 'pending_approval')
        self.assertIn("Added", new_version.change_summary)

    # --- Scenario 10: Event Publication (Success Path) ---
    def test_10_execution_events_published(self):
        events_before = self.env['nexora.runtime_event'].search_count([('builder_session_id', '=', self.session.id)])
        self.test_09_execution_success()
        events_after = self.env['nexora.runtime_event'].search_count([('builder_session_id', '=', self.session.id)])
        self.assertTrue(events_after > events_before)
        
    # --- Scenario 11: Validation Failure Rejection ---
    def test_11_validation_failure(self):
        # We mock DesignReviewEngine to fail
        executor = SafeExecutionEngine(self.orchestrator)
        class MockReview:
            def evaluate_graph(self, graph):
                return {"is_valid": False, "errors": ["Mock Error"]}
        executor.design_review_engine = MockReview()
        
        plan = self.env['nexora.builder.execution_plan'].create({
            'name': 'Test Plan Fail',
            'session_id': self.session.id,
            'plan_payload': json.dumps({"steps": []}),
            'status': 'draft'
        })
        res = executor.execute_plan(plan, self.session)
        self.assertIsNone(res)
        self.assertEqual(plan.status, 'rolled_back')
        self.assertIn("Validation failed", plan.rollback_reason)

    # --- Scenario 12: Rollback Restores Active Version ---
    def test_12_rollback_state(self):
        self.test_11_validation_failure()
        self.assertEqual(self.session.active_version_id.id, self.version_1.id)

    # --- Scenario 13: Approval / Commit ---
    def test_13_approval_commit(self):
        plan = self.env['nexora.builder.execution_plan'].create({'name': 'T', 'session_id': self.session.id, 'plan_payload': '{}'})
        executor = SafeExecutionEngine(self.orchestrator)
        nv = executor.execute_plan(plan, self.session)
        executor.commit_version(nv)
        self.assertEqual(nv.approval_status, 'approved')
        self.assertEqual(self.session.active_version_id.id, nv.id)

    # --- Scenario 14: Rejection Restores ---
    def test_14_rejection_restores(self):
        plan = self.env['nexora.builder.execution_plan'].create({'name': 'T2', 'session_id': self.session.id, 'plan_payload': '{}'})
        executor = SafeExecutionEngine(self.orchestrator)
        nv = executor.execute_plan(plan, self.session)
        executor.rollback_version(nv)
        self.assertEqual(nv.approval_status, 'rejected')
        # Rejection implies active version is untouched
        self.assertEqual(self.session.active_version_id.id, self.version_1.id)

    # --- Scenario 15: Hash Determinism ---
    def test_15_version_hashing(self):
        v2 = self.env['nexora.builder.workspace.version'].create({
            'name': 'v2',
            'session_id': self.session.id,
            'component_tree_data': self.version_1.component_tree_data,
            'theme_data': self.version_1.theme_data
        })
        self.assertEqual(v2.snapshot_hash, self.version_1.snapshot_hash)
        
    # --- Scenario 16: Component Ranking Pipeline Usage ---
    def test_16_component_replacement_engine(self):
        from odoo.addons.nexora_studio.services.builder_intelligence.component_replacement_engine import ComponentReplacementEngine
        engine = ComponentReplacementEngine(self.orchestrator)
        
        # Mock ranking pipeline to avoid complex package dependencies in this unit test
        class MockPipeline:
            def rank_components(self, components):
                for c in components:
                    c['score'] = 99
                return components
        engine.ranking_pipeline = MockPipeline()
        
        res = engine.replace_component("hero_1", "I need a better hero", self.session)
        self.assertTrue(res["success"])
        self.assertEqual(res["new_component_id"], "new_hero")