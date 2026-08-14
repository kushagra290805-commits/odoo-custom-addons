# -*- coding: utf-8 -*-
"""
Backward-compatible shim — the real Provider Manager now lives at
services/ai/provider_manager.py.  This file is retained solely to
keep the import chain `from . import ai_provider_manager` working
in services/__init__.py.  The Odoo model name 'nexora.ai_provider_manager'
is registered by the new module; this file adds nothing.
"""
