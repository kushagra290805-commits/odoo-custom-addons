# -*- coding: utf-8 -*-
"""
AI Execution Context

Immutable data structure passed across the entire AI execution pipeline.
Ensures consistency, correlation, and zero parameter explosion.
"""
from dataclasses import dataclass, field
import uuid
from typing import Dict, Any, List


@dataclass(frozen=True)
class ProviderResolution:
    """Structured resolution trace from the CostRouter."""
    requested_provider: str = ''
    requested_capability: str = ''
    selected_provider: str = ''
    selected_model: str = ''
    skipped_providers: List[str] = field(default_factory=list)
    fallback_depth: int = 0
    execution_policy_applied: str = ''


@dataclass(frozen=True)
class AIExecutionContext:
    """Canonical immutable AI Execution Context."""
    
    # Identifiers
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: int = 0
    project_id: int = 0
    builder_session_id: int = 0
    
    # Task Parameters
    provider: str = ''
    model: str = ''
    capability: str = 'medium'  # Simple, Medium, Complex
    temperature: float = 0.7
    max_tokens: int = 4096
    json_mode: bool = False
    
    # Execution Policy Configuration
    timeout: int = 60
    retries: int = 2
    
    # Tracing & Telemetry
    resolution_trace: ProviderResolution = field(default_factory=ProviderResolution)
    correlation_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def with_resolution(self, resolution: ProviderResolution) -> 'AIExecutionContext':
        """Return a new context with the applied provider resolution."""
        return AIExecutionContext(
            execution_id=self.execution_id,
            request_id=self.request_id,
            job_id=self.job_id,
            project_id=self.project_id,
            builder_session_id=self.builder_session_id,
            provider=resolution.selected_provider,
            model=resolution.selected_model,
            capability=self.capability,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            json_mode=self.json_mode,
            timeout=self.timeout,
            retries=self.retries,
            resolution_trace=resolution,
            correlation_metadata=self.correlation_metadata,
        )
