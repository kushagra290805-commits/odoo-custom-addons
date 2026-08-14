# -*- coding: utf-8 -*-
import unittest
import threading
import odoo
from odoo.tests.common import TransactionCase

has_db = bool(odoo.tools.config.get('db_name') or hasattr(threading.current_thread(), 'dbname'))

@unittest.skipIf(not has_db, "Requires running Odoo database connection")
class TestDIPORM(TransactionCase):
    test_tags = {'standard', 'at_install'}
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SourceRegistry = cls.env['nexora.source_registry']
        cls.ComponentIndex = cls.env['nexora.component_index']
        
        # Register mock provider
        cls.mock_provider = cls.SourceRegistry.create({
            'name': 'Test Provider',
            'technical_name': 'test_adapter',
            'adapter_class': 'agency.nexora_studio.services.source_framework.adapters.internal_adapter.InternalAdapter',
            'capabilities': 'SEARCH,PREVIEW',
            'config_json': '{}'
        })
        
    def test_provider_registration(self):
        self.assertEqual(self.mock_provider.technical_name, 'test_adapter')
        
    def test_component_persistence(self):
        index = self.ComponentIndex.create({
            'component_id': 'test_comp_001',
            'provider_id': self.mock_provider.id,
            'name': 'Test Button',
            'interaction_type': 'installed'
        })
        self.assertEqual(index.interaction_type, 'installed')
        
    def test_semantic_extension(self):
        index = self.ComponentIndex.create({
            'component_id': 'test_comp_002',
            'provider_id': self.mock_provider.id,
            'name': 'Semantic Card',
            'interaction_type': 'ai_selected',
            'semantic_tags': 'card,ui,modern'
        })
        self.assertEqual(index.semantic_tags, 'card,ui,modern')
