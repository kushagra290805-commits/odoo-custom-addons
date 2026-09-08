import dataclasses
import logging
from typing import Any, Dict, List
from odoo.addons.nexora_studio.services.generation.engines.base_engine import BaseGenerationEngine, EngineExecutionResult
from odoo.addons.nexora_studio.services.generation.core.generation_context import WebsiteGenerationArtifact

_logger = logging.getLogger(__name__)

class KnowledgeEnrichmentEngine(BaseGenerationEngine):
    """
    Transform raw research into structured planning knowledge.

    Phase 47.7 / U7: this engine is the SINGLE knowledge owner. It consumes
    canonical source-framework artifacts through the existing source
    abstraction (ProviderManager -> adapter -> UniversalCapabilityRouter):

      KnowledgeDocument   (SEARCH providers)
          -> artifact.knowledge['knowledge_documents']
      RepositoryArtifact  (REPOSITORY_INTELLIGENCE providers)
          -> artifact.knowledge['implementation_context']

    Phase 47.26 (ADR-0078): the stage is deterministic — the former LLM
    enrichment call produced keys consumed by no downstream stage (verified
    by runtime consumer tracing); only the source-framework collections
    above are read. External sources remain OPTIONAL and isolated;
    malformed knowledge artifacts fail this stage.
    """
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        _logger.info("Executing KnowledgeEnrichmentEngine (Phase 21E.2 Canonical Engine)...")

        raw_research = artifact.research

        try:
            documents, repo_artifacts, source_status = self._collect_source_knowledge(runtime, artifact)
        except ValueError as e:
            return EngineExecutionResult(
                success=False,
                artifact=artifact,
                metadata={"knowledge_source_status": "malformed_artifact"},
                error=str(e),
            )

        # We transform raw_research into a normalized structure for PlanningEngine
        # Even if raw_research is empty, we still generate a baseline structure

        # Phase 47.26 (ADR-0078): the LLM enrichment call is ELIMINATED —
        # runtime consumer tracing proved every LLM-generated key
        # (business_summary, usp, seo_keywords, …) is read by NO downstream
        # stage; only knowledge_documents / implementation_context (the
        # deterministic source-framework collections) are consumed. The
        # artifact contract below is unchanged: same keys, same consumers.
        req = artifact.requirements
        knowledge_struct = {
            "business_summary": (
                (getattr(req, 'business_name', '') or '') + ' — ' +
                (getattr(req, 'business_category', '') or req.domain)),
            "usp": "Quality and Reliability",
            "seo_keywords": [req.domain.lower()] + [
                str(s).lower() for s in (req.branding or {}).get('services', [])[:4]],
            "target_audience": getattr(req, 'target_audience', '') or '',
        }

        if not isinstance(knowledge_struct, dict):
            knowledge_struct = {}

        # Canonical source artifacts become first-class knowledge context —
        # never opaque transport responses, never discarded on AI fallback.
        knowledge_struct["knowledge_documents"] = documents
        knowledge_struct["implementation_context"] = repo_artifacts
        knowledge_struct["knowledge_sources"] = source_status

        return EngineExecutionResult(
            success=True,
            artifact=artifact.evolve(knowledge=knowledge_struct),
            metadata={
                "knowledge_keys": list(knowledge_struct.keys()),
                "knowledge_documents_found": len(documents),
                "repository_artifacts_found": len(repo_artifacts),
                "knowledge_source_status": source_status.get("status"),
            },
            error=None
        )

    # ------------------------------------------------------------------
    # Canonical CSF knowledge consumption (Phase 47.7 / U7)
    # ------------------------------------------------------------------

    def _collect_source_knowledge(
        self, runtime: 'GenerationRuntime', artifact: WebsiteGenerationArtifact
    ):
        """Collect KnowledgeDocument and RepositoryArtifact models through the
        existing source framework. Optional providers are isolated; malformed
        canonical artifacts raise ValueError (stage failure)."""
        from odoo.addons.nexora_studio.services.source_framework.domain_models import (
            KnowledgeDocument, RepositoryArtifact,
        )

        provider_errors: List[Dict[str, str]] = []
        documents: List[Dict[str, Any]] = []
        repo_artifacts: List[Dict[str, Any]] = []
        providers_used: List[str] = []

        try:
            env = runtime.env
        except Exception:
            env = None
        if not env:
            return documents, repo_artifacts, self._source_status(
                'not_applicable', providers_used, provider_errors, documents, repo_artifacts)

        from odoo.addons.nexora_studio.services.source_framework.provider_manager import ProviderManager

        try:
            provider_manager = ProviderManager(env)
            provider_manager.load_from_registry()
            search_providers = provider_manager.get_capable_providers('SEARCH')
            repo_providers = provider_manager.get_capable_providers('REPOSITORY_INTELLIGENCE')
        except Exception as exc:
            provider_errors.append({
                'provider': 'source_framework',
                'operation': 'load',
                'error': str(exc),
            })
            return documents, repo_artifacts, self._source_status(
                'provider_unavailable', providers_used, provider_errors, documents, repo_artifacts)

        if not search_providers and not repo_providers:
            return documents, repo_artifacts, self._source_status(
                'not_applicable', providers_used, provider_errors, documents, repo_artifacts)

        req = artifact.requirements

        # Phase 47.18 (Part B): the knowledge query is derived from the
        # brief-extracted business identity (category + market city + primary
        # audience clause) so research matches the actual client's business
        # instead of a generic domain label. Falls back to domain/audience.
        category = (getattr(req, 'business_category', '')
                    or (req.branding or {}).get('business_category') or '').strip()
        location = (getattr(req, 'location', '')
                    or (req.branding or {}).get('location') or '').strip()
        city = location.split(',')[0].strip() if location else ''
        audience = (req.target_audience or '').strip()
        audience_core = audience.split(',')[0].strip() if audience else ''
        if audience_core.lower() == 'general public':
            audience_core = ''

        doc_query = ' '.join(filter(None, [category or req.domain, city, audience_core])).strip()
        if not doc_query:
            doc_query = ' '.join(part for part in (req.domain, req.target_audience) if part)

        if doc_query:
            for provider_id in search_providers:
                try:
                    results = provider_manager.route_request(provider_id, 'search', doc_query)
                except Exception as exc:
                    provider_errors.append({
                        'provider': provider_id,
                        'operation': 'search',
                        'error': str(exc),
                    })
                    continue
                providers_used.append(provider_id)
                for item in results or []:
                    if isinstance(item, KnowledgeDocument):
                        documents.append(self._validate_and_serialize_document(item, provider_id))
                    # ComponentPackage / raw payloads belong to the component
                    # and research paths — never forced into knowledge.

        repo_query = ' '.join(filter(None, [req.domain] + list(req.goals or [])[:2]))
        for provider_id in repo_providers:
            try:
                results = provider_manager.route_request(
                    provider_id, 'fetch_repository_artifacts',
                    'repo_search', {'query': repo_query},
                )
            except Exception as exc:
                provider_errors.append({
                    'provider': provider_id,
                    'operation': 'fetch_repository_artifacts',
                    'error': str(exc),
                })
                continue
            providers_used.append(provider_id)
            for item in results or []:
                if not isinstance(item, RepositoryArtifact):
                    raise ValueError(
                        f"Malformed RepositoryArtifact from {provider_id}: "
                        f"got {type(item).__name__}, expected RepositoryArtifact"
                    )
                repo_artifacts.append(self._validate_and_serialize_repo_artifact(item, provider_id))

        return documents, repo_artifacts, self._source_status(
            None, providers_used, provider_errors, documents, repo_artifacts)

    @staticmethod
    def _source_status(status, providers_used, provider_errors, documents, repo_artifacts):
        if status is None:
            if not providers_used:
                status = 'provider_unavailable'
            elif not documents and not repo_artifacts:
                status = 'no_data'
            else:
                status = 'completed' if not provider_errors else 'partially_completed'
        return {
            'status': status,
            'providers_used': list(providers_used),
            'provider_errors': list(provider_errors),
            'documents_found': len(documents),
            'repository_artifacts_found': len(repo_artifacts),
        }

    @staticmethod
    def _serialize_provenance(provenance):
        if provenance and dataclasses.is_dataclass(provenance):
            return dataclasses.asdict(provenance)
        return provenance

    @classmethod
    def _validate_and_serialize_document(cls, item, provider_id):
        if not item.document_id or not item.title or not isinstance(item.content, str) or not item.content:
            raise ValueError(
                f"Malformed KnowledgeDocument from {provider_id}: "
                "document_id/title/content contract violated"
            )
        return {
            'document_id': item.document_id,
            'title': item.title,
            'content': item.content,
            'metadata': dict(item.metadata or {}),
            'provenance': cls._serialize_provenance(item.provenance),
        }

    @classmethod
    def _validate_and_serialize_repo_artifact(cls, item, provider_id):
        if not item.artifact_id or not item.path:
            raise ValueError(
                f"Malformed RepositoryArtifact from {provider_id}: "
                "artifact_id/path contract violated"
            )
        return {
            'artifact_id': item.artifact_id,
            'path': item.path,
            'type': item.type,
            'content': item.content,
            'metadata': dict(item.metadata or {}),
            'provenance': cls._serialize_provenance(item.provenance),
        }
