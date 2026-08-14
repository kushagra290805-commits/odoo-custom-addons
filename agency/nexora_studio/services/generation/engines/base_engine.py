import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext, WebsiteGenerationArtifact
from odoo.addons.nexora_studio.services.providers.base_provider import ProviderFeatureSet, ProviderCategory

@dataclass
class EngineExecutionResult:
    success: bool
    artifact: WebsiteGenerationArtifact
    metadata: Dict[str, Any]
    error: Optional[str] = None

_logger = logging.getLogger(__name__)

class BaseGenerationEngine(ABC):
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    @abstractmethod
    def execute(self, artifact: WebsiteGenerationArtifact, runtime: 'GenerationRuntime') -> EngineExecutionResult:
        pass

