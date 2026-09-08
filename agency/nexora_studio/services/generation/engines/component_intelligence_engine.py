import logging
import re
import dataclasses
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact, ComponentTree
from odoo.addons.nexora_studio.services.design.component_intelligence import ComponentIntelligence
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderCategory, ProviderFeatureSet

_logger = logging.getLogger(__name__)

# Phase 47.18 (Part H): semantic alias groups for component matching. Token
# overlap across these groups lets a semantic like '3d_canvas_container'
# match a source candidate named 'Canvas.tsx' (or carrying three_d_scene
# metadata) without fabricating provenance.
_SEMANTIC_ALIASES = {
    'hero': {'hero', 'header', 'banner', 'masthead'},
    'section': {'section', 'block', 'container', 'wrapper', 'layout'},
    'feature': {'feature', 'features', 'card', 'grid', 'service', 'services',
                # Phase 47.25: menu/featured-item semantics compose through
                # the same feature-group vocabulary (grids of items).
                'menu', 'featured', 'dish', 'dishes', 'cuisine', 'highlights'},
    'testimonial': {'testimonial', 'review', 'quote'},
    'contact': {'contact', 'cta', 'button', 'form'},
    'footer': {'footer'},
    'canvas': {'canvas', 'scene', 'three', 'r3f', 'webgl', '3d', 'threed'},
    'content': {'content', 'text', 'copy'},
    'pricing': {'pricing', 'plan', 'price', 'plans', 'packages',
                'subscription', 'tiers', 'offer', 'offers'},
    'faq': {'faq', 'question', 'questions', 'frequently', 'answers',
            'help'},
}


def _tokens(text) -> set:
    # Phase 47.25 (ADR-0077): split camelCase/PascalCase names so
    # 'FeatureGrid' yields {feature, grid} — composite names previously
    # collapsed into single unusable tokens. Split BEFORE lowering.
    original = str(text or '')
    split = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', original)
    split = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', split)
    return set(re.findall(r'[a-z0-9]+', split.lower()))


def _dependency_weight(pkg) -> int:
    """Phase 47.25 (ADR-0077): external dependency complexity of a candidate.

    Counts non-react, non-relative import specifiers in the source plus the
    Tailwind runtime requirement — native components (React + relative
    library imports only) weigh 0; registry components weigh their stack.
    """
    metadata = getattr(pkg, "metadata", {}) or {}
    code = str(metadata.get('source_code') or '')
    weight = 0
    for spec in re.findall(r"from\s+['\"]([^'\"]+)['\"]", code):
        if spec.startswith('.') or spec in ('react', 'react-dom',
                                            'react-router-dom', 'lucide-react'):
            continue
        weight += 1
    if metadata.get('requires_tailwind'):
        weight += 2
    return weight


def _expanded_tokens(semantic: str) -> set:
    tokens = _tokens(semantic)
    expanded = set(tokens)
    for token in tokens:
        for group_tokens in _SEMANTIC_ALIASES.values():
            if token in group_tokens:
                expanded |= group_tokens
    return expanded


