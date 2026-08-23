# Phase 37 — 3D Website Generation Capability Gap Audit

**Date:** 2026-08-17
**Objective:** Audit existing 3D generation capabilities and identify external connector candidates to expand 3D website generation via the canonical Universal Connector Platform (UCP).
**Constraint Check:** Read-only audit. No production code modified.

---

## 1. Existing 3D Generation Architecture

Currently, Nexora Studio's 3D architecture is entirely restricted to the **planning and design phase**. 
- The `AssetPlanningEngine`, `BlueprintValidator`, and `ComponentIntelligence` modules successfully parse intents to request 3D assets, emitting `3d_asset` directives and specifying `glb` formats.
- Render domains and blueprint models support strategies like `webgl`, `canvas`, and `immersive`.
- The `provider_registry.py` contains a metadata stub for a future `react_three_fiber` rendering provider.

However, there is **zero execution capability**. The `react_provider.py` explicitly throws validation errors (`Prohibited 3D canvas engine reference found`) if 3D elements are encountered to prevent unsupported hallucinations. There is no active pipeline to acquire models, build 3D scenes, or optimize GLTF files.

---

## 2. Existing Capability Inventory

| Capability | Current Status | Existing Owner | Existing Connector | Missing Capability |
| :--- | :--- | :--- | :--- | :--- |
| **A. 3D scene gen** | Planned in DS | `DesignSystem` | None | Scene synthesis execution |
| **B. Three.js / R3F** | Stubbed | `react_three_fiber` (Stub) | None | Code generation for WebGL |
| **C. GLTF / GLB** | Schema only | `AssetDomain` | None | Parsing, binary handling, compression |
| **D. 3D model search**| Gap | None | None | Querying 3D model repositories |
| **E. 3D asset acqu.** | Gap | None | None | Downloading and extracting 3D files |
| **F. Textures/Mats** | Gap | None | None | Acquiring PBR material maps |
| **G. HDRI/Env** | Gap | None | None | Acquiring environment lighting maps |
| **H. Procedural geo** | Gap | None | None | Generating programmatic geometry |
| **I. Animation** | DS property only | `ProviderCapabilityModel`| None | Synthesizing R3F animation loops |
| **J. Camera/Lights** | Planned (`lighting_mood`) | `AssetPlanningEngine` | None | R3F camera/light translation |
| **K. Component gen** | CSS 3D only | `AceternityAdapter` | None | True WebGL component generation |
| **L. Design-to-code** | 2D React only | `ReactRenderingProvider` | None | R3F specific design-to-code |
| **M. Browser render** | 2D DOM only | None | None | Headless WebGL browser support |
| **N. Visual verify** | Gap | None | None | Visual diffing of canvas outputs |
| **O. Performance** | Payload limits | `BlueprintValidator` | None | Polygon count / texture size reduction |
| **P. Accessibility** | `aria_role` only | `AssetContentValidator` | None | Canvas a11y (focus, descriptions) |
| **Q. Licensing** | Gap | None | None | CC0 / Attribution tracking for 3D |

---

## 3. Existing Connector Inventory

The canonical UCP currently manages three connectors, none of which natively support 3D domains:
1. **`github_mcp`**: Git operations.
2. **`context7_mcp`**: Standard LLM generation (lacks specialized 3D tools/knowledge bases).
3. **`tavily_mcp`**: Web search (could theoretically search for assets, but cannot acquire/process binary GLB files natively).

---

## 4. Capability Gaps

To achieve production-grade 3D website generation, the system requires capabilities across three execution pillars:
1. **Asset Acquisition & Generation:** The ability to find, generate (Text-to-3D), or download GLB models, HDRIs, and PBR textures.
2. **Scene Synthesis:** Specialized code generation tailored for React Three Fiber (R3F) to compose assets, cameras, lighting, and animations correctly.
3. **Optimization & Validation:** The ability to compress binaries (DRACO) and verify WebGL canvas renders.

---

## 5. Connector Candidates

To fill these gaps using the GoSOM MCP model, the following candidates are proposed:

