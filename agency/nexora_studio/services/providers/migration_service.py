import logging
from typing import List
from datetime import datetime

from .base_provider import (
    ProviderMigrationService,
    MigrationRecord,
    MigrationStatus,
    ProviderServiceContainer,
    LockService,
    ProviderStateMachine,
    ProviderRuntimeState,
    ProviderCompatibilityService,
    CapabilityCache,
    ProviderRegistry,
    ProviderFactory,
    ProviderEventBus,
    ProviderEvent,
    ProviderEventChannel,
    ProviderConfiguration,
    ProviderAuthentication,
    ProviderLockTimeoutError
)

_logger = logging.getLogger(__name__)

class OdooProviderMigrationService(ProviderMigrationService):
    """
    Coordinates Provider upgrades and rollbacks ensuring transactional safety, 
    traffic isolation, and state machine consistency.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container

    @property
    def _lock_service(self) -> LockService:
        return self._container.resolve(LockService)

    @property
    def _state_machine(self) -> ProviderStateMachine:
        return self._container.resolve(ProviderStateMachine)

    @property
    def _compat_service(self) -> ProviderCompatibilityService:
        return self._container.resolve(ProviderCompatibilityService)

    @property
    def _cap_cache(self) -> CapabilityCache:
        return self._container.resolve(CapabilityCache)
        
    @property
    def _registry(self) -> ProviderRegistry:
        return self._container.resolve(ProviderRegistry)
        
    @property
    def _factory(self) -> ProviderFactory:
        return self._container.resolve(ProviderFactory)
        
    @property
    def _event_bus(self) -> ProviderEventBus:
        return self._container.resolve(ProviderEventBus)

    def plan_upgrade(self, provider_id: str, to_version: str) -> List[MigrationRecord]:
        """
        Inspects the upgrade path and returns a plan.
        """
        metadata = self._registry.get_metadata(provider_id)
        if not metadata:
            raise ValueError(f"Provider {provider_id} not found.")
            
        return [
            MigrationRecord(
                provider_id=provider_id,
                from_version=metadata.provider_version,
                to_version=to_version,
                status=MigrationStatus.PENDING,
                started_at=datetime.utcnow()
            )
        ]

    def execute_upgrade(self, provider_id: str, to_version: str) -> MigrationRecord:
        """
        Executes a transactional upgrade.
        """
        metadata = self._registry.get_metadata(provider_id)
        if not metadata:
            raise ValueError(f"Provider {provider_id} not found.")
            
        from_version = metadata.provider_version
        
        record = MigrationRecord(
            provider_id=provider_id,
            from_version=from_version,
            to_version=to_version,
            status=MigrationStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        provider = self._factory.create_provider(
            provider_id, ProviderConfiguration(), ProviderAuthentication(auth_type="migration", credentials_vault_key="")
        )
        
        if not provider.validate_upgrade(from_version, to_version):
            record.status = MigrationStatus.FAILED
            record.error_detail = "validate_upgrade() returned False"
            record.completed_at = datetime.utcnow()
            self._log_migration(record)
            return record

        lock_key = f"nexora:provider:{provider_id}:migration_lock"
        lock_res = self._lock_service.acquire(lock_key, holder_id="migration_svc", timeout_ms=10000, ttl_ms=60000)
        
        if not lock_res.acquired:
            raise ProviderLockTimeoutError(f"Could not acquire migration lock for {provider_id}", provider_id=provider_id)
            
        try:
            # Transition to DISABLED for traffic isolation
            original_state = self._state_machine.get_state(provider_id)
            self._state_machine.transition(provider_id, ProviderRuntimeState.DISABLED, reason="Migration in progress")
            
            try:
                provider.before_upgrade(from_version, to_version)
                provider.migrate(from_version, to_version)
                
                # Re-validate compatibility
                provider_class = self._registry.get_provider_class(provider_id)
                compat_report = self._compat_service.validate(provider_class)
                if not compat_report.is_compatible:
                    raise ValueError(f"Post-migration compatibility check failed: {compat_report.failures}")
                    
                # Invalidate capability cache
                self._cap_cache.invalidate(provider_id)
                
                # Transition to CONFIGURED -> AUTHENTICATED -> READY
                self._state_machine.transition(provider_id, ProviderRuntimeState.CONFIGURED, reason="Migration successful")
                provider.after_upgrade(from_version, to_version)
                
                record.status = MigrationStatus.COMPLETED
                
            except Exception as e:
                _logger.error(f"Migration failed for {provider_id}: {e}")
                record.error_detail = str(e)
                
                # Perform rollback
                self.rollback_upgrade(provider_id, from_version)
                record.status = MigrationStatus.ROLLED_BACK
                
                # Restore original state
                if original_state != ProviderRuntimeState.DISABLED:
                    self._state_machine.transition(provider_id, original_state, reason="Migration rolled back")
                    
        finally:
            self._lock_service.release(lock_key, holder_id="migration_svc")
            
        record.completed_at = datetime.utcnow()
        self._log_migration(record)
        return record

    def rollback_upgrade(self, provider_id: str, to_version: str) -> MigrationRecord:
        """
        Rolls back a failed migration.
        """
        metadata = self._registry.get_metadata(provider_id)
        if not metadata:
            raise ValueError(f"Provider {provider_id} not found.")
            
        record = MigrationRecord(
            provider_id=provider_id,
            from_version=metadata.provider_version,
            to_version=to_version,
            status=MigrationStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        provider = self._factory.create_provider(
            provider_id, ProviderConfiguration(), ProviderAuthentication(auth_type="migration", credentials_vault_key="")
        )
        
        try:
            provider.rollback(to_version)
            record.status = MigrationStatus.ROLLED_BACK
        except Exception as e:
            record.status = MigrationStatus.FAILED
            record.error_detail = f"Rollback failed: {e}"
            
        record.completed_at = datetime.utcnow()
        self._log_migration(record)
        return record

    def get_migration_history(self, provider_id: str) -> List[MigrationRecord]:
        # Return history from database
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                records = env['nexora.provider.migration_log'].sudo().search([('provider_id', '=', provider_id)])
                history = []
                for rec in records:
                    history.append(MigrationRecord(
                        provider_id=rec.provider_id,
                        from_version=rec.from_version,
                        to_version=rec.to_version,
                        status=MigrationStatus(rec.status),
                        started_at=rec.started_at,
                        completed_at=rec.completed_at,
                        error_detail=rec.error_detail
                    ))
                return history
        except Exception as e:
            _logger.error(f"Failed to retrieve migration history: {e}")
        return []

    def _log_migration(self, record: MigrationRecord) -> None:
        """
        Persists the migration record and emits an AUDIT event.
        """
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                env['nexora.provider.migration_log'].sudo().create({
                    'provider_id': record.provider_id,
                    'from_version': record.from_version,
                    'to_version': record.to_version,
                    'status': record.status.value,
                    'started_at': record.started_at,
                    'completed_at': record.completed_at,
                    'error_detail': record.error_detail
                })
        except Exception as e:
            _logger.error(f"Failed to log migration: {e}")
            
        self._event_bus.publish(
            ProviderEvent(
                event_id=f"migr_{record.provider_id}_{record.started_at.timestamp()}",
                timestamp=datetime.utcnow(),
                provider_id=record.provider_id,
                event_type="PROVIDER_MIGRATION",
                channel=ProviderEventChannel.AUDIT,
                session_uuid=None,
                duration_ms=0.0,
                payload=record.__dict__
            )
        )
