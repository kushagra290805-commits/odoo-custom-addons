"""Odoo-level runtime contract tests for Phase 47.3 U3."""

import shutil
import tempfile

from odoo.tests import TransactionCase, tagged

from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType
from odoo.addons.nexora_studio.services.connector.integration.connector_executor import (
    ConnectorExecutionTarget,
)
from odoo.addons.nexora_studio.services.generation.core.generation_runtime import (
    GenerationRuntime,
)
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import (
    GenerationStateManager,
)
from odoo.addons.nexora_studio.services.generation.engines.component_discovery_engine import (
    ComponentDiscoveryEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.planning_engine import (
    PlanningEngine,
)
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import (
    PipelineEventBus,
)


@tagged('-at_install', 'post_install', 'phase47_3')
class TestPhase473RuntimeOdoo(TransactionCase):
    def setUp(self):
        super().setUp()
        self.workspace_path = tempfile.mkdtemp(prefix='nexora-phase47-3-')

    def tearDown(self):
        shutil.rmtree(self.workspace_path, ignore_errors=True)
        super().tearDown()

    def _runtime(self):
        return GenerationRuntime(
            ai_provider_manager=self.env['nexora.ai_provider_manager'],
            workspace_path=self.workspace_path,
            event_bus=PipelineEventBus(),
            state_manager=GenerationStateManager(),
            session_id='phase47-3-session',
            generation_id='phase47-3-generation',
            env=self.env,
        )

    def test_explicit_environment_and_single_router(self):
        runtime = self._runtime()

        self.assertIs(runtime.env, self.env)
        self.assertIs(runtime.tools._router, runtime.ucel_router)
        self.assertIs(runtime.orchestrator._router, runtime.ucel_router)
        self.assertIn(ExecutionTargetType.LOCAL, runtime.ucel_router.executors)
        self.assertIn(ExecutionTargetType.CONNECTOR, runtime.ucel_router.executors)
        self.assertIsInstance(
            runtime.ucel_router.executors[ExecutionTargetType.CONNECTOR],
            ConnectorExecutionTarget,
        )

    def test_affected_engine_scopes_are_declared(self):
        runtime = self._runtime()
        planning_scope = runtime.get_scoped_view(PlanningEngine)
        discovery_scope = runtime.get_scoped_view(ComponentDiscoveryEngine)

        self.assertIs(planning_scope.orchestrator, runtime.orchestrator)
        self.assertIs(discovery_scope.env, self.env)
