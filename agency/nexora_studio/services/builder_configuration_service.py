# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
import uuid

_logger = logging.getLogger(__name__)

class BuilderConfigurationService(models.AbstractModel):
    _name = 'nexora.builder_configuration_service'
    _description = 'Builder Configuration Service Interface'

    @api.model
    def create_configuration(self, vals):
        """
        Creates a new Builder Configuration.
        """
        return self.env['nexora.builder_configuration'].create(vals)

    @api.model
    def clone_configuration(self, config_id):
        """
        Clones an existing configuration, sets it to draft, and increments the version semantically.
        """
        config = self.env['nexora.builder_configuration'].browse(config_id)
        if not config.exists():
            raise ValidationError(_('Configuration does not exist.'))
        if config.status != 'locked':
            raise ValidationError(_('Only locked configurations can be cloned to create a new version.'))
            
        # Parse semantic version and increment patch version as a default (e.g. 1.0.0 -> 1.0.1)
        current_version = config.semantic_version
        parts = current_version.split('.')
        
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            major, minor, patch = map(int, parts)
            new_version = f"{major}.{minor}.{patch + 1}"
        else:
            # Fallback if it isn't strictly x.y.z
            new_version = current_version + " (Clone)"

        new_config = config.copy(default={
            'name': f"{config.name} (v{new_version})",
            'configuration_uuid': str(uuid.uuid4()),
            'semantic_version': new_version,
            'status': 'draft',
        })
        
        _logger.info(f"Cloned Configuration {config.name} to {new_config.name}")
        return new_config

    @api.model
    def lock_configuration(self, config_id):
        """
        Locks the configuration.
        """
        config = self.env['nexora.builder_configuration'].browse(config_id)
        if not config.exists():
            raise ValidationError(_('Configuration does not exist.'))
        
        self.validate_configuration(config_id)
            
        if config.status != 'draft':
            raise ValidationError(_('Only draft configurations can be locked.'))
            
        config.status = 'locked'
        _logger.info(f"Configuration {config.name} locked.")
        return True

    @api.model
    def archive_configuration(self, config_id):
        """
        Archives the configuration.
        """
        config = self.env['nexora.builder_configuration'].browse(config_id)
        if not config.exists():
            raise ValidationError(_('Configuration does not exist.'))
            
        if config.status not in ('draft', 'locked'):
            raise ValidationError(_('Configuration is already archived.'))
            
        config.status = 'archived'
        _logger.info(f"Configuration {config.name} archived.")
        return True

    @api.model
    def validate_configuration(self, config_id):
        """
        Ensures metadata integrity before locking.
        """
        config = self.env['nexora.builder_configuration'].browse(config_id)
        if not config.name or not config.semantic_version or not config.environment:
            raise ValidationError(_('Configuration is missing required metadata (Name, Version, Environment).'))
        
        # Ensure semantic version is properly formatted X.Y.Z
        parts = config.semantic_version.split('.')
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValidationError(_("Semantic version must follow X.Y.Z format (e.g., 1.0.0)."))
            
        return True
