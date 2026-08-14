from odoo.tests.common import TransactionCase, tagged
from odoo.addons.nexora_studio.services.design.intelligence.design_analysis_service import DesignAnalysisService
from odoo.addons.nexora_studio.services.design.intelligence.design_token_service import DesignTokenService
from odoo.addons.nexora_studio.services.design.intelligence.design_extraction_service import DesignExtractionService
from odoo.addons.nexora_studio.services.preview.live_preview_engine import LivePreviewEngine
from odoo.addons.nexora_studio.services.preview.component_preview_renderer import ComponentPreviewRenderer
from odoo.addons.nexora_studio.services.providers.container import GLOBAL_CONTAINER
from odoo.addons.nexora_studio.services.providers.execution_orchestrator import ExecutionOrchestrator
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderSession, ProviderSandboxPolicy, ProviderCategory
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult
from odoo.addons.nexora_studio.services.providers.component.github_adapter import GitHubComponentProvider
from odoo.addons.nexora_studio.services.providers.asset.asset_bridge_provider import AssetBridgeProvider
import uuid
import base64
from unittest.mock import patch, MagicMock

# Create a valid 1x1 GIF base64 for testing PIL
TEST_IMG = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="

@tagged('post_install', '-at_install', 'phase15c')
class TestPhase15C(TransactionCase):

    def setUp(self):
        super().setUp()
        self.session = ProviderSession(
            session_id=str(uuid.uuid4()),
            user_id=1,
            workspace_path="/tmp",
            provider=None,
            auth=None,
            config=None,
            sandbox=ProviderSandboxPolicy.default_restricted(),
            quota=None,
            cost_budget_usd=1.0
        )
        self.orch = GLOBAL_CONTAINER.resolve(ExecutionOrchestrator)

    @patch('odoo.addons.nexora_studio.services.providers.execution_orchestrator.OdooExecutionOrchestrator.execute')
    def test_01_figma_import(self, mock_exec):
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionResult
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest
        mock_exec.return_value = ProviderExecutionResult(success=True, data={"components": ["FigmaButton"]}, metadata={}, execution_ms=10.0)
        data = DesignExtractionService.execute({"url": "figma.com/file/123"}, self.session)
        self.assertIn("components", data)
        self.assertEqual(data["components"][0], "FigmaButton")

    @patch('odoo.addons.nexora_studio.services.providers.network_client.ProviderNetworkClient.request')
    def test_02_github_component_import(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"content": base64.b64encode(b"const GitBtn = () => <div/>;").decode('utf-8'), "encoding": "base64"}
        mock_get.return_value = mock_resp
        
        provider = GitHubComponentProvider()
        req = ProviderExecutionRequest(namespace="github.import_component", payload={"repo": "test/test", "path": "Btn.tsx"}, context=self.session.to_execution_context())
        res = provider.execute(req)
        self.assertTrue(res.success)
        self.assertIn("code", res.data)
        self.assertIn("GitBtn", res.data["code"])

    @patch('odoo.addons.nexora_studio.services.providers.execution_orchestrator.OdooExecutionOrchestrator.execute')
    def test_03_design_token_extraction(self, mock_exec):
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionResult
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest
        mock_exec.return_value = ProviderExecutionResult(success=True, data={"colors": ["#123456"]}, metadata={}, execution_ms=10.0)
        data = DesignTokenService.execute({"image": "base64..."}, self.session)
        self.assertIn("colors", data)
        self.assertEqual(data["colors"][0], "#123456")

    def test_05_preview_rendering(self):
        renderer = ComponentPreviewRenderer("/tmp")
        res = renderer.process(component="Button", props={"label": "Click"})
        self.assertEqual(res["status"], "success")
        self.assertIn("artifact_url", res)
        self.assertIn("base64,", res["artifact_url"])
        
    def test_06_asset_optimization(self):
        provider = AssetBridgeProvider()
        req = ProviderExecutionRequest(namespace="asset.optimize_asset", payload={"file": "icon.png", "content": TEST_IMG}, context=self.session.to_execution_context())
        res = provider.execute(req)
        self.assertTrue(res.success)
        self.assertTrue(res.data.get("is_optimized"))
        self.assertEqual(res.data.get("format"), "png")
        
    @patch('odoo.addons.nexora_studio.services.providers.execution_orchestrator.OdooExecutionOrchestrator.execute')
    def test_07_ai_analysis(self, mock_exec):
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionResult
        from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest
        mock_exec.return_value = ProviderExecutionResult(success=True, data={"accessibility_score": 99}, metadata={}, execution_ms=10.0)
        data = DesignAnalysisService.execute({"layout": "grid"}, self.session)
        self.assertEqual(data["accessibility_score"], 99)
        
    def test_08_provider_platform_integration(self):
        # Verify the global DI container is fully wired
        self.assertIsNotNone(self.orch)
