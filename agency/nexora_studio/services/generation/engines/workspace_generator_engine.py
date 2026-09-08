import logging
import json
from typing import Any, Dict, List
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, Workspace

_logger = logging.getLogger(__name__)

# Phase 47.9 (U8): default file-ownership contract, mirrored from
# DesignOrchestrationEngine. CodeGenerationEngine owns page modules and the
# application entry; the rendering provider owns every other scaffold file.
_DEFAULT_CODEGEN_OWNED_PATHS = ("src/App.jsx",)
_DEFAULT_CODEGEN_OWNED_PREFIXES = ("src/pages/",)


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

        materialized_provider_files = 0
        dependency_gaps: List[str] = []
        try:
            # We use the workspace adapter to safely import external content
            runtime.workspace.import_external_directory(template_path, dest_relative_path=".", ignore_func=ignore_func)

            # Phase 47.9 (U8): materialize rendering-provider output into the
            # managed workspace through the existing WorkspaceAdapter. The
            # provider owns its scaffold files; CodeGenerationEngine-owned
            # paths are never touched here so each file has exactly one owner.
            materialized_provider_files, dependency_gaps = self._materialize_provider_output(artifact, runtime)

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
        
        workspace_path = str(runtime.workspace.root)
        model = Workspace(
            session_id=str(session_id),
            project_path=workspace_path,
            is_ready=True
        )
        metadata = {
            "workspace_path": workspace_path,
            "provider_files_materialized": materialized_provider_files,
        }
        if dependency_gaps:
            metadata["dependency_contract_gaps"] = dependency_gaps
        return EngineExecutionResult(success=True, artifact=artifact.evolve(workspace=model), metadata=metadata, error=None)

    # ------------------------------------------------------------------
    # Phase 47.9 (U8): provider output materialization
    # ------------------------------------------------------------------

    def _materialize_provider_output(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime'):
        """Write provider-owned scaffold files into the managed workspace and
        aggregate dependencies deterministically.

        Merge order (single aggregation path, no second resolver):
          1. existing template dependencies (template package.json);
          2. provider dependencies (provider package.json — precedence);
          3. selected ComponentPackage dependencies (artifact.component_tree)
             — kept when already versioned, recorded as a contract gap when
             no version is defined anywhere.

        Returns (files_written, dependency_gaps).
        """
        design = artifact.design or {}
        project_structure = design.get("project_structure") or {}
        if not isinstance(project_structure, dict) or not project_structure:
            return 0, []

        ownership = design.get("file_ownership") or {}
        codegen_owned = tuple(ownership.get("code_generation_owned") or []) or None
        owned_paths = _DEFAULT_CODEGEN_OWNED_PATHS
        owned_prefixes = _DEFAULT_CODEGEN_OWNED_PREFIXES

        def is_codegen_owned(path: str) -> bool:
            if codegen_owned:
                for entry in codegen_owned:
                    if entry.endswith('/*'):
                        if path.startswith(entry[:-1]):
                            return True
                    elif path == entry:
                        return True
                return False
            return path in owned_paths or path.startswith(owned_prefixes)

        # 1. Read the template dependency manifest before provider files land.
        template_pkg = {}
        try:
            template_pkg = json.loads(runtime.workspace.read_file('package.json'))
        except Exception:
            template_pkg = {}

        # 2. Write provider-owned files only.
        files_written = 0
        provider_pkg = {}
        for path, content in sorted(project_structure.items()):
            if is_codegen_owned(path):
                continue
            runtime.workspace.write_file(path, content)
            files_written += 1
            if path == 'package.json':
                try:
                    provider_pkg = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    provider_pkg = {}

        # 3. Deterministic dependency union.
        dependency_gaps = self._merge_dependencies(runtime, template_pkg, provider_pkg, artifact)
        return files_written, dependency_gaps

    def _merge_dependencies(self, runtime: 'GenerationRuntime', template_pkg: Dict[str, Any],
                            provider_pkg: Dict[str, Any], artifact: WebsiteGenerationArtifact) -> List[str]:
        base = provider_pkg or template_pkg or {}
        if not base:
            return []

        merged = dict(base)
        merged_deps = dict((template_pkg.get('dependencies') or {}))
        merged_deps.update(provider_pkg.get('dependencies') or {})
        merged_dev = dict((template_pkg.get('devDependencies') or {}))
        merged_dev.update(provider_pkg.get('devDependencies') or {})

        gaps: List[str] = []
        for raw_dep in getattr(artifact.component_tree, 'dependencies', []) or []:
            dep = str(raw_dep or '').strip()
            if not dep:
                continue
            if '@' in dep and not dep.startswith('@'):
                name, version = dep.split('@', 1)
                name, version = name.strip(), version.strip()
                if name and version:
                    merged_deps.setdefault(name, version)
                    continue
                dep = name or dep
            if dep.startswith('@') and dep.count('@') > 1:
                name, version = dep.rsplit('@', 1)
                if name and version:
                    merged_deps.setdefault(name, version)
                    continue
            if dep in merged_deps or dep in merged_dev:
                continue
            # No version defined by provider/template/component contract —
            # record the precise gap instead of inventing a version.
            gaps.append(dep)

        merged['dependencies'] = merged_deps
        if merged_dev:
            merged['devDependencies'] = merged_dev
        runtime.workspace.write_file('package.json', json.dumps(merged, indent=2))
        return gaps
