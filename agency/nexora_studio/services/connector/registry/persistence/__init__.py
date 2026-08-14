# -*- coding: utf-8 -*-
"""
Persistence package init
"""
from .port import ConnectorPersistencePort
from .service import ConnectorPersistenceService
from .adapter import ConnectorPersistenceAdapter
from .odoo_adapter import OdooConnectorPersistenceAdapter

__all__ = [
    "ConnectorPersistencePort",
    "ConnectorPersistenceService",
    "ConnectorPersistenceAdapter",
    "OdooConnectorPersistenceAdapter",
]
