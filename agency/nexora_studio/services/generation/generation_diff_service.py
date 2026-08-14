# -*- coding: utf-8 -*-
from odoo import models
import hashlib
import os

class GenerationDiffService(models.AbstractModel):
    _name = 'nexora.generation_diff_service'
    _description = 'Incremental Generation Diff Engine'

    def calculate_workspace_hashes(self, workspace_path: str, ignore_patterns: list = None) -> dict:
        """
        Calculates SHA-256 hashes for all files in a workspace, skipping ignored patterns.
        """
        if ignore_patterns is None:
            ignore_patterns = ['.git', 'node_modules', 'dist', 'build', '__pycache__']
            
        hashes = {}
        for root, dirs, files in os.walk(workspace_path):
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in ignore_patterns)]
            for file in files:
                if any(pattern in file for pattern in ignore_patterns):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, workspace_path)
                hashes[rel_path] = self._hash_file(file_path)
        return hashes

    def compute_diff(self, old_hashes: dict, new_hashes: dict) -> dict:
        """
        Computes the delta between two hash maps.
        Returns dict with 'added', 'modified', 'deleted', 'unchanged' keys.
        """
        old_keys = set(old_hashes.keys())
        new_keys = set(new_hashes.keys())
        
        added = list(new_keys - old_keys)
        deleted = list(old_keys - new_keys)
        
        common = old_keys.intersection(new_keys)
        modified = [k for k in common if old_hashes[k] != new_hashes[k]]
        unchanged = [k for k in common if old_hashes[k] == new_hashes[k]]
        
        return {
            'added': added,
            'modified': modified,
            'deleted': deleted,
            'unchanged': unchanged
        }

    def _hash_file(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
