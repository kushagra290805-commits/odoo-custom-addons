# Phase 37.2 — Spline Rendering Provider Implementation Report

## Provider Architecture

The Spline rendering provider (`SplineRenderingProvider`) extends `ReactRenderingProvider`,
following the exact same pattern established by `ReactThreeFiberProvider` in Phase 37.1.
It is a peer provider under `RenderingProviderRegistry`, not a subclass of R3F.

```
RenderingProviderRegistry
├── react              → ReactRenderingProvider       (standard 2D)
├── react_three_fiber  → ReactThreeFiberProvider       (procedural 3D via Three.js)
└── spline             → SplineRenderingProvider       (embedded 3D via Spline scenes)
```

## Provider Registry Integration

- **Metadata stub** added to `_initialize_defaults()` with `provider_id="spline"`
- **Lazy-load** registration added to `get_provider()` following the existing pattern
- All three providers resolve independently and coexist

## Dependency Model

| Provider | Required npm Dependencies | Optional Dependencies |
|----------|--------------------------|----------------------|
| `react`  | react, react-dom, react-router-dom | — |
| `react_three_fiber` | three, @react-three/fiber | @react-three/drei |
| `spline` | @splinetool/react-spline | @splinetool/runtime |

Generated Spline components follow the canonical React pattern:
```jsx
import Spline from '@splinetool/react-spline';
<Spline scene="https://prod.spline.design/.../scene.splinecode" />
```

## Scene Source Policy

Scene URLs are validated by `validate_spline_scene_url()`:

| Source Type | Policy |
|---|---|
| `https://prod.spline.design/*/scene.splinecode` | Accepted |
| `https://draft.spline.design/*/scene.splinecode` | Accepted |
| `https://app.spline.design/*/scene.splinecode` | Accepted |
| `https://my.spline.design/*/scene.splinecode` | Accepted |
| `assets/local/scene.splinecode` (relative) | Accepted (local asset) |
| `http://` (non-TLS) | Rejected |
| `javascript:` | Rejected |
| `data:` | Rejected |
| Unapproved host domains | Rejected |
| Missing `.splinecode`/`.spline` extension | Rejected |

## Security Boundary

The Spline provider is a **rendering adapter**, not a code-execution engine:
- Zero subprocess/os.system/exec calls
- Zero Node.js execution
- Zero MCP client instantiation
- Zero API key requirements
- Generated React code renders Spline scenes client-side in the browser

## R3F / Spline Coexistence Model

Both 3D providers allow peer dependency references:
- R3F provider does NOT reject `@splinetool` imports (they belong to the Spline peer)
- Spline provider does NOT reject `three`/`@react-three/*` imports (they belong to the R3F peer)
- Standard React provider rejects BOTH `three` and `@splinetool`
- Both providers reject `playcanvas` and `babylon` as unapproved engines

Combined project validated successfully with both R3F and Spline components.

## Legacy Spline Audit

`models/spline_provider.py` (`nexora.provider.spline`) is referenced only by:
1. `verification/provider_conformance_suite.py` (verification script)
2. `scripts/run_piat.py` (test script)
3. `models/__init__.py` (import registration)

It is NOT referenced by the canonical generation pipeline, GenerationPipeline,
RenderingProviderRegistry, or any active production orchestration path. It remains
legacy/deprecated. The canonical Phase 37 path does NOT depend on it.

## Tavily Boundary

Zero Tavily integration in the Spline provider. No direct MCP invocation.
No API key dependency. Tavily remains optional enrichment via the existing UCP.

## Test Results

### Phase 37.1 Regression (5/5 PASS)
- Provider registration ✅
- Standard React isolation ✅
- R3F validation ✅
- Existing providers ✅
- No connector bypass ✅

### Phase 37.2 Unit Tests (19/19 PASS)
- A. Registry: react/r3f/spline all resolve ✅
- B. Standard React isolation: rejects @splinetool and three ✅
- C. R3F isolation: accepts R3F deps ✅
- D. Spline validation: accepts valid, rejects playcanvas, rejects missing dep ✅
- E. Scene source: valid URL ✅, javascript: ✅, data: ✅, HTTP ✅, bad host ✅, local asset ✅, malformed in component ✅
- F. Combined project (React + R3F + Spline) ✅
- H. No UCP bypass: no subprocess/exec/MCP ✅

### Runtime Verification (4/4 PASS)
- TEST 1: Spline-only project via canonical path ✅
- TEST 2: R3F-only project via canonical path (regression) ✅
- TEST 3: Combined React + R3F + Spline project ✅
- TEST 4: Standard React still rejects 3D ✅

## Files Changed

| File | Action | Description |
|---|---|---|
| `services/design/providers/spline_provider.py` | **NEW** | Canonical SplineRenderingProvider + scene URL validator |
| `services/design/providers/provider_registry.py` | MODIFIED | Added Spline metadata stub + lazy-load registration |
| `services/design/providers/react_provider.py` | MODIFIED | Extended mode-aware validation for @splinetool + Spline peer coexistence |
| `services/design/providers/react_three_fiber_provider.py` | MODIFIED | Removed blanket `spline` rejection (peer coexistence) |
| `docs/adr/ADR-0064-phase37-3d-website-generation-capability.md` | MODIFIED | Phase 37.2 implementation addendum |

## Remaining Limitations

- Spline `generate_project()` inherits the base React generation logic. A Spline-specific
  component template generator (producing `<Spline scene="..." />` boilerplate automatically)
  would be a natural Phase 37.3 enhancement.
- The scene URL validator uses a static approved-hosts list. If Spline adds new hosting
  domains, the list must be updated.

**Verdict:** PHASE 37.2 — SPLINE PROVIDER IMPLEMENTATION COMPLETE
