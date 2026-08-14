# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)

class RuntimeService(models.AbstractModel):
    _name = 'nexora.runtime_service'
    _description = 'Runtime Service Registry and Lifecycle Manager'

    @api.model
    def synchronize_runtime_capabilities(self):
        """
        Discovers all RuntimePlugin implementations, validates their manifests,
        and synchronizes them to the nexora.runtime_capability database registry.
        """
        plugin_base = self.env.registry['nexora.runtime_plugin']
        capability_model = self.env['nexora.runtime_capability']
        
        # 1. Discover all plugins and their manifests
        discovered_manifests = {}
        for model_name, model_cls in self.env.registry.models.items():
            if model_name != 'nexora.runtime_plugin' and issubclass(model_cls, plugin_base):
                service = self.env.get(model_name)
                if service is None:
                    continue
                    
                # Ensure plugin_manifest is overridden
                base_method = getattr(self.env['nexora.runtime_plugin'], 'plugin_manifest')
                plugin_method = getattr(service, 'plugin_manifest')
                if getattr(plugin_method, '__code__', None) == getattr(base_method, '__code__', None):
                    raise ValidationError(_(f"Plugin {model_name} must implement plugin_manifest()"))
                    
                manifest = service.plugin_manifest()
                
                # Basic validation
                r_type = manifest.get('runtime_type')
                if not r_type:
                    raise ValidationError(_(f"Plugin {model_name} manifest is missing 'runtime_type'."))
                if r_type in discovered_manifests:
                    raise ValidationError(_(f"Duplicate runtime_type '{r_type}' detected in {model_name}."))
                
                deps = manifest.get('dependencies', [])
                if not isinstance(deps, list):
                    raise ValidationError(_(f"Plugin {model_name} must define 'dependencies' as a list."))
                    
                priority = manifest.get('priority', 100)
                if not isinstance(priority, int):
                    raise ValidationError(_(f"Plugin {model_name} must define 'priority' as an integer."))
                    
                # Validate lifecycle interface (must be overridden)
                required_methods = ['start_runtime_instance', 'stop_runtime_instance', 
                                    'restart_runtime_instance', 'refresh_runtime', 'check_health']
                for method in required_methods:
                    if not hasattr(service, method):
                        raise ValidationError(_(f"Plugin {model_name} is missing required lifecycle method: {method}"))
                    base_m = getattr(self.env['nexora.runtime_plugin'], method)
                    plugin_m = getattr(service, method)
                    if getattr(plugin_m, '__code__', None) == getattr(base_m, '__code__', None):
                        raise ValidationError(_(f"Plugin {model_name} must override lifecycle method: {method}"))
                        
                manifest['plugin_service'] = model_name
                discovered_manifests[r_type] = manifest
                
        # 2. Dependency Resolution Validation
        for r_type, manifest in discovered_manifests.items():
            for dep in manifest['dependencies']:
                if dep not in discovered_manifests:
                    raise ValidationError(_(f"Plugin {manifest['plugin_service']} depends on unknown runtime_type '{dep}'."))
                    
        # 3. DB Sync
        existing_caps = capability_model.search([])
        existing_by_type = {c.runtime_type: c for c in existing_caps}
        
        # A. Create / Update
        new_records_by_type = {}
        for r_type, manifest in discovered_manifests.items():
            vals = {
                'name': manifest.get('name', r_type.capitalize()),
                'provider': manifest.get('provider', 'nexora'),
                'version': manifest.get('version', '1.0.0'),
                'plugin_service': manifest['plugin_service'],
                'startup_priority': manifest.get('priority', 100),
                'supports_health_checks': manifest.get('supports_health_checks', False),
                'restart_policy': manifest.get('restart_policy', 'always'),
                'description': manifest.get('description', ''),
                'metadata_json': json.dumps(manifest),
                'active': True
            }
            if r_type in existing_by_type:
                # Update existing (avoid overriding user fields like 'enabled')
                existing_by_type[r_type].write(vals)
                new_records_by_type[r_type] = existing_by_type[r_type]
            else:
                vals['runtime_type'] = r_type
                vals['enabled'] = True
                new_records_by_type[r_type] = capability_model.create(vals)
                
        # B. Archive removed plugins
        for r_type, cap in existing_by_type.items():
            if r_type not in discovered_manifests:
                cap.write({'active': False, 'enabled': False})
                
        # C. Link M2M Dependencies
        for r_type, manifest in discovered_manifests.items():
            cap = new_records_by_type[r_type]
            dep_records = [new_records_by_type[dep].id for dep in manifest['dependencies']]
            cap.write({'dependency_ids': [(6, 0, dep_records)]})
            
            # Run initialization recovery hook if supported
            service = self.env.get(manifest['plugin_service'])
            if service is not None and hasattr(service, 'initialize_service'):
                if getattr(service.__class__, '_init_done', False):
                    continue
                try:
                    with self.env.cr.savepoint():
                        service.initialize_service()
                except Exception as e:
                    _logger.warning(f"Error initializing service {manifest['plugin_service']}: {e}")
            
        return True

    @api.model
    def build_dependency_graph(self):
        """
        Builds a deterministic dependency graph using topological sorting from the database.
        Returns an ordered list of runtime_types.
        """
        capabilities = self.env['nexora.runtime_capability'].search([('enabled', '=', True)])
        
        # graph[u] = list of nodes that depend on u (u -> v)
        graph = {cap.runtime_type: [] for cap in capabilities}
        in_degree = {cap.runtime_type: 0 for cap in capabilities}
        cap_by_type = {cap.runtime_type: cap for cap in capabilities}
        
        for cap in capabilities:
            for dep in cap.dependency_ids:
                if dep.runtime_type not in graph:
                    raise ValidationError(_(f"Enabled capability '{cap.runtime_type}' depends on disabled/missing capability '{dep.runtime_type}'."))
                graph[dep.runtime_type].append(cap.runtime_type)
                in_degree[cap.runtime_type] += 1
                
        # Kahn's algorithm with priority-based deterministic ordering
        zero_in_degree = [node for node in graph.keys() if in_degree[node] == 0]
        
        order = []
        while zero_in_degree:
            # Sort by priority, then alphabetically for determinism
            zero_in_degree.sort(key=lambda x: (cap_by_type[x].startup_priority, x))
            
            u = zero_in_degree.pop(0)
            order.append(u)
            
            for v in graph[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    zero_in_degree.append(v)
                    
        if len(order) != len(graph):
            remaining = [node for node in graph.keys() if in_degree[node] > 0]
            raise ValidationError(_(f"Circular dependency detected among runtimes: {', '.join(remaining)}"))
            
        return order

    @api.model
    def discover_runtimes(self, session):
        """
        Ensures that necessary runtime records exist for a given session based on enabled capabilities.
        Returns the list of required runtimes.
        """
        # First ensure sync is run so capabilities are up to date
        self.synchronize_runtime_capabilities()
        
        runtime_model = self.env['nexora.runtime']
        order = self.build_dependency_graph()
        
        for r_type in order:
            runtime = runtime_model.search([('builder_session_id', '=', session.id), ('runtime_type', '=', r_type)], limit=1)
            if not runtime:
                runtime_model.create({
                    'name': f"{session.name} - {r_type.capitalize()}",
                    'builder_session_id': session.id,
                    'runtime_type': r_type,
                    'status': 'stopped',
                    'health': 'unknown'
                })
        
        return runtime_model.search([('builder_session_id', '=', session.id)])

    @api.model
    def _dispatch_runtime(self, runtime, action):
        """
        Generic dispatcher for runtime lifecycle hooks via capability registry.
        """
        cap = self.env['nexora.runtime_capability'].search([('runtime_type', '=', runtime.runtime_type), ('enabled', '=', True)], limit=1)
        if not cap:
            _logger.error(f"No enabled capability registered for runtime type: {runtime.runtime_type}")
            raise ValidationError(_(f"No enabled capability registered for runtime type: {runtime.runtime_type}"))
            
        service_name = cap.plugin_service
        service = self.env.get(service_name)
        if service is None:
            raise ValidationError(_(f"Service {service_name} for capability {runtime.runtime_type} is not available in registry."))
            
        return getattr(service, action)(runtime)

    @api.model
    def start_runtime(self, session):
        """
        Starts all discovered runtimes for the session in dependency order.
        """
        runtimes = self.discover_runtimes(session)
        order = self.build_dependency_graph()
        
        # Sort runtimes by the topological order
        sorted_runtimes = sorted(runtimes, key=lambda r: order.index(r.runtime_type) if r.runtime_type in order else 999)
        
        for runtime in sorted_runtimes:
            runtime.status = 'starting'
            try:
                self._dispatch_runtime(runtime, 'start_runtime_instance')
                runtime.status = 'running'
                runtime.health = 'healthy'
                runtime.started_at = fields.Datetime.now()
                runtime.last_activity = fields.Datetime.now()
            except Exception as e:
                runtime.status = 'error'
                runtime.health = 'critical'
                _logger.error(f"Failed to start runtime {runtime.runtime_type}: {e}")
                raise ValidationError(_(f"Failed to start runtime {runtime.runtime_type}: {e}"))

    @api.model
    def stop_runtime(self, session):
        """
        Stops all runtimes for the session in reverse dependency order.
        """
        runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
        order = self.build_dependency_graph()
        
        # Stop in reverse dependency order
        sorted_runtimes = sorted(runtimes, key=lambda r: order.index(r.runtime_type) if r.runtime_type in order else -1, reverse=True)
        
        for runtime in sorted_runtimes:
            if runtime.status in ['stopped', 'error']:
                continue
            runtime.status = 'stopping'
            try:
                self._dispatch_runtime(runtime, 'stop_runtime_instance')
            except Exception as e:
                _logger.error(f"Error stopping runtime {runtime.runtime_type}: {e}")
            
            runtime.status = 'stopped'
            runtime.stopped_at = fields.Datetime.now()
            runtime.last_activity = fields.Datetime.now()

    @api.model
    def restart_runtime(self, session):
        self.stop_runtime(session)
        self.start_runtime(session)

    @api.model
    def refresh_runtime(self, session):
        """Refreshes status of all runtimes."""
        runtimes = self.env['nexora.runtime'].search([('builder_session_id', '=', session.id)])
        for runtime in runtimes:
            try:
                self._dispatch_runtime(runtime, 'refresh_runtime')
            except Exception as e:
                _logger.warning(f"Could not refresh runtime {runtime.runtime_type}: {e}")

    @api.model
    def get_runtime(self, session, runtime_type):
        return self.env['nexora.runtime'].search([
            ('builder_session_id', '=', session.id),
            ('runtime_type', '=', runtime_type)
        ], limit=1)

