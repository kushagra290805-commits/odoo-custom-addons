from . import models
from . import services
from . import wizard

try:
    from . import controllers
except ImportError:
    # controllers import Odoo HTTP/ORM modules that may not be available
    # in standalone unit test environments
    pass

def post_init_provider_platform(env):
    from .services.providers.container import bootstrap_container
    bootstrap_container(env)
    
    # Phase 18.2 Migration
    from .migrations.migration_18_2_default_model import migrate_default_models
    migrate_default_models(env)

    # Phase 23.11 Architecture Remediation (ADR-0015 Initial Sync)
    env['nexora.capability_discovery_service'].execute_discovery()

    # Phase 23.29 Canonical Capability Registry Bootstrap
    env['nexora.registry_bootstrap_service'].execute_bootstrap()

def post_load_provider_platform():
    from .services.providers.container import bootstrap_container
    bootstrap_container(None)
    
    try:
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
        ConnectorPlatformBootstrap.get_instance().bootstrap(None)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to bootstrap connector platform: %s", e)
