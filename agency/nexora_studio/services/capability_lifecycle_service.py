# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
import logging

_logger = logging.getLogger(__name__)

class CapabilityLifecycleService(models.AbstractModel):
    _name = 'nexora.capability_lifecycle_service'
    _description = 'Enterprise Capability Lifecycle Manager'

    @api.model
    def install(self, capability):
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'install_capability'):
                model.install_capability(capability)
            capability.health_status = 'healthy'
            self._emit_event(capability, 'capability.installed')
        except Exception as e:
            capability.health_status = 'failed'
            _logger.error(f"Failed to install capability {capability.capability_id}: {e}")

    @api.model
    def uninstall(self, capability):
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'uninstall_capability'):
                model.uninstall_capability(capability)
            self._emit_event(capability, 'capability.removed')
        except Exception as e:
            _logger.error(f"Failed to uninstall capability {capability.capability_id}: {e}")

    @api.model
    def enable(self, capability):
        others = self.env['nexora.capability_registry'].search([('capability_code', '=', capability.capability_code), ('id', '!=', capability.id)])
        others.write({'enabled': False})
        capability.enabled = True
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'enable_capability'):
                model.enable_capability(capability)
            self._emit_event(capability, 'capability.enabled')
            # Rebuild cache
            self.env['nexora.capability_cache_service'].rebuild_cache()
        except Exception as e:
            _logger.error(f"Error enabling {capability.capability_id}: {e}")

    @api.model
    def disable(self, capability):
        capability.enabled = False
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'disable_capability'):
                model.disable_capability(capability)
            self._emit_event(capability, 'capability.disabled')
            # Rebuild cache
            self.env['nexora.capability_cache_service'].rebuild_cache()
        except Exception as e:
            _logger.error(f"Error disabling {capability.capability_id}: {e}")

    @api.model
    def upgrade(self, capability):
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'upgrade_capability'):
                model.upgrade_capability(capability)
            self._emit_event(capability, 'capability.upgraded')
            self.env['nexora.capability_cache_service'].rebuild_cache()
        except Exception as e:
            _logger.error(f"Error upgrading {capability.capability_id}: {e}")

    @api.model
    def downgrade(self, capability):
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'downgrade_capability'):
                model.downgrade_capability(capability)
            self._emit_event(capability, 'capability.downgraded')
            self.env['nexora.capability_cache_service'].rebuild_cache()
        except Exception as e:
            _logger.error(f"Error downgrading {capability.capability_id}: {e}")

    @api.model
    def rollback_cap(self, capability):
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'rollback_capability'):
                model.rollback_capability(capability)
        except Exception as e:
            _logger.error(f"Error rolling back {capability.capability_id}: {e}")

    @api.model
    def check_health(self, capability):
        capability.last_validation = fields.Datetime.now()
        try:
            model = self.env.get(capability.implementation_model)
            if model and hasattr(model, 'health'):
                is_healthy = model.health()
                capability.health_status = 'healthy' if is_healthy else 'failed'
            else:
                capability.health_status = 'healthy'
        except Exception as e:
            capability.health_status = 'failed'
            _logger.error(f"Health check failed for {capability.capability_id}: {e}")
            
    @api.model
    def validate_capability(self, capability):
        try:
            model = self.env.get(capability.implementation_model)
            if not model:
                raise ValueError(f"Model {capability.implementation_model} not found")
            return True
        except Exception as e:
            capability.health_status = 'failed'
            capability.last_validation = fields.Datetime.now()
            self._emit_event(capability, 'capability.validation_failed')
            _logger.error(f"Validation failed for {capability.capability_id}: {e}")
            return False

    @api.model
    def _emit_event(self, capability, event_type):
        # We emit events globally, but without a specific builder session, we might just log or attach to a global system event trace if one exists.
        # Since Phase 11 wants runtime events for capabilities, we will emit them loosely.
        try:
            self.env['nexora.runtime_event'].create({
                'runtime_type': 'system',
                'event_type': event_type,
                'message': f"Capability {capability.capability_code} triggered {event_type}"
            })
        except Exception:
            pass
