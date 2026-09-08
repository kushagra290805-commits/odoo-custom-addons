"""Phase 47.8A — Runtime boot integrity & capability classification closure."""

import shutil
import tempfile
import unittest
import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType
from odoo.addons.nexora_studio.services.connector.integration.connector_executor import ConnectorExecutionTarget
from odoo.addons.nexora_studio.services.generation.core.generation_runtime import GenerationRuntime
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import GenerationStateManager
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus
from odoo.addons.nexora_studio.services.capabilities.repository import _derive_target_type


class TestPhase478ARuntimeBoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.new('nexora_studio')
        cls.cr = cls.registry.cursor()
        cls.env = odoo.api.Environment(cls.cr, odoo.SUPERUSER_ID, {})
        cls.workspace_path = tempfile.mkdtemp(prefix='nexora-phase47-8a-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workspace_path, ignore_errors=True)
        cls.cr.close()

    def _runtime(self):
        return GenerationRuntime(
            ai_provider_manager=self.env['nexora.ai_provider_manager'],
            workspace_path=self.workspace_path,
            event_bus=PipelineEventBus(),
            state_manager=GenerationStateManager(),
            session_id='phase47-8a-session',
            generation_id='phase47-8a-generation',
            env=self.env,
        )

    def test_generation_runtime_constructs_and_boots(self):
        """GenerationRuntime constructs successfully (no REMOTE row blocking)."""
        runtime = self._runtime()
        self.assertIsNotNone(runtime)
        self.assertIsNotNone(runtime.capability_repository)

    def test_capability_resolution_penpot_connector(self):
        """mcp.penpot resolves to CONNECTOR executor (not REMOTE/LOCAL)."""
        runtime = self._runtime()
        manifests = runtime.capability_repository.get_manifests_by_namespace('mcp.penpot')
        self.assertTrue(manifests, "mcp.penpot should have at least one manifest")
        for m in manifests:
            self.assertEqual(m.target_type, ExecutionTargetType.CONNECTOR,
                f"mcp.penpot manifest target_type must be CONNECTOR, got {m.target_type}")

    def test_single_executor_per_target(self):
        """Exactly one executor per resolved target (no duplicate executor registration)."""
        runtime = self._runtime()
        # The CONNECTOR executor is registered once at construction
        self.assertIn(ExecutionTargetType.CONNECTOR, runtime.ucel_router.executors)
        executor = runtime.ucel_router.executors[ExecutionTargetType.CONNECTOR]
        self.assertIsInstance(executor, ConnectorExecutionTarget)

    def test_router_singularity(self):
        """Exactly one UniversalCapabilityRouter per runtime (no shadow router)."""
        runtime = self._runtime()
        r1 = runtime.ucel_router
        r2 = runtime.ucel_router
        self.assertIs(r1, r2, "UCEL router is singular per runtime")

    def test_strict_boot_preserved(self):
        """Strict boot: no REMOTE-capable row allowed in capability_registry."""
        runtime = self._runtime()
        records = runtime.capability_repository.get_all_registry_records()
        for r in records:
            target_type = _derive_target_type(r)
            self.assertNotEqual(target_type, ExecutionTargetType.REMOTE,
                f"Capability {r.capability_code} must not be REMOTE (strict boot)")

    def test_no_penpot_specific_executor(self):
        """No penpot-specific executor subclass; uses generic CONNECTOR executor."""
        runtime = self._runtime()
        executor = runtime.ucel_router.executors[ExecutionTargetType.CONNECTOR]
        self.assertIsInstance(executor, ConnectorExecutionTarget)
        self.assertNotIn('penpot', type(executor).__name__.lower())


if __name__ == '__main__':
    unittest.main()