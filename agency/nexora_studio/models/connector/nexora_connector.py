# -*- coding: utf-8 -*-
"""
nexora.connector — Root Connector Entity (Odoo Model)
Part 7 of Phase 26 — Universal Connector Platform Foundation.

This is the primary Odoo model that backs the ConnectorRegistry.
All connector lifecycle state is authoritative here.
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class NexoraConnector(models.Model):
    _name = 'nexora.connector'
    _description = 'Nexora Connector'
    _order = 'name asc'
    _rec_name = 'name'

    @api.model
    def _register_hook(self):
        super()._register_hook()
        # Trigger the persistent runtime upgrade and async reconciliation
        try:
            from odoo.addons.nexora_studio.services.connector.integration.bootstrap import ConnectorPlatformBootstrap
            bootstrap = ConnectorPlatformBootstrap.get_instance()
            bootstrap.bootstrap(self.env)
        except Exception as e:
            _logger.error("NexoraConnector._register_hook: Failed to bootstrap Connector Platform: %s", e)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(string='Name', required=True)
    connector_id = fields.Char(
        string='Connector ID', required=True, index=True,
        help='Globally unique identifier (reverse-DNS style, e.g., com.nexora.github).'
    )
    connector_type_id = fields.Many2one(
        'nexora.connector_type', string='Connector Type',
        required=True, ondelete='restrict', index=True
    )
    description = fields.Text(string='Description')
    author = fields.Char(string='Author')
    homepage_url = fields.Char(string='Homepage URL')
    documentation_url = fields.Char(string='Documentation URL')
    tags = fields.Char(string='Tags', help='Comma-separated tags.')

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------
    version = fields.Char(string='Version', required=True, default='0.0.0')

    # ------------------------------------------------------------------
    # Lifecycle State
    # ------------------------------------------------------------------
    state = fields.Selection([
        ('registered', 'Registered'),
        ('discovered', 'Discovered'),
        ('downloaded', 'Downloaded'),
        ('installed', 'Installed'),
        ('configured', 'Configured'),
        ('authenticated', 'Authenticated'),
        ('validated', 'Validated'),
        ('healthy', 'Healthy'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('disabled', 'Disabled'),
        ('failed', 'Failed'),
        ('updating', 'Updating'),
        ('removed', 'Removed'),
    ], string='Lifecycle State', default='registered', required=True, index=True)

    enabled = fields.Boolean(
        string='Enabled', compute='_compute_enabled', store=True, index=True
    )
    error_message = fields.Text(string='Error Message', readonly=True)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    health_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('failed', 'Failed'),
    ], string='Health Status', default='unknown', index=True)
    last_health_check = fields.Datetime(string='Last Health Check')

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    manifest_json = fields.Text(
        string='Manifest (JSON)', default='{}',
        help='Full ConnectorManifest serialized as JSON.'
    )
    checksum = fields.Char(string='Checksum (SHA-256)')

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------
    installed_at = fields.Datetime(string='Installed At')
    registered_at = fields.Datetime(string='Registered At', default=fields.Datetime.now)

    # ------------------------------------------------------------------
    # MCP Extension (Phase 28)
    # ------------------------------------------------------------------
    mcp_server_config_ids = fields.One2many(
        'nexora.mcp_server_config', 'connector_id', string='MCP Server Configuration'
    )
    mcp_credential_ids = fields.One2many(
        'nexora.mcp_credential', 'connector_id', string='MCP Credentials'
    )
    mcp_discovered_tool_ids = fields.One2many(
        'nexora.mcp_discovered_tool', 'connector_id', string='Discovered Capabilities'
    )

    def action_test_mcp_connection(self):
        """Open the MCP connection test wizard."""
        self.ensure_one()
        from odoo.exceptions import AccessError
        if not self.env.user.has_group('nexora_studio.group_nexora_admin'):
            raise AccessError("Administrator privileges required to test MCP connections.")
            
        wizard = self.env['nexora.mcp_connection_test_wizard'].create({
            'connector_id': self.id,
        })
        return {
            'name': 'Test MCP Connection',
            'type': 'ir.actions.act_window',
            'res_model': 'nexora.mcp_connection_test_wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_test_tool_execution(self):
        """E2E test endpoint: execute echo tool on this connector."""
        self.ensure_one()
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
        from odoo.addons.nexora_studio.services.connector.integration.connector_executor import ConnectorExecutionTarget
        
        runtime = get_connector_runtime()
        target = ConnectorExecutionTarget(runtime)
        
        payload = {
            'namespace': 'tools.call',
            'inputs': {
                'name': 'echo',
                'arguments': {'message': 'Hello from MCP Onboarding!'}
            },
            'context': {
                'connector_id': self.connector_id,
                'session_id': 'e2e-test-123'
            },
            'timeout': 30.0
        }
        
        result = target.execute(payload)
        return {
            'success': getattr(result, 'success', False),
            'data': getattr(result, 'result', None),
            'error': getattr(result, 'logs', []),
        }

    def action_discover_mcp_capabilities(self):
        """Run MCP capability discovery."""
        self.ensure_one()
        from odoo.exceptions import AccessError, UserError
        if not self.env.user.has_group('nexora_studio.group_nexora_admin'):
            raise AccessError("Administrator privileges required to discover capabilities.")
            
        if self.state != 'running':
            raise UserError("Connector must be running to discover capabilities.")
            
        try:
            from odoo.addons.nexora_studio.services.connector.onboarding.capability_discovery import McpCapabilityDiscoveryService
            from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime, ConnectorPlatformBootstrap
            from odoo.addons.nexora_studio.services.connector.runtime.connector_runtime import ConnectorRuntime
            
            runtime = get_connector_runtime()
            if runtime is None:
                ConnectorPlatformBootstrap.get_instance().bootstrap(self.env)
                runtime = get_connector_runtime()
            if runtime is None:
                from odoo.addons.nexora_studio.services.connector.registry.persistence.odoo_adapter import OdooConnectorPersistenceAdapter
                runtime = ConnectorRuntime(persistence_port=OdooConnectorPersistenceAdapter(self.env))
                runtime.startup()
                
            service = McpCapabilityDiscoveryService(runtime, self.env)
            service.discover(self)
        except Exception as e:
            import traceback
            raise UserError(f"Discovery failed: {e}\nRuntime Type: {type(runtime)}\n{traceback.format_exc()}")

    # ------------------------------------------------------------------
    # Related records
    # ------------------------------------------------------------------

    capability_ids = fields.One2many('nexora.connector_capability', 'connector_id', string='Capabilities')
    installation_id = fields.Many2one('nexora.connector_installation', string='Installation', compute='_compute_installation', store=False)
    configuration_ids = fields.One2many('nexora.connector_configuration', 'connector_id', string='Configuration')
    dependency_ids = fields.One2many('nexora.connector_dependency', 'connector_id', string='Dependencies')
    health_ids = fields.One2many('nexora.connector_health', 'connector_id', string='Health Records')
    event_ids = fields.One2many('nexora.connector_event', 'connector_id', string='Events')
    log_ids = fields.One2many('nexora.connector_log', 'connector_id', string='Logs')
    diagnostic_ids = fields.One2many('nexora.connector_diagnostic', 'connector_id', string='Diagnostics')

    _sql_constraints = [
        ('unique_connector_id', 'unique(connector_id)', 'Connector ID must be globally unique!'),
    ]

    @api.depends('state')
    def _compute_enabled(self):
        active_states = {'running', 'healthy', 'paused'}
        for record in self:
            record.enabled = record.state in active_states

    def _compute_installation(self):
        for record in self:
            installation = self.env['nexora.connector_installation'].search(
                [('connector_id', '=', record.id), ('state', '=', 'installed')], limit=1
            )
            record.installation_id = installation

    def action_enable(self):
        """Operator action: request activation and only persist RUNNING after runtime activation succeeds."""
        for record in self:
            if record.state in ('registered', 'installed', 'healthy', 'validated', 'configured', 'disabled', 'failed'):
                connector_type = record.connector_type_id.type_code if record.connector_type_id else ''
                if connector_type == 'mcp':
                    try:
                        from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import McpOnboardingService
                        runtime = self._get_global_runtime()
                        if not runtime:
                            raise Exception("Connector Platform is not initialized.")
                        onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, self.env)
                        
                        # 1. Clear any old session
                        onboarding.deregister_connector(record.connector_id)
                        
                        # 2. Attempt registration (this validates config, credentials, handshake)
                        onboarding.register_connector(record)
                        
                        # 3. Only if successful, persist running
                        record.state = 'running'
                        record.error_message = ''
                    except Exception as e:
                        # 4. If failed, persist failed immediately
                        record.state = 'failed'
                        record.error_message = f"Activation failed: {str(e)}"
                else:
                    record.state = 'running'
                    record.error_message = ''

    def action_disable(self):
        """Operator action: disable connector."""
        for record in self:
            if record.state in ('running', 'paused', 'healthy', 'failed'):
                record.state = 'disabled'

    def action_remove(self):
        """Operator action: remove connector."""
        for record in self:
            if record.state not in ('disabled', 'failed'):
                raise ValidationError(
                    _("Connector must be Disabled or Failed before removal. Current state: %s") % record.state
                )
            record.state = 'removed'

    # ------------------------------------------------------------------
    # Health Monitoring (Cron)
    # ------------------------------------------------------------------

    @api.model
    def _cron_check_health(self):
        """Periodic background job to probe health of all eligible running connectors."""
        from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
        
        runtime = get_connector_runtime()
        if not runtime or not runtime._initialized:
            return
            
        eligible_connectors = self.search([('state', 'in', ['running', 'healthy', 'degraded'])])
        
        for record in eligible_connectors:
            try:
                # 1. Dispatch probe via runtime (this triggers dispatcher -> health_monitor)
                health_result = runtime.probe_health(record.connector_id)
                
                if health_result:
                    from datetime import datetime
                    # 2. Update canonical health tracking fields on Odoo record
                    update_vals = {
                        'health_status': health_result.status.value,
                        'last_health_check': datetime.utcnow()
                    }
                    if health_result.status.value == 'failed':
                        update_vals['error_message'] = getattr(health_result, 'error_detail', '')
                        
                    record.write(update_vals)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Health check failed for connector %s", record.connector_id)

    # ------------------------------------------------------------------
    # Phase 28 — ORM Hooks for Runtime Synchronization
    # ------------------------------------------------------------------

    def write(self, vals):
        """Track state changes and synchronize ConnectorRuntime for MCP connectors."""
        previous_states = {rec.id: rec.state for rec in self}
        result = super().write(vals)

        if 'state' in vals:
            for record in self:
                prev_state = previous_states.get(record.id)
                if prev_state != record.state:
                    self._trigger_runtime_sync(record, prev_state)

        return result

    def unlink(self):
        """Ensure runtime cleanup before deletion."""
        for record in self:
            self._trigger_runtime_unlink(record)
        return super().unlink()

    def _trigger_runtime_sync(self, record, previous_state):
        """Trigger ConnectorRuntimeSynchronizer.sync_on_write for MCP connectors."""
        try:
            connector_type = record.connector_type_id.type_code if record.connector_type_id else ''
            if connector_type != 'mcp':
                return
            from odoo.addons.nexora_studio.services.connector.onboarding.runtime_synchronizer import (
                ConnectorRuntimeSynchronizer
            )
            from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import (
                McpOnboardingService
            )
            from odoo.addons.nexora_studio.services.connector.registry.capability_index import ConnectorCapabilityIndex

            runtime = self._get_global_runtime()
            if runtime is None:
                return
            onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, self.env)
            synchronizer = ConnectorRuntimeSynchronizer(onboarding)
            synchronizer.sync_on_write(record, previous_state)
        except Exception as e:
            _logger.warning(
                "nexora.connector: runtime sync failed for '%s': %s",
                record.connector_id, type(e).__name__
            )

    def _trigger_runtime_unlink(self, record):
        """Trigger ConnectorRuntimeSynchronizer.sync_on_unlink for MCP connectors."""
        try:
            connector_type = record.connector_type_id.type_code if record.connector_type_id else ''
            if connector_type != 'mcp':
                return
            from odoo.addons.nexora_studio.services.connector.onboarding.runtime_synchronizer import (
                ConnectorRuntimeSynchronizer
            )
            from odoo.addons.nexora_studio.services.connector.onboarding.mcp_onboarding_service import (
                McpOnboardingService
            )
            from odoo.addons.nexora_studio.services.connector.registry.capability_index import ConnectorCapabilityIndex

            runtime = self._get_global_runtime()
            if runtime is None:
                return
            onboarding = McpOnboardingService(runtime, runtime.registration_pipeline, self.env)
            synchronizer = ConnectorRuntimeSynchronizer(onboarding)
            synchronizer.sync_on_unlink(record)
        except Exception as e:
            _logger.warning(
                "nexora.connector: runtime unlink sync failed for '%s': %s",
                record.connector_id, type(e).__name__
            )

    def _get_global_runtime(self):
        """
        Retrieve the global ConnectorRuntime singleton from the bootstrap.
        Returns None if not initialized (e.g., during DB initialization).
        Safe to call from ORM hooks.
        """
        try:
            from odoo.addons.nexora_studio.services.connector.integration.bootstrap import get_connector_runtime
            return get_connector_runtime()
        except ImportError:
            pass
        except Exception:
            pass
        return None

