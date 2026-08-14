# -*- coding: utf-8 -*-
from odoo import models, api

class MetadataVersionService(models.AbstractModel):
    _name = 'nexora.metadata_version_service'
    _description = 'Enterprise Metadata Version Service'

    SUPPORTED_VERSIONS = ['1.0']

    @api.model
    def validate_metadata(self, meta):
        """Validate that the metadata version is supported."""
        version = meta.get('metadata_version')
        if version not in self.SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported metadata version: {version}. "
                f"Supported: {self.SUPPORTED_VERSIONS}"
            )
        return True

    @api.model
    def upgrade_metadata(self, meta, target_version):
        """
        Upgrade metadata to the target version.
        Currently only version 1.0 is supported; returns metadata unchanged.
        Future versions will implement migration transforms here.
        """
        current = meta.get('metadata_version', '1.0')
        if current == target_version:
            return meta
        # When 2.0 is introduced, add migration logic here
        return meta

    @api.model
    def downgrade_metadata(self, meta, target_version):
        """
        Downgrade metadata to the target version.
        Currently only version 1.0 is supported; returns metadata unchanged.
        Future versions will implement reverse migration here.
        """
        current = meta.get('metadata_version', '1.0')
        if current == target_version:
            return meta
        return meta

    @api.model
    def migrate_metadata(self, meta):
        """Auto-migrate legacy plugins to the current version."""
        if not meta.get('metadata_version'):
            meta['metadata_version'] = '1.0'
        self.validate_metadata(meta)
        return meta
