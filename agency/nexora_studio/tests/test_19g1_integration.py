import odoo.tests
from odoo.addons.nexora_studio.services.providers.container import bootstrap_container
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderFactory, ProviderDiscovery

@odoo.tests.tagged('post_install', '-at_install')
class TestPhase19G1Integration(odoo.tests.TransactionCase):

    def setUp(self):
        super().setUp()
        self.container = bootstrap_container(env=self.env)
        
    def test_single_registration_path(self):
        """Verifies exactly one provider registration path exists via container"""
        discovery = self.container.resolve(ProviderDiscovery)
        
        # 1. Module Load & Discovery
        providers = discovery.discover_builtin()
        self.assertTrue(len(providers) > 0)
        
        # 2. Registration -> Routes to Container
        report = discovery._compat_service.validate(providers[0])
        print("Validation report:", report.is_compatible, report.failures)
        success = discovery.validate_and_register(providers[0])
        self.assertTrue(success, f"Failed to register provider. Failures: {report.failures}")
        
        # 3. Validation: The container intrinsically holds the class, NOT the wrapper
        metadata = providers[0].get_default_metadata()
        resolved_class = self.container.get_provider_class(metadata.provider_id)
        self.assertEqual(resolved_class, providers[0])
        
    def test_provider_resolution(self):
        """Verifies the factory routes through the container"""
        discovery = self.container.resolve(ProviderDiscovery)
        factory = self.container.resolve(ProviderFactory)
        
        provider_cls = discovery.discover_builtin()[0]
        discovery.validate_and_register(provider_cls)
        
        # Provider instantiation should succeed because factory delegates to container
        provider = factory.create_provider(
            provider_cls.get_default_metadata().provider_id,
            config=None,
            auth=None
        )
        self.assertIsInstance(provider, provider_cls)
