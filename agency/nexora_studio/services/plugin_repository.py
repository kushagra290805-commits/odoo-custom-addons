# -*- coding: utf-8 -*-
import os
import codecs

class AbstractPluginRepository:
    def discover_manifests(self):
        """Returns a list of manifest strings"""
        raise NotImplementedError

class LocalPluginRepository(AbstractPluginRepository):
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def discover_manifests(self):
        manifests = []
        if not os.path.exists(self.base_dir):
            return manifests
            
        for root, dirs, files in os.walk(self.base_dir):
            if 'plugin.json' in files:
                manifest_path = os.path.join(root, 'plugin.json')
                with codecs.open(manifest_path, 'r', encoding='utf-8-sig') as f:
                    manifests.append(f.read())
        return manifests
