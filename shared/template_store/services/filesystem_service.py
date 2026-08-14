# -*- coding: utf-8 -*-
import os
import shutil
import logging
from pathlib import Path
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class FilesystemService(models.AbstractModel):
    _name = 'nexora.filesystem_service'
    _description = 'Secure Filesystem Abstraction'

    @api.model
    def create_directory(self, path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            return True
        return False

    @api.model
    def copy_tree(self, src, dst, ignore_patterns=None):
        if not os.path.exists(src):
            raise UserError(_(f"Source directory {src} does not exist."))
        ignore_func = shutil.ignore_patterns(*ignore_patterns) if ignore_patterns else None
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore_func)
        return True
        
    @api.model
    def write_file(self, path, content, is_binary=False):
        mode = 'wb' if is_binary else 'w'
        encoding = None if is_binary else 'utf-8'
        with open(path, mode, encoding=encoding) as f:
            f.write(content)
            
    @api.model
    def read_file(self, path, is_binary=False):
        mode = 'rb' if is_binary else 'r'
        encoding = None if is_binary else 'utf-8'
        with open(path, mode, encoding=encoding) as f:
            return f.read()

    @api.model
    def remove_path(self, path):
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
            
    @api.model
    def file_exists(self, path):
        return os.path.exists(path)
        
    @api.model
    def walk(self, path):
        return os.walk(path)
