import os
import unittest
from odoo.tests.common import TransactionCase, tagged
from odoo.addons.nexora_studio.services.providers.component.github_adapter import GitHubComponentProvider
from odoo.addons.nexora_studio.services.providers.component.figma_adapter import FigmaComponentProvider
from odoo.addons.nexora_studio.services.providers.component.shadcn_adapter import ShadcnComponentProvider
from odoo.addons.nexora_studio.services.providers.component.magic_ui_adapter import MagicUIComponentProvider
from odoo.addons.nexora_studio.services.providers.component.aceternity_adapter import AceternityComponentProvider
from odoo.addons.nexora_studio.services.providers.component.react_bits_adapter import ReactBitsComponentProvider
from odoo.addons.nexora_studio.services.providers.component.twentyfirst_dev_adapter import TwentyFirstDevComponentProvider
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderSession, ProviderSandboxPolicy
import uuid

@tagged('post_install', '-at_install', 'phase15c_smoke')
class TestPhase15CLiveSmoke(TransactionCase):
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
        self.context = self.session.to_execution_context()

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1", "Live tests disabled")
    def test_github_live(self):
        provider = GitHubComponentProvider()
        res = provider.execute("import_component", {"repo": "magicuidesign/magicui", "path": "package.json"}, self.context)
        self.assertTrue(res.success)
        self.assertIn("version", res.data.get("code", ""))

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1" and os.environ.get("FIGMA_TOKEN"), "Live tests disabled or missing FIGMA_TOKEN")
    def test_figma_live(self):
        provider = FigmaComponentProvider()
        res = provider.execute("import_component", {"file_key": "some_file", "node_id": "0:1", "token": os.environ.get("FIGMA_TOKEN")}, self.context)
        self.assertTrue(res.success)

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1", "Live tests disabled")
    def test_shadcn_live(self):
        provider = ShadcnComponentProvider()
        res = provider.execute("import_component", {"component_id": "button", "style": "default"}, self.context)
        self.assertTrue(res.success)
        self.assertIn("Button", res.data.get("code", ""))

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1", "Live tests disabled")
    def test_magic_ui_live(self):
        provider = MagicUIComponentProvider()
        res = provider.execute("import_component", {"component_id": "marquee"}, self.context)
        self.assertTrue(res.success)
        self.assertIn("Marquee", res.data.get("code", ""))

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1", "Live tests disabled")
    def test_aceternity_live(self):
        provider = AceternityComponentProvider()
        res = provider.execute("import_component", {"component_id": "aurora-background"}, self.context)
        self.assertTrue(res.success)

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1", "Live tests disabled")
    def test_react_bits_live(self):
        provider = ReactBitsComponentProvider()
        res = provider.execute("import_component", {"component_id": "Animations/SplitText/SplitText"}, self.context)
        self.assertTrue(res.success)

    @unittest.skipUnless(os.environ.get("RUN_LIVE_TESTS") == "1", "Live tests disabled")
    def test_twentyfirst_live(self):
        provider = TwentyFirstDevComponentProvider()
        res = provider.execute("import_component", {"component_id": "magicui-marquee"}, self.context)
        self.assertTrue(res.success)
