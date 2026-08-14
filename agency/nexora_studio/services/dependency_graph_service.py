# -*- coding: utf-8 -*-
from odoo import models, api

class DependencyGraphService(models.AbstractModel):
    _name = 'nexora.dependency_graph_service'
    _description = 'Enterprise Dependency Graph Service V2'

    @api.model
    def build_graph(self, enabled_plugins):
        graph = {}
        for p in enabled_plugins:
            deps = [d.strip() for d in p.dependencies.split(',')] if p.dependencies else []
            graph[p.capability_code] = [d for d in deps if d]
        return graph

    @api.model
    def detect_cycles(self, graph):
        visited = set()
        temp = set()
        
        def visit(node):
            if node in temp:
                raise ValueError(f"Dependency cycle detected involving: {node}")
            if node not in visited:
                temp.add(node)
                for dep in graph.get(node, []):
                    visit(dep)
                temp.remove(node)
                visited.add(node)
                
        for node in graph:
            visit(node)
        return False

    @api.model
    def detect_missing_dependencies(self, graph, enabled_codes):
        for node, deps in graph.items():
            for dep in deps:
                if dep not in enabled_codes:
                    raise ValueError(f"Missing dependency: {node} requires {dep}")

    @api.model
    def validate_graph(self, enabled_plugins):
        graph = self.build_graph(enabled_plugins)
        enabled_codes = {p.capability_code for p in enabled_plugins}
        
        self.detect_missing_dependencies(graph, enabled_codes)
        self.detect_cycles(graph)
        
        # Emit event
        self.env['nexora.runtime_event'].create({
            'runtime_type': 'system',
            'event_type': 'dependency.graph.updated',
            'message': f"Validated dependency graph for {len(enabled_plugins)} plugins."
        })
        return True

    @api.model
    def validate_dependencies_for_enable(self, plugin):
        # Ensure all required dependencies are already enabled
        deps = [d.strip() for d in plugin.dependencies.split(',')] if plugin.dependencies else []
        registry = self.env['nexora.capability_registry']
        for dep in deps:
            if not dep: continue
            if not registry.search_count([('capability_code', '=', dep), ('enabled', '=', True)]):
                raise ValueError(f"Cannot enable {plugin.capability_code}: missing required dependency {dep}")

    @api.model
    def startup_order(self, enabled_plugins):
        graph = self.build_graph(enabled_plugins)
        
        sorted_codes = []
        visited = set()
        temp = set()
        
        def visit(node):
            if node in temp:
                raise ValueError(f"Dependency cycle detected involving: {node}")
            if node not in visited:
                temp.add(node)
                for dep in graph.get(node, []):
                    if dep in graph:
                        visit(dep)
                temp.remove(node)
                visited.add(node)
                sorted_codes.append(node)
                
        for node in graph:
            if node not in visited:
                visit(node)
                
        # Return plugins in sorted order
        code_to_plugin = {p.capability_code: p for p in enabled_plugins}
        return [code_to_plugin[code] for code in sorted_codes if code in code_to_plugin]

    @api.model
    def shutdown_order(self, enabled_plugins):
        # Reverse of startup order
        return list(reversed(self.startup_order(enabled_plugins)))
