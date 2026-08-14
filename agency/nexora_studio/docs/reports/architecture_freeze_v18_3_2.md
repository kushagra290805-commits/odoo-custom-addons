# Architecture Freeze v18.3.2

## Document Revision
**Version**: 18.3.2 (Generation Architecture Consolidation)
**Status**: FROZEN

## Scope of Freeze
The following architectural elements are formally frozen as of this release:
1. **The Generation Orchestrator**: Exactly one orchestrator shall exist (`WebsiteGenerationPipeline`). The pipeline operates as an explicit State Machine.
2. **The Immutable Artifact**: All generation engines shall strictly consume and enrich the `WebsiteGenerationArtifact`.
3. **The Design Truth**: Penpot is the exclusive source of design tokens and blueprints.
4. **The Execution Scaffolding**: `assets/frontend-templates` is the exclusive source of physical React/Vite boilerplate.
5. **Legacy Systems**: `template_store` and `GenerationStageRegistry` are locked into a Deprecated/Read-only state, pending physical removal in Phase 18.3.5.

## Future Development Constraints
Any future development (e.g. Streaming, Agent Runtime) must:
- Build upon the `WebsiteGenerationArtifact`.
- Integrate as Engines within the `WebsiteGenerationPipeline`.
- Conform to the 3 Permanent Architectural Rules defined in `architecture_roadmap_baseline.md`.

*No parallel architectures or duplicate orchestration paths may be introduced beyond this point.*
