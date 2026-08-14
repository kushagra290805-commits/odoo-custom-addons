import logging
from typing import Dict
from datetime import datetime

from .base_provider import (
    UnifiedCostQuotaService,
    ProviderCategory,
    ProviderServiceContainer
)

_logger = logging.getLogger(__name__)

class OdooUnifiedCostQuotaService(UnifiedCostQuotaService):
    """
    Unified 5-dimension cost accounting service.
    Tracks expenditure across AI tokens, Bandwidth, CPU, Storage, and Custom units.
    """

    def __init__(self, container: ProviderServiceContainer):
        self._container = container
        # Note: In a real Odoo environment, quotas would be fetched from ir.config_parameter
        # or a specific billing model based on the user/workspace.
        self._category_quotas: Dict[ProviderCategory, float] = {
            ProviderCategory.AI: 50.0,         # $50 limit
            ProviderCategory.ASSET: 10.0,      # $10 limit (or bandwidth mapped to USD)
            ProviderCategory.COMPONENT: 20.0,
            ProviderCategory.DESIGN: 30.0,
            ProviderCategory.MCP: 5.0,
            ProviderCategory.PREVIEW: 5.0,
            ProviderCategory.STORAGE: 15.0,
            ProviderCategory.CUSTOM: 10.0
        }

    def check_quota(self, provider_id: str, category: ProviderCategory, cost_units: float) -> bool:
        """
        Check if the requested execution fits within the budget/quota.
        """
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                # Aggregate spent for this category (ideally filtered by workspace/user)
                # For simplicity, we just look at the global total or a placeholder
                # A full implementation would query `nexora.provider.cost_ledger`
                # grouped by category (which requires joining with registry)
                pass
        except ImportError:
            pass

        # In absence of full DB tracking, we assume True (within quota)
        # unless cost_units exceeds the absolute category limit in a single request.
        limit = self._category_quotas.get(category, 0.0)
        
        if cost_units > limit:
            _logger.warning(
                f"Quota exceeded for {provider_id} in category {category.value}. "
                f"Requested: {cost_units}, Limit: {limit}"
            )
            return False
            
        return True

    def record_expenditure(self, session_uuid: str, provider_id: str, usd_cost: float, units: float) -> None:
        """
        Records the cost into the nexora.provider.cost_ledger model.
        """
        if usd_cost <= 0 and units <= 0:
            return
            
        try:
            from odoo import http
            if http.request and hasattr(http.request, 'env'):
                env = http.request.env
                env['nexora.provider.cost_ledger'].sudo().create({
                    'session_uuid': session_uuid,
                    'provider_id': provider_id,
                    'usd_cost': usd_cost,
                    'units_consumed': units,
                    'unit_type': 'tokens', # Simplified. Should be mapped to category.
                    'timestamp': datetime.utcnow()
                })
        except Exception as e:
            _logger.error(f"Failed to record expenditure for {provider_id}: {e}")
