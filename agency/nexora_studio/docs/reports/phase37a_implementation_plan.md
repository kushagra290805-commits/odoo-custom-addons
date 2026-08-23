# Phase 37A — 3D Vertical-Slice Implementation Plan

**Date:** 2026-08-17
**Objective:** Establish the FIRST COMPLETE 3D website generation vertical slice using canonical UCP abstractions, strictly adhering to ADR-0063.

---

## Part 2: R3F Provider Gap Analysis

To activate the `react_three_fiber` provider without duplicating the generation engine, the new provider must subclass `RenderingProvider` and intercept specific components that map to 3D capabilities.

- **Canvas & Scene:** Missing. Needs a wrapper component that emits `<Canvas>` from `@react-three/fiber` instead of standard `<div>`.
- **Camera:** Missing. Needs `<PerspectiveCamera>` injection with responsive defaults.
- **Lighting & Environment:** Missing. Needs `<ambientLight>` and `<Environment preset="city">` (via `@react-three/drei`).
- **GLB/GLTF Loading:** Missing. Must generate a component utilizing `useGLTF(asset.localPath)`.
- **Animation:** Missing. Must map `animations=True` to `useAnimations(useGLTF().animations)`.
- **Controls:** Missing. Standard `<OrbitControls />` injection.
- **Materials:** Existing GLB materials will be used implicitly; programmatic override is missing.
- **Responsive rendering:** Native to R3F `<Canvas>` wrapping a full-width container.
- **Error boundaries:** Missing. Must wrap `<Canvas>` contents in `<Suspense fallback={<Loader />}>`.
- **Accessibility:** Missing. Needs ARIA properties applied to the container canvas and fallback DOM elements.

**Implementation Strategy:** The `react_three_fiber` implementation will share 80% of `react_provider.py`'s syntax synthesis but will override the `_render_component_tree` loop to yield WebGL elements when `asset_type == '3d_asset'`.

---

## Part 3: Canonical 3D Asset Contract

Instead of creating a new architecture, we will reuse `AssetDefinition` and `AssetMetadata` from `asset_domain.py`, extending the dictionary schema where necessary.

- **asset_id:** Existing (`AssetDefinition.asset_id`)
- **source:** Existing (`AssetDefinition.source_type`)
- **asset_type:** Existing (`'3d_asset'`)
- **URI:** *Extension required* -> `metadata.source_uri`
- **local_workspace_path:** *Extension required* -> `metadata.local_path` (populated by `AssetContentEngine` during materialization)
- **format:** Existing (`metadata.file_format = 'glb'`)
- **license / attribution:** Existing (`AssetLicense` sub-model)
- **provenance:** Existing (`license.source_url`)
- **preview:** *Extension required* -> `metadata.preview_image_uri`
- **dimensions / bounding box:** *Extension required* -> `metadata.bounding_box_meters`
- **texture metadata:** *Extension required* -> `metadata.textures_included` (boolean)
- **estimated size / optimization:** Existing (`metadata.file_size_kb_max`) + *Extension required* (`metadata.optimized`)

---

## Part 4: First Asset Source Evaluation

**Candidate:** `polyhaven_mcp` (Polyhaven CC0 Assets via MCP)

- **Actual MCP Availability:** A dedicated GoSOM MCP connector needs to be verified/registered to query Polyhaven's public API.
- **Exposed Tools Required:** `polyhaven.search`, `polyhaven.acquire_gltf`.
- **Authentication:** None required (CC0 public API).
- **Response Schema:** JSON metadata containing download URIs for `.gltf`/`.glb` and `.exr`/`.hdr` files.
- **Binary Handling:** The MCP must return a binary stream or local temp file path that the `AssetContentEngine` copies into `workspace/public/assets/`.
- **Licensing Metadata:** Guaranteed CC0, making it legally risk-free for generated sites.
- **Rate Limits:** Extremely generous; low risk of throttling during pipeline execution.
- **Suitability:** Exceptional for environment maps (HDRI) and static decorative models.

*Note: Before adding this connector, we must verify if `tavily_mcp` or `context7_mcp` can synthesize/acquire a primitive 3D model to satisfy the FIRST slice without introducing new external dependencies.*

---

## Part 5: WebGL Verification Strategy

We will reuse the existing `mcp.playwright` (PlaywrightProvider) local execution target. No new automation frameworks will be added.

**Verification Flow:**
1. **Mount:** Playwright navigates to `http://localhost:VITE_PORT`.
2. **Context Init:** `page.evaluate("return !!window.WebGLRenderingContext")` is asserted to ensure headless WebGL is supported.
3. **Canvas Exists:** `page.waitForSelector('canvas[data-engine~="three.js"]')` validates the R3F mount.
4. **No Errors:** Attach listener `page.on('console', msg => check(msg.type()))` to catch missing GLB 404s or shader compile errors.
5. **Asset Load:** Evaluate `window.__THREE__` or internal scene graph (if exposed) to count loaded meshes > 0.
6. **Snapshot:** Take a visual snapshot to prove non-black render.

---

## Part 6: Vertical Slice Acceptance Criteria (Minimum Production Changes)

To achieve the goal **without parallel architectures or immediate GoSOM expansion**, the minimum changes are:

1. **RenderingProvider Registry:** Implement `react_three_fiber.py` strictly subclassing `RenderingProvider`.
2. **Design-to-Code:** Implement R3F file generation for a minimal `<Canvas>` and `<useGLTF()>` wrapper.
3. **AssetContentEngine Mock/Stub:** For the very first slice, if no 3D connector is registered, fallback to writing a primitive procedural `.glb` (e.g. via standard library binary writing) or fetching a known CC0 URL via standard UCP HTTP, proving the pipeline from Engine -> Workspace -> Vite Build.
4. **Browser Verification:** Update `verify_phase23_*.py` script logic to include the WebGL selector assertions.

**Conclusion:** The pipeline is structurally ready. The primary execution work is implementing the specific `ReactThreeFiberProvider` syntax generation and plumbing the `AssetContentEngine` to download binaries into the workspace.