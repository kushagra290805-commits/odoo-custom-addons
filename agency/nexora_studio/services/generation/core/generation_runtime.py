import time
import typing
from typing import Any, List, Dict, Optional
from odoo.addons.nexora_studio.services.generation.core.workspace_adapter import WorkspaceAdapter
from odoo.addons.nexora_studio.services.generation.core.runtime_interfaces import (
    AIRuntimeAdapter, EventsRuntimeAdapter, StateRuntimeAdapter,
    CancellationRuntimeAdapter, AgentRuntimeAdapter, RuntimeMetadata,
    KnowledgeRuntimeAdapter
)
from odoo.addons.nexora_studio.services.generation.events.pipeline_event_bus import PipelineEventBus
from odoo.addons.nexora_studio.services.generation.core.generation_state_manager import GenerationStateManager

class GenerationRuntime:
    """
    Capability-oriented Facade representing the execution environment.
    Wraps existing infrastructure to provide a safe, immutable, and decoupled 
    runtime environment for Generation Engines and future Autonomous Agents.
    """
    def __init__(self, 
                 ai_provider_manager: Any, 
                 workspace_path: str,
                 event_bus: PipelineEventBus,
                 state_manager: GenerationStateManager,
                 session_id: str,
                 generation_id: str,
                 initiated_by: str = "system"):
                 
        from odoo.addons.nexora_studio.services.generation.core.runtime_hooks import RuntimeHooks
        
        self.hooks = RuntimeHooks()
        
        self.workspace = WorkspaceAdapter(workspace_path, self.hooks)
        self.ai = AIRuntimeAdapter(ai_provider_manager, self.hooks)
        self.events = EventsRuntimeAdapter(event_bus)
        self.state = StateRuntimeAdapter(state_manager, generation_id)
        self.cancellation = CancellationRuntimeAdapter(state_manager, generation_id)
        
        # Phase 21D UCEL wiring
        from odoo.addons.nexora_studio.services.capabilities.models import ExecutionTargetType
        from odoo.addons.nexora_studio.services.capabilities.repository import CapabilityRepository
        from odoo.addons.nexora_studio.services.capabilities.resolver import CapabilityResolver
        from odoo.addons.nexora_studio.services.capabilities.policy import CapabilityPolicyEngine
        from odoo.addons.nexora_studio.services.capabilities.security import SecurityLayer
        from odoo.addons.nexora_studio.services.capabilities.middleware import MiddlewarePipeline
        from odoo.addons.nexora_studio.services.capabilities.strategy import ExecutionStrategy
        from odoo.addons.nexora_studio.services.capabilities.scheduler import ExecutionScheduler
        from odoo.addons.nexora_studio.services.capabilities.router import UniversalCapabilityRouter
        from odoo.addons.nexora_studio.services.capabilities.executors.local import LocalToolExecutor
        from odoo.addons.nexora_studio.services.capabilities.executors.remote import RemoteToolExecutor
        from odoo.addons.nexora_studio.services.capabilities.remote.transport import TransportLayer
        from odoo.addons.nexora_studio.services.capabilities.remote.protocol import ProtocolLayer
        from odoo.http import request
        
        env = None
        try:
            env = request.env
        except:
            pass
            
        self.tool_registry = env['nexora.tool_registry'] if env else None # Local Tool Metadata
        
        self.capability_repository = CapabilityRepository(env=env)
        self.capability_resolver = CapabilityResolver(self.capability_repository)
        self.capability_policy = CapabilityPolicyEngine()
        self.security_layer = SecurityLayer()
        self.middleware = MiddlewarePipeline()
        self.execution_strategy = ExecutionStrategy()
        self.execution_scheduler = ExecutionScheduler(self.execution_strategy)
        
        from odoo.addons.nexora_studio.services.capabilities.remote.session import McpSessionManager
        self.mcp_session_manager = McpSessionManager()
        self.protocol_layer = ProtocolLayer(self.mcp_session_manager)
        self.transport_layer = TransportLayer(self.protocol_layer)
        
        executors = {
            ExecutionTargetType.LOCAL: LocalToolExecutor(self.tool_registry),
            ExecutionTargetType.REMOTE: RemoteToolExecutor(self.transport_layer)
        }
        
        self.ucel_router = UniversalCapabilityRouter(
            self.capability_resolver,
            self.capability_policy,
            self.security_layer,
            self.middleware,
            self.execution_scheduler,
            executors
        )
        
        from odoo.addons.nexora_studio.services.generation.core.runtime_interfaces import ToolRuntimeAdapter, OrchestratorRuntimeAdapter
        self.tools = ToolRuntimeAdapter(self.ucel_router)
        self.orchestrator = OrchestratorRuntimeAdapter(self.capability_resolver, self.ucel_router)

        # Phase 18.7 Knowledge Framework wiring
        from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_event_bus import KnowledgeEventBus
        from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_registry import KnowledgeRegistry
        from odoo.addons.nexora_studio.services.generation.knowledge.embedding_store import PgVectorStore
        from odoo.addons.nexora_studio.services.generation.knowledge.embedding_manager import EmbeddingManager
        from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_lifecycle import KnowledgeLifecycleManager
        from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_health import KnowledgeHealthService
        from odoo.addons.nexora_studio.services.generation.knowledge.semantic_retrieval import SemanticRetrievalEngine
        from odoo.addons.nexora_studio.services.generation.knowledge.context_budget_manager import ContextBudgetManager
        from odoo.addons.nexora_studio.services.generation.knowledge.knowledge_service import KnowledgeService
        
        self.knowledge_event_bus = KnowledgeEventBus()
        self.knowledge_registry = KnowledgeRegistry(self.knowledge_event_bus)
        self.embedding_store = PgVectorStore()
        self.embedding_manager = EmbeddingManager(ai_provider_manager, self.embedding_store)
        self.knowledge_lifecycle = KnowledgeLifecycleManager(self.knowledge_registry, self.embedding_manager, self.knowledge_event_bus)
        self.knowledge_health = KnowledgeHealthService(self.knowledge_registry, self.embedding_store)
        self.semantic_retrieval = SemanticRetrievalEngine(ai_provider_manager, self.embedding_store)
        self.context_budget_manager = ContextBudgetManager()
        self.knowledge_service = KnowledgeService(self.knowledge_registry, self.semantic_retrieval, self.context_budget_manager)
        
        self.knowledge = KnowledgeRuntimeAdapter(self.knowledge_service)

        # Phase 18.5 Agent Runtime wiring
        from odoo.addons.nexora_studio.services.generation.agents.agent_capability_registry import AgentCapabilityRegistry, AgentProfile
        from odoo.addons.nexora_studio.services.generation.agents.agent_runtime import AgentRuntime
        self.agent_capability_registry = AgentCapabilityRegistry()
        self.agent_runtime = AgentRuntime(self.agent_capability_registry, event_bus)
        self.agent = AgentRuntimeAdapter(self.agent_runtime)
        
        # Stubs for capabilities that aren't fully fleshed out yet but requested
        self.configuration = None
        self.telemetry = None
        self.git = None
        
        # Metadata will be updated by pipeline before creating ScopedRuntimeProxy
        self.metadata = RuntimeMetadata(
            session_id=session_id,
            generation_id=generation_id,
            correlation_id=generation_id,
            started_at=time.time(),
            initiated_by=initiated_by,
            runtime_version="1.0",
            environment="production",
            scope_name="Global Scope"
        )
        
        from odoo.addons.nexora_studio.services.generation.core.runtime_scope import RuntimeScopeRegistry, ScopedRuntimeProxy
        self._registry = RuntimeScopeRegistry()
        self._populate_registry()
        
    def _populate_registry(self):
        from odoo.addons.nexora_studio.services.generation.engines.business_research_engine import BusinessResearchEngine
        from odoo.addons.nexora_studio.services.generation.engines.knowledge_enrichment_engine import KnowledgeEnrichmentEngine
        from odoo.addons.nexora_studio.services.generation.engines.review_engine import ReviewEngine
        from odoo.addons.nexora_studio.services.generation.engines.requirement_engine import RequirementEngine
        from odoo.addons.nexora_studio.services.generation.engines.planning_engine import PlanningEngine
        from odoo.addons.nexora_studio.services.generation.engines.architecture_engine import ArchitectureEngine
        from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import CodeGenerationEngine
        from odoo.addons.nexora_studio.services.generation.engines.validation_engine import ValidationEngine
        from odoo.addons.nexora_studio.services.generation.engines.optimization_engine import OptimizationEngine
        from odoo.addons.nexora_studio.services.generation.engines.component_discovery_engine import ComponentDiscoveryEngine
        from odoo.addons.nexora_studio.services.generation.engines.theme_engine import ThemeEngine
        from odoo.addons.nexora_studio.services.generation.engines.asset_engine import AssetEngine
        from odoo.addons.nexora_studio.services.generation.engines.content_engine import ContentEngine
        from odoo.addons.nexora_studio.services.generation.engines.preview_engine import PreviewEngine
        from odoo.addons.nexora_studio.services.generation.engines.workspace_generator_engine import WorkspaceGeneratorEngine

        # Setup according to Phase 18.4.6 requirements
        self._registry.register(RequirementEngine, {'ai', 'state', 'events'})
        self._registry.register(BusinessResearchEngine, {'tools', 'state', 'events', 'orchestrator'})
        self._registry.register(KnowledgeEnrichmentEngine, {'ai', 'state', 'events'})
        self._registry.register(ReviewEngine, {'tools', 'ai', 'state', 'events'})
        self._registry.register(PlanningEngine, {'ai', 'state', 'events'})
        self._registry.register(ArchitectureEngine, {'ai', 'workspace', 'events'})
        self._registry.register(CodeGenerationEngine, {'ai', 'workspace', 'events'})
        self._registry.register(ValidationEngine, {'workspace', 'events', 'orchestrator'})
        self._registry.register(OptimizationEngine, {'workspace', 'telemetry'})
        
        # Unspecified but inferred scopes
        self._registry.register(ComponentDiscoveryEngine, {'ai', 'workspace', 'events'})
        self._registry.register(ThemeEngine, {'ai', 'workspace', 'events'})
        self._registry.register(AssetEngine, {'ai', 'workspace', 'events'})
        self._registry.register(ContentEngine, {'ai', 'workspace', 'events'})
        self._registry.register(WorkspaceGeneratorEngine, {'workspace', 'events'})
        self._registry.register(PreviewEngine, {'workspace', 'events'})

        # Agent registrations
        from odoo.addons.nexora_studio.services.generation.agents.review_agent import ReviewAgent
        from odoo.addons.nexora_studio.services.generation.agents.agent_capability_registry import AgentProfile
        self.agent_capability_registry.register(ReviewAgent, AgentProfile.REVIEW)

    def get_scoped_view(self, engine_class: type):
        from odoo.addons.nexora_studio.services.generation.core.runtime_scope import ScopedRuntimeProxy
        import copy
        
        allowed = self._registry.get_scope(engine_class)
        scope_name = self._registry.resolve_scope_name(engine_class.__name__)
        
        # Clone metadata with current scope name
        scoped_metadata = copy.copy(self.metadata)
        scoped_metadata.scope_name = scope_name
        
        proxy = ScopedRuntimeProxy(self, allowed)
        # We need metadata to always be accessible
        proxy._allowed_capabilities.add('metadata')
        
        # We need to inject the cloned metadata into the proxy specifically?
        # Actually proxy getattr will return self._runtime.metadata. We can override it in proxy.
        proxy.metadata = scoped_metadata
        
        return proxy
