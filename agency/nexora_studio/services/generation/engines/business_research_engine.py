import dataclasses
import logging
from typing import Any, Dict, List, Optional, Tuple
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class BusinessResearchEngine(BaseGenerationEngine):
    """
    Acquire structured external business information.

    Two complementary research channels, both through existing execution
    layers:

      1. UCEL planner-driven web research (runtime.orchestrator).
      2. Canonical CSF business search:
             ProviderManager/source abstraction
                 -> UniversalCapabilityRouter
                 -> gosom_mcp
                 -> McpSourceAdapter.search_businesses()
                 -> BusinessData

    Normalized BusinessData becomes structured research context on
    artifact.research. Business sources are OPTIONAL: an unavailable
    provider or an empty result is isolated and recorded, never failing the
    generation. A malformed BusinessData contract violation fails this stage.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing BusinessResearchEngine (Capability-Driven)...")

        req = artifact.requirements
        search_query = f"{req.domain} business information {req.target_audience}"

        research_data = dict(artifact.research or {})

        try:
            if not hasattr(runtime, 'orchestrator'):
                raise Exception("Production orchestrator not available on runtime proxy")

            trace = runtime.orchestrator.execute_plan(
                f"Research {search_query} using web search and crawling",
                target_outputs=["search_results", "scraped_content"]
            )

            # Extract output
            research_data["trace"] = {
                "steps_completed": trace.steps_completed,
                "steps_failed": trace.steps_failed,
                "capability_trace": trace.capability_trace
            }

            # In a real scenario we'd pull trace.final_output
            # For now we just record it succeeded
            research_data["search_results"] = {"status": "completed_via_orchestrator"}

        except Exception as e:
            _logger.warning(f"BusinessResearchEngine: Planner-driven research failed: {e}")

        try:
            business_entries, status, providers_used, provider_errors, queries = (
                self._consume_business_sources(runtime, req)
            )
        except ValueError as e:
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                metadata={"business_research_status": "malformed_artifact"},
                error=str(e),
            )

        if business_entries is not None:
            research_data["business_data"] = business_entries
        research_data["business_research"] = {
            "status": status,
            "queries": queries,
            "providers_used": providers_used,
            "provider_errors": provider_errors,
        }

        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(research=research_data),
            metadata={
                "research_sources_used": len(research_data),
                "business_research_status": status,
                "business_data_count": len(business_entries or []),
            },
            error=None
        )

    # ------------------------------------------------------------------
    # Canonical CSF BusinessData consumption (Phase 47.7 / U7)
    # ------------------------------------------------------------------

    def _consume_business_sources(
        self, runtime: 'GenerationRuntime', req
    ) -> Tuple[Optional[List[Dict[str, Any]]], str, List[str], List[Dict[str, str]], List[str]]:
        """Query BUSINESS_SEARCH-capable sources through the existing source
        framework. Returns (entries, status, providers_used, provider_errors,
        queries). ``entries is None`` means no business-source attempt was
        applicable; the pipeline continues normally either way.
        """
        try:
            env = runtime.env
        except Exception:
            env = None
        if not env:
            return None, 'not_applicable', [], [], []

        from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager

        provider_errors: List[Dict[str, str]] = []
        try:
            provider_manager = ProviderManager(env)
            provider_manager.load_from_registry()
            providers = provider_manager.get_capable_providers('BUSINESS_SEARCH')
        except Exception as exc:
            provider_errors.append({
                'provider': 'source_framework',
                'operation': 'load',
                'error': str(exc),
            })
            return None, 'provider_unavailable', [], provider_errors, []

        if not providers:
            return None, 'not_applicable', [], [], []

        queries = self._business_queries(req)
        if not queries:
            return None, 'not_applicable', [], [], []

        entries: List[Dict[str, Any]] = []
        providers_used: List[str] = []
        for provider_id in providers:
            try:
                results = provider_manager.route_request(
                    provider_id, 'search_businesses', queries
                )
            except Exception as exc:
                provider_errors.append({
                    'provider': provider_id,
                    'operation': 'search_businesses',
                    'error': str(exc),
                })
                continue
            providers_used.append(provider_id)
            for item in results or []:
                entries.append(self._validate_and_serialize_business_data(item, provider_id))

        if not providers_used:
            return [], 'provider_unavailable', providers_used, provider_errors, queries
        if not entries:
            return [], 'no_data', providers_used, provider_errors, queries
        status = 'completed' if not provider_errors else 'partially_completed'
        return entries, status, providers_used, provider_errors, queries

    @staticmethod
    def _business_queries(req) -> List[str]:
        """Derive business-search queries from captured requirements only.

        Phase 47.18 (Part B): queries are built from the brief-extracted
        business identity — category + location for a local competitor
        search, falling back to name, then to domain/audience. Nothing is
        invented and no arbitrary single keywords are used.
        """
        branding = req.branding or {}
        name = branding.get('business_name') or branding.get('name')
        category = (getattr(req, 'business_category', '')
                    or branding.get('business_category') or '').strip()
        location = (getattr(req, 'location', '')
                    or branding.get('location') or '').strip()
        city = location.split(',')[0].strip() if location else ''

        if category and city:
            # Category-level local search yields comparable real businesses.
            return [f"{category} {city}"]
        if name and city:
            return [f"{name} {city}"]
        if name:
            return [str(name)]
        parts = [part for part in (category or req.domain, req.target_audience) if part]
        return [' '.join(parts)] if parts else []

    @staticmethod
    def _validate_and_serialize_business_data(item: Any, provider_id: str) -> Dict[str, Any]:
        from odoo.addons.nexora_studio.services.source_framework.domain_models import BusinessData
        if not isinstance(item, BusinessData):
            raise ValueError(
                f"Malformed BusinessData from {provider_id}: "
                f"got {type(item).__name__}, expected BusinessData"
            )
        if not item.data_id or not item.category or not isinstance(item.payload, dict):
            raise ValueError(
                f"Malformed BusinessData from {provider_id}: "
                "data_id/category/payload contract violated"
            )
        provenance = item.provenance
        return {
            'data_id': item.data_id,
            'category': item.category,
            'payload': dict(item.payload),
            'provenance': (
                dataclasses.asdict(provenance)
                if provenance and dataclasses.is_dataclass(provenance)
                else provenance
            ),
        }
