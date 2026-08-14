import time
import json
import logging
from typing import Dict, Any, Optional
from odoo.addons.nexora_studio.services.generation.core.generation_context import GenerationContext, GenerationState, GenerationProgress
from dataclasses import asdict

_logger = logging.getLogger(__name__)

class GenerationStateManager:
    """Manages checkpoint creation, resumption, interruption, and rollbacks for the Generation Pipeline."""
    
    def __init__(self):
        # Memory-backed for now; in a full DB implementation, this hits an Odoo model.
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._interruptions: Dict[str, bool] = {}
        self._metadata_store: Dict[str, Dict[str, Any]] = {}

    def save_checkpoint(self, context: GenerationContext) -> None:
        ctx_dict = asdict(context)
        # Convert enums for serialization
        ctx_dict['state'] = context.state.value
        self._checkpoints[context.context_id] = ctx_dict
        
        # Track detailed metadata as requested
        if context.context_id not in self._metadata_store:
            self._metadata_store[context.context_id] = {
                "completed_stages": [],
                "failed_stages": [],
                "retry_count": 0,
                "execution_metadata": {},
                "timestamps": {"started_at": time.time(), "last_saved": time.time()},
                "diagnostics": []
            }
        
        meta = self._metadata_store[context.context_id]
        meta["timestamps"]["last_saved"] = time.time()
        
        if context.state == GenerationState.FAILED:
            meta["failed_stages"].append(context.progress.current_step)
        elif context.state not in [GenerationState.PENDING, GenerationState.INTERRUPTED]:
            if context.state.name not in meta["completed_stages"]:
                meta["completed_stages"].append(context.state.name)
                
        _logger.info(f"Checkpoint saved for {context.context_id} at state {context.state.name}. Completed: {len(meta['completed_stages'])}")

    def load_checkpoint(self, context_id: str) -> Optional[GenerationContext]:
        if context_id not in self._checkpoints:
            return None
        data = self._checkpoints[context_id]
        
        from odoo.addons.nexora_studio.services.generation.core.generation_context import (
            RequirementModel, WebsiteBlueprint, ArchitectureModel, ComponentTree, Theme,
            Assets, Content, TemplateResolution, ValidationReport, PreviewArtifacts, Workspace, WebsiteGenerationArtifact
        )
        
        try:
            artifact_data = data.get('artifact', {})
            artifact = WebsiteGenerationArtifact(
                requirements=RequirementModel(**artifact_data.get('requirements', {})),
                blueprint=WebsiteBlueprint(**artifact_data.get('blueprint', {})),
                architecture=ArchitectureModel(**artifact_data.get('architecture', {})),
                component_tree=ComponentTree(**artifact_data.get('component_tree', {})),
                theme=Theme(**artifact_data.get('theme', {})),
                assets=Assets(**artifact_data.get('assets', {})),
                content=Content(**artifact_data.get('content', {})),
                template=TemplateResolution(**artifact_data.get('template', {})),
                design=artifact_data.get('design', {}),
                validation=ValidationReport(**artifact_data.get('validation', {})),
                previews=PreviewArtifacts(**artifact_data.get('previews', {})),
                workspace=Workspace(**artifact_data.get('workspace', {})),
                generation_metadata=artifact_data.get('generation_metadata', {})
            )
            return GenerationContext(
                context_id=data['context_id'],
                artifact=artifact,
                metadata=data.get('metadata', {}),
                progress=GenerationProgress(**data.get('progress', {})),
                state=GenerationState(data.get('state', GenerationState.PENDING.value))
            )
        except Exception as e:
            _logger.error(f"Failed to restore checkpoint for {context_id}: {str(e)}")
            return None

    def update_progress(self, context: GenerationContext, state: GenerationState, percentage: float, message: str) -> GenerationContext:
        msgs = list(context.progress.messages)
        msgs.append(message)
        prog = GenerationProgress(
            percentage=percentage,
            current_step=state.name,
            messages=msgs,
            started_at=context.progress.started_at,
            updated_at=time.time()
        )
        new_ctx = context.evolve(state=state, progress=prog)
        self.save_checkpoint(new_ctx)
        return new_ctx

    def interrupt(self, context_id: str) -> None:
        self._interruptions[context_id] = True
        _logger.warning(f"Interruption requested for {context_id}")

    def check_interruption(self, context_id: str) -> bool:
        if self._interruptions.get(context_id, False):
            return True
            
        try:
            from odoo.http import request
            if request and request.env:
                session = request.env['nexora.builder_session'].sudo().search([('session_uuid', '=', context_id)], limit=1)
                if session and session.status == 'cancelled':
                    self._interruptions[context_id] = True
                    return True
        except Exception as e:
            pass
            
        return False

    def clear_interruption(self, context_id: str) -> None:
        if context_id in self._interruptions:
            del self._interruptions[context_id]

    def rollback(self, context_id: str) -> Optional[GenerationContext]:
        # Simple rollback just loads the last valid checkpoint.
        _logger.info(f"Rolling back context {context_id}")
        if context_id in self._metadata_store:
            self._metadata_store[context_id]["diagnostics"].append(f"Rollback triggered at {time.time()}")
        return self.load_checkpoint(context_id)
        
    def cancel(self, context: GenerationContext) -> GenerationContext:
        _logger.error(f"Cancelling context {context.context_id}")
        new_ctx = context.evolve(state=GenerationState.FAILED)
        self.save_checkpoint(new_ctx)
        return new_ctx
