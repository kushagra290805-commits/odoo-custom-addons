from odoo import models, api
import os
import hashlib
import json
import logging
from .repository import CapabilityRepository
from .models import CapabilityManifest, ExecutionTargetType

_logger = logging.getLogger(__name__)

def _parse_registry_manifests(registry_path: str) -> list:
    """Parses mcp_registry.json into CapabilityManifest objects."""
    if not os.path.exists(registry_path):
        return []
        
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            raw_config = data.get("mcpServers", {})
    except Exception as e:
        _logger.error(f"Failed to load MCP registry from {registry_path}: {e}")
        return []

    manifests = []
    for provider_id, conf in raw_config.items():
        namespace = conf.get("namespace")
        if not namespace:
            continue
            
        # Phase 44.2 (W2 / ADR-0068): registry-backed MCP capabilities are
        # connector-backed. Transport kind (stdio/sse) is a connector concern,
        # not an execution-target concern. They execute via
        # ConnectorExecutionTarget -> ConnectorRuntime -> McpConnector.
        manifest = CapabilityManifest(
            namespace=namespace,
            display_name=conf.get("display_name", provider_id),
            target_type=ExecutionTargetType.CONNECTOR,
            version="1.0.0",
            aliases=[],
            input_schema={},
            output_schema={},
            metadata={
                "provider": conf.get("provider_id", provider_id),
                "category": conf.get("business_capability", "unknown"),
                "implementation_model": f"nexora.provider.{provider_id}",
                "transport": conf.get("transport"),
                "enabled": conf.get("enabled", False),
                "lifecycle": conf.get("lifecycle", "planned"),
                "supported_capabilities": conf.get("supported_capabilities", []),
                "priority": conf.get("priority", 50),
                "provider_type": conf.get("provider_type", "unknown"),
                "limits": conf.get("limits", {}),
                "estimated_latency_ms": conf.get("estimated_latency_ms", 500),
                "requires_authentication": conf.get("requires_authentication", False)
            }
        )
        manifests.append(manifest)
    return manifests

class RegistryBootstrapService(models.AbstractModel):
    _name = 'nexora.registry_bootstrap_service'
    _description = 'Registry Bootstrap Service'

    @api.model
    def execute_bootstrap(self):
        """
        Idempotent bootstrap of capability registries into the Odoo database.
        """
        _logger.info("Executing Capability Registry Bootstrap...")
        
        registry_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'config', 'mcp_registry.json'
        )
        registry_path = os.path.normpath(registry_path)

        if not os.path.exists(registry_path):
            _logger.warning(f"Registry config not found at {registry_path}")
            return {"status": "skipped", "reason": "file_not_found"}

        # Calculate hash for idempotency checking
        with open(registry_path, 'rb') as f:
            content = f.read()
            current_hash = hashlib.sha256(content).hexdigest()

        # Check hash against a system parameter
        stored_hash = self.env['ir.config_parameter'].sudo().get_param('nexora.mcp_registry_hash')
        if stored_hash == current_hash:
            # Phase 44.2 (W4 / G-08): a matching hash only proves the file is
            # unchanged, not that DB state exists. If registry rows are missing
            # (e.g. DB restored without parameters), force a resync.
            registry_count = self.env['nexora.capability_registry'].sudo().search_count(
                [('implementation_model', 'like', 'nexora.provider.')]
            )
            if registry_count:
                _logger.info("Registry hash unchanged. Skipping bootstrap synchronization.")
                return {"status": "skipped", "reason": "hash_match"}
            _logger.warning("Registry hash matches but registry rows are missing. Forcing resync.")

        _logger.info(f"Registry hash changed ({stored_hash} -> {current_hash}). Synchronizing...")

        manifests = _parse_registry_manifests(registry_path)

        # Phase 44.2 (W4 / G-03): never synchronize an empty manifest set —
        # that would deactivate every existing registry capability.
        if not manifests:
            _logger.error("Registry parse produced no manifests; aborting sync to protect existing state.")
            return {"status": "error", "reason": "empty_registry_parse"}
        
        # Enforce lifecycle-aware enablement rules
        for manifest in manifests:
            lifecycle = manifest.metadata.get('lifecycle', 'planned')
            if lifecycle in ['verified', 'production']:
                manifest.metadata['enabled'] = True
            elif lifecycle in ['planned', 'deprecated']:
                manifest.metadata['enabled'] = False
            # If experimental, we leave it as configured in JSON
        
        repository = CapabilityRepository(self.env)
        repository.synchronize_manifests(manifests)
        
        # Save new hash
        self.env['ir.config_parameter'].sudo().set_param('nexora.mcp_registry_hash', current_hash)
        
        _logger.info(f"Successfully synchronized {len(manifests)} capabilities.")
        return {"status": "success", "synchronized_count": len(manifests)}