class ComponentIntelligenceEngine(BaseGenerationEngine):
    """
    Adapter engine that delegates enrichment to the canonical ComponentIntelligence.
    Builds the final canonical component tree.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing ComponentIntelligenceEngine (Delegating to CapabilityCompositionEngine)...")

        resolved_nodes = list(artifact.component_tree.nodes) if hasattr(artifact.component_tree, "nodes") else []
        dependencies = set(artifact.component_tree.dependencies or [])
        dependencies.update(["react", "react-dom", "tailwindcss"])

        # Phase 45 (ADR-0072): consume ALREADY-RANKED candidates discovered by
        # ComponentDiscoveryEngine (published on artifact.generation_metadata).
        # This engine must NOT search/rank/resolve — it only selects from
        # resolved candidates; sections without a match keep the placeholder.
        candidates = artifact.generation_metadata.get("candidate_components") or []

        def _find_candidate(section_type: str):
            # Phase 47.18 (Part H): token/alias/metadata-aware matching that
            # strongly prefers source-backed candidates (real fetched code),
            # replacing the 47.17 failure mode where real GitHub candidates
            # were never matched. The legacy substring path is retained as a
            # compatibility fallback.
            # Phase 47.25 (ADR-0077): after semantic relevance, fewer
            # external dependencies win, then deterministic/local
            # availability — never a hardcoded source preference. The
            # selection evidence is recorded on the matched node.
            st = (section_type or "").lower()
            if not st:
                return None
            semantic_tokens = _expanded_tokens(st)
            is_3d_semantic = bool(semantic_tokens & _SEMANTIC_ALIASES['canvas'])

            best = None
            best_evidence = None
            best_rank = (-1, -1, 0, 0)  # (has_source_code, overlap, -deps, local)
            for candidate in candidates:
                pkg = candidate.get('package') if isinstance(candidate, dict) else candidate
                if pkg is None:
                    continue
                metadata = getattr(pkg, "metadata", {}) or {}
                # A candidate without real fetched source code can never
                # deliver a source-backed component: matching it would
                # fabricate provenance and (for renderer semantics) let the
                # renderer materialize placeholder code as a broken module
                # (the exact 47.18-E2E-v1 failure). Metadata-only search
                # results are therefore never matched.
                if not metadata.get('source_code'):
                    continue

                haystack = " ".join(filter(None, [
                    getattr(pkg, "name", ""),
                    getattr(pkg, "description", "") or "",
                    str(metadata.get("source_identifier", "")),
                    getattr(pkg, "component_id", ""),
                ])).lower()

                # Legacy substring compatibility (e.g. 'hero' in 'Hero Card').
                matched = st in haystack

                # Token/alias overlap.
                overlap = semantic_tokens & _tokens(haystack)

                # Metadata qualification: three_d_scene metadata matches any
                # 3D semantic ('3d', 'canvas', 'scene', 'webgl', ...).
                metadata_match = (
                    is_3d_semantic and bool(metadata.get('three_d_scene')))
                if metadata_match:
                    overlap |= {'canvas'}

                if not (matched or overlap):
                    continue

                dep_weight = _dependency_weight(pkg)
                is_local = 1 if metadata.get('source_provider') == 'native_library' else 0
                has_code = 1
                rank = (has_code, len(overlap), -dep_weight, is_local)
                if rank > best_rank:
                    best_rank = rank
                    best = candidate if isinstance(candidate, dict) else {
                        'package': candidate,
                        'score': None,
                        'final_score': None,
                    }
                    provider = getattr(pkg, 'provenance', None)
                    best_evidence = {
                        'overlap': len(overlap),
                        'dependency_weight': dep_weight,
                        'local': bool(is_local),
                        'source': (provider.provider if provider
                                   else metadata.get('source_provider', 'unknown')),
                    }
            if best is not None and best_evidence is not None:
                best['_selection'] = best_evidence
            return best

        # We can extract the components generated by DesignIntelligenceEngine
        # which are now stored in artifact.generation_metadata.
        blueprint_data = artifact.generation_metadata.get("modular_blueprint", {})
        components = blueprint_data.get("component", {}).get("abstract_components", [])

        for comp in components:
            if isinstance(comp, dict):
                comp_id = comp.get("id", "unknown")
                semantic = comp.get("purpose", "")
            else:
                comp_id = str(comp)
                semantic = str(comp)

            matched = _find_candidate(semantic or comp_id)
            if matched is not None:
                package = matched['package']
                provenance = package.provenance
                package_dependencies = list(package.dependencies or [])
                for dependency in package_dependencies:
                    if isinstance(dependency, dict) and dependency.get('name'):
                        dependencies.add(dependency['name'])
                node_metadata = {
                    **dict(package.metadata or {}),
                    "source_identifier": package.component_id,
                    "semantic": semantic,
                    "from_source": True,
                }
                # Phase 47.25 (ADR-0077): explainable selection evidence —
                # why this candidate won (overlap, deps, locality, source).
                if matched.get('_selection'):
                    node_metadata['selection'] = matched['_selection']
                resolved_nodes.append({
                    "provider": (provenance.provider if provenance else "csf"),
                    "component_id": package.component_id,
                    "code": (package.metadata or {}).get("source_code")
                            or "/* Code generated by Orchestrator */",
                    "score": matched.get('score'),
                    "final_score": matched.get('final_score'),
                    "dependencies": package_dependencies,
                    "provenance": (dataclasses.asdict(provenance)
                                   if provenance and dataclasses.is_dataclass(provenance)
                                   else provenance),
                    "metadata": node_metadata,
                })
                continue

            resolved_nodes.append({
                "provider": "nexora_dynamic",
                "component_id": comp_id,
                "code": "/* Code generated by Orchestrator */",
                "score": None,
                "final_score": None,
                "dependencies": [],
                "provenance": None,
                "metadata": {
                    "source_identifier": comp_id,
                    "semantic": semantic
                }
            })
            
        model = ComponentTree(
            nodes=resolved_nodes,
            dependencies=list(dependencies)
        )
        
        return EngineExecutionResult(
            success=True, 
            artifact=artifact.evolve(component_tree=model), 
            metadata={"intelligence_status": "delegated_to_composition_engine"}, 
            error=None
        )
