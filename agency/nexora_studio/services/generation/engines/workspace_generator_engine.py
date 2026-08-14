import logging
import json
from typing import Any
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Workspace

_logger = logging.getLogger(__name__)

class WorkspaceGeneratorEngine(BaseGenerationEngine):
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing WorkspaceGeneratorEngine (Template Materialization)...")
        
        session_id = runtime.metadata.session_id
        
        
        if not hasattr(artifact, 'template') or not getattr(artifact.template, 'template_path', None):
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error="Template path missing in artifact. TemplateResolutionEngine must run first.")
            
        template_path = artifact.template.template_path
        if not runtime.workspace.check_external_exists(template_path):
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=f"Template path does not exist: {template_path}")
            
        ignore_rules = ['.git', 'node_modules', '__pycache__', '.nexora_ignore']
        def ignore_func(dir_name, files):
            return [f for f in files if any(rule in f for rule in ignore_rules)]
            
        try:
            # We use the workspace adapter to safely import external content
            runtime.workspace.import_external_directory(template_path, dest_relative_path=".", ignore_func=ignore_func)
            
            # Ensure required base directories exist
            directories_to_create = ['.nexora']
            for d in directories_to_create:
                runtime.workspace.mkdir(d)
                
            # Simulate saving artifacts to file system
            metadata_path = '.nexora/workspace_meta.json'
            import dataclasses
            from datetime import datetime

            workspace_payload = {
                "schema_version": "1.0",
                "generation_version": "20B.4",
                "generation_timestamp": datetime.utcnow().isoformat() + "Z",
                "requirements": dataclasses.asdict(artifact.requirements) if hasattr(artifact.requirements, '__dataclass_fields__') else artifact.requirements,
                "blueprint": artifact.generation_metadata.get("modular_blueprint", {}),
                "architecture": dataclasses.asdict(artifact.architecture) if hasattr(artifact.architecture, '__dataclass_fields__') else artifact.architecture,
                "theme": dataclasses.asdict(artifact.theme) if hasattr(artifact.theme, '__dataclass_fields__') else artifact.theme,
                "template": dataclasses.asdict(artifact.template) if hasattr(artifact.template, '__dataclass_fields__') else artifact.template,
                "design": artifact.design,
                "component_tree": dataclasses.asdict(artifact.component_tree) if hasattr(artifact.component_tree, '__dataclass_fields__') else artifact.component_tree,
                "assets": dataclasses.asdict(artifact.assets) if hasattr(artifact.assets, '__dataclass_fields__') else artifact.assets,
                "content": dataclasses.asdict(artifact.content) if hasattr(artifact.content, '__dataclass_fields__') else artifact.content
            }
            runtime.workspace.write_file(metadata_path, json.dumps(workspace_payload, default=str))
            
            _logger.info(f"Workspace {session_id} materialized from template: {artifact.template.template_name}")
            
        except Exception as e:
            return EngineExecutionResult(success=False, artifact=artifact, metadata={}, error=f"Template materialization failed: {str(e)}")
        
        model = Workspace(
            session_id=str(session_id),
            project_path="/sandboxed/workspace",
            is_ready=True
        )
        return EngineExecutionResult(success=True, artifact=artifact.evolve(workspace=model), metadata={"workspace_path": "sandboxed"}, error=None)