### Candidate 1: Luma AI / Meshy MCP (GoSOM)
- **Capability:** Generative 3D (Text-to-3D, Image-to-3D).
- **Workflow:** E, D, Q (Acquisition, Discovery).
- **Output:** `.glb` or `.obj` binaries.

### Candidate 2: Sketchfab / Polyhaven MCP (GoSOM)
- **Capability:** High-quality CC0 3D asset, material, and HDRI acquisition.
- **Workflow:** D, E, F, G, Q.
- **Output:** Verified PBR materials, HDRIs, and `.glb` files.

### Candidate 3: glTF-Transform MCP (GoSOM Local Tool)
- **Capability:** GLB/GLTF binary optimization, DRACO compression, and metadata extraction.
- **Workflow:** C, O, P, Q (Handling, Performance, Provenance).
- **Output:** Optimized binary streams and JSON metadata.

### Candidate 4: Context7 R3F Expert MCP (Reuse / Extension)
- **Capability:** R3F/Three.js specialized scene code generation.
- **Workflow:** A, B, H, I, J, K, L.
- **Output:** `.jsx` / `.tsx` React components.

---

## 6. Connector-to-Capability Mapping

| GoSOM Connector | Target Capabilities | UCP Integration Point |
| :--- | :--- | :--- |
| **Context7 R3F Expert** | A, B, H, I, J, K, L | `ConnectorDispatcher.dispatch(tools.generate_r3f)` |
| **Polyhaven/Sketchfab** | D, E, F, G, Q | `ConnectorDispatcher.dispatch(asset.acquire.3d)` |
| **glTF-Transform Local**| C, O | `ConnectorDispatcher.dispatch(asset.optimize.glb)` |
| **WebGL Playwright** | M, N | `ConnectorDispatcher.dispatch(verify.canvas)` |

---

## 7. Reuse Opportunities

- **Context7 Extension:** Instead of building a new R3F generation connector, we can **reuse the existing `context7_mcp` connector**. By exposing a new capability namespace (e.g., `generation.code.r3f`) or provisioning a specialized prompt profile within the UCP registry, we leverage the canonical pipeline without new infrastructure.
- **Tavily Fallback:** `tavily_mcp` can be reused immediately to search for open-source CC0 3D repositories as an interim discovery mechanism.

---

## 8. Duplicate/Parallel Architecture Risks

To enforce ADR-0063, we must avoid the following architectural violations:
- **Risk 1:** Creating a `3d_asset_manager.py` that makes direct HTTP requests to Polyhaven/Sketchfab.
  - **Mitigation:** All asset acquisition MUST be wrapped as an MCP server (e.g., `polyhaven_mcp`) and executed strictly through `ConnectorRuntime.dispatch()`.
- **Risk 2:** Creating a parallel `ReactThreeFiberEngine` that duplicates `react_provider.py`'s file synthesis logic.
  - **Mitigation:** The stubbed `react_three_fiber` provider in `provider_registry.py` must subclass the canonical `RenderingProvider` and integrate cleanly into the `WorkspaceGeneratorEngine`.

---

## 9. Recommended Connector Implementation Order

1. **Context7 R3F Generation Capability (Reuse):** Enable R3F synthesis via existing `context7_mcp`. *(Solves B, K, L)*
2. **Polyhaven / Asset Acquisition MCP (New GoSOM):** Introduce a connector for HDRI and CC0 model acquisition. *(Solves E, F, G)*
3. **glTF-Transform Optimization MCP (New GoSOM):** Add a local CLI/MCP connector for payload reduction. *(Solves C, O)*

---

## 10. Verification Strategy

1. **Unit Testing:** Register `polyhaven_mcp` via `ConnectorPlatformBootstrap`. Call `ConnectorRuntime.dispatch(capability='asset.acquire')` and verify a valid binary stream is returned without bypassing the dispatcher.
2. **Integration Testing:** Run the `AssetContentEngine` and `WorkspaceGeneratorEngine` end-to-end to generate a React project that correctly includes an R3F `<Canvas>` and a downloaded `.glb` file, utilizing only canonical transport layers.
