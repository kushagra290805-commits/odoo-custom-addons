# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ToolRegistry(models.AbstractModel):
    _name = 'nexora.tool_registry'
    _description = 'Enterprise Tool Registry Wrapper'

    @api.model
    def get_registered_tools(self):
        """Discovers tools via Capability Cache Service"""
        cache_service = self.env['nexora.capability_cache_service']
        capabilities = cache_service.get_sorted_capabilities()
        tools = []
        for cap in capabilities:
            if cap.category != 'tool':
                continue
            try:
                tools.append({
                    'tool_id': cap.capability_id,
                    'tool_name': cap.display_name,
                    'tool_type': cap.capability_code,
                    'priority': cap.priority,
                    'instance': self.env[cap.implementation_model]
                })
            except Exception as e:
                _logger.warning(f"Failed to load tool {cap.capability_id}: {e}")
        return tools

    @api.model
    def get_tool(self, tool_id=None, tool_type=None):
        """Resolves a tool by ID or Type using the Capability Cache"""
        cache_service = self.env['nexora.capability_cache_service']
        capabilities = cache_service.get_sorted_capabilities()
        
        cap = None
        for c in capabilities:
            if c.category == 'tool':
                if tool_id and (c.capability_id == tool_id or c.capability_code == tool_id):
                    cap = c
                    break
                if tool_type and c.capability_code == tool_type:
                    cap = c
                    break
                    
        if not cap:
            return None
            
        try:
            res = self.env[cap.implementation_model]
            return res
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Failed to load tool model %s: %s', cap.implementation_model, e)
            return None

    @api.model
    def resolve_tool(self, tool_id=None, tool_type=None):
        """Resolves a tool and returns (provider_instance, descriptor)"""
        cache_service = self.env['nexora.capability_cache_service']
        capabilities = cache_service.get_sorted_capabilities()
        
        cap = None
        for c in capabilities:
            if c.category == 'tool':
                if tool_id and (c.capability_id == tool_id or c.capability_code == tool_id):
                    cap = c
                    break
                if tool_type and c.capability_code == tool_type:
                    cap = c
                    break
                    
        if not cap:
            return None
            
        try:
            return (self.env[cap.implementation_model], cap)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Failed to load tool model %s: %s', cap.implementation_model, e)
            return None

    @api.model
    def execute_tool(self, tool_id, context, **kwargs):
        tool = self.get_tool(tool_id=tool_id)
        if tool is None:
            raise ValueError(f"Tool {tool_id} not registered or not enabled.")
        tool.validate(context, **kwargs)
        return tool.execute(context, **kwargs)
