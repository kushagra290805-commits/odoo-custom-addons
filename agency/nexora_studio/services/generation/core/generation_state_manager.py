import logging
import time
from copy import deepcopy
from dataclasses import fields
from typing import Any, Dict, Optional

from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    GenerationContext,
    GenerationProgress,
    GenerationState,
)


_logger = logging.getLogger(__name__)


class GenerationStateManager:
    """Own checkpoint, same-run rollback, interruption, and progress semantics."""

    def __init__(self, env: Any = None):
        # Deliberately process-local. Durable cross-worker resume is out of U4.
        self.env = env
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._interruptions: Dict[str, bool] = {}
        self._metadata_store: Dict[str, Dict[str, Any]] = {}

    def _metadata(self, context_id: str) -> Dict[str, Any]:
        if context_id not in self._metadata_store:
            self._metadata_store[context_id] = {
                "completed_stages": [],
                "failed_stages": [],
                "retry_count": 0,
                "execution_metadata": {},
                "timestamps": {
                    "started_at": time.time(),
                    "last_saved": time.time(),
                },
                "diagnostics": [],
            }
        return self._metadata_store[context_id]

    @staticmethod
    def _serialize_dataclass(value: Any) -> Dict[str, Any]:
        return {
            item.name: deepcopy(getattr(value, item.name))
            for item in fields(value)
        }

    def _serialize_context(self, context: GenerationContext) -> Dict[str, Any]:
        artifact = context.artifact
        return {
            'context_id': context.context_id,
            'artifact': {
                'requirements': self._serialize_dataclass(artifact.requirements),
                'research': deepcopy(artifact.research),
                'knowledge': deepcopy(artifact.knowledge),
                'architecture': self._serialize_dataclass(artifact.architecture),
                'component_tree': self._serialize_dataclass(artifact.component_tree),
                'theme': self._serialize_dataclass(artifact.theme),
                'assets': self._serialize_dataclass(artifact.assets),
                'content': self._serialize_dataclass(artifact.content),
                'template': self._serialize_dataclass(artifact.template),
                'design': deepcopy(artifact.design),
                'validation': self._serialize_dataclass(artifact.validation),
                'previews': self._serialize_dataclass(artifact.previews),
                'workspace': self._serialize_dataclass(artifact.workspace),
                'generation_metadata': deepcopy(artifact.generation_metadata),
            },
            'metadata': deepcopy(context.metadata),
            'progress': self._serialize_dataclass(context.progress),
            'state': context.state.value,
        }

    def save_checkpoint(self, context: GenerationContext) -> None:
        meta = self._metadata(context.context_id)

        # Failed/interrupted contexts describe terminal execution state, not a
        # valid resume boundary. Preserve the preceding successful checkpoint.
        if context.state in (GenerationState.FAILED, GenerationState.INTERRUPTED):
            if context.progress.current_step:
                meta["failed_stages"].append(context.progress.current_step)
            meta["timestamps"]["last_saved"] = time.time()
            return

        self._checkpoints[context.context_id] = self._serialize_context(context)
        meta["timestamps"]["last_saved"] = time.time()

        if context.state != GenerationState.PENDING:
            if context.state.name not in meta["completed_stages"]:
                meta["completed_stages"].append(context.state.name)

        _logger.info(
            "Checkpoint saved for %s at state %s. Completed: %s",
            context.context_id,
            context.state.name,
            len(meta["completed_stages"]),
        )

    def load_checkpoint(self, context_id: str) -> Optional[GenerationContext]:
        if context_id not in self._checkpoints:
            return None

        data = deepcopy(self._checkpoints[context_id])
        try:
            from odoo.addons.nexora_studio.services.generation.core.generation_context import (
                ArchitectureModel,
                Assets,
                ComponentTree,
                Content,
                PreviewArtifacts,
                RequirementModel,
                TemplateResolution,
                Theme,
                ValidationReport,
                WebsiteGenerationArtifact,
                Workspace,
            )

            if not isinstance(data, dict) or data.get('context_id') != context_id:
                raise ValueError('checkpoint identity is invalid')
            expected_context_fields = {
                'context_id', 'artifact', 'metadata', 'progress', 'state',
            }
            if set(data) != expected_context_fields:
                raise ValueError('checkpoint context fields are incompatible')
            artifact_data = data.get('artifact')
            if not isinstance(artifact_data, dict):
                raise ValueError('checkpoint artifact is not an object')

            expected_fields = {
                'requirements', 'research', 'knowledge', 'architecture',
                'component_tree', 'theme', 'assets', 'content', 'template',
                'design', 'validation', 'previews', 'workspace',
                'generation_metadata',
            }
            if set(artifact_data) != expected_fields:
                missing = sorted(expected_fields - set(artifact_data))
                unknown = sorted(set(artifact_data) - expected_fields)
                raise ValueError(
                    f'artifact fields are incompatible; missing={missing}, unknown={unknown}'
                )

            def restore(model, field_name):
                raw = artifact_data[field_name]
                if not isinstance(raw, dict):
                    raise ValueError(f'{field_name} is not an object')
                expected = {item.name for item in fields(model)}
                if set(raw) != expected:
                    raise ValueError(f'{field_name} fields are incompatible')
                return model(**deepcopy(raw))

            for flexible_field in (
                'research', 'knowledge', 'design', 'generation_metadata',
            ):
                if not isinstance(artifact_data[flexible_field], dict):
                    raise ValueError(f'{flexible_field} is not an object')
            if not isinstance(data['metadata'], dict):
                raise ValueError('context metadata is not an object')

            artifact = WebsiteGenerationArtifact(
                requirements=restore(RequirementModel, 'requirements'),
                research=artifact_data['research'],
                knowledge=artifact_data['knowledge'],
                architecture=restore(ArchitectureModel, 'architecture'),
                component_tree=restore(ComponentTree, 'component_tree'),
                theme=restore(Theme, 'theme'),
                assets=restore(Assets, 'assets'),
                content=restore(Content, 'content'),
                template=restore(TemplateResolution, 'template'),
                design=artifact_data['design'],
                validation=restore(ValidationReport, 'validation'),
                previews=restore(PreviewArtifacts, 'previews'),
                workspace=restore(Workspace, 'workspace'),
                generation_metadata=artifact_data['generation_metadata'],
            )
            progress_data = data['progress']
            if not isinstance(progress_data, dict):
                raise ValueError('progress is not an object')
            expected_progress = {item.name for item in fields(GenerationProgress)}
            if set(progress_data) != expected_progress:
                raise ValueError('progress fields are incompatible')
            return GenerationContext(
                context_id=data['context_id'],
                artifact=artifact,
                metadata=data.get('metadata', {}),
                progress=GenerationProgress(**deepcopy(progress_data)),
                state=GenerationState(data.get('state')),
            )
        except Exception as exc:
            _logger.error("Failed to restore checkpoint for %s: %s", context_id, exc)
            raise ValueError(
                f"Invalid generation checkpoint for {context_id}: {exc}"
            ) from exc

    def update_progress(
        self,
        context: GenerationContext,
        state: GenerationState,
        percentage: float,
        message: str,
    ) -> GenerationContext:
        messages = list(context.progress.messages)
        messages.append(message)
        progress = GenerationProgress(
            percentage=percentage,
            current_step=state.name,
            messages=messages,
            started_at=context.progress.started_at,
            updated_at=time.time(),
        )
        new_context = context.evolve(state=state, progress=progress)
        self.save_checkpoint(new_context)
        return new_context

    def interrupt(self, context_id: str) -> None:
        self._interruptions[context_id] = True
        _logger.warning("Interruption requested for %s", context_id)

    def check_interruption(self, context_id: str) -> bool:
        if self._interruptions.get(context_id, False):
            return True

        if self.env:
            session = self.env['nexora.builder_session'].sudo().search(
                [('session_uuid', '=', context_id)], limit=1
            )
            if session and session.status == 'cancelled':
                self._interruptions[context_id] = True
                return True
        return False

    def clear_interruption(self, context_id: str) -> None:
        self._interruptions.pop(context_id, None)

    def rollback(self, context_id: str) -> Optional[GenerationContext]:
        _logger.info("Rolling back context %s", context_id)
        meta = self._metadata(context_id)
        meta["retry_count"] += 1
        meta["diagnostics"].append(f"Rollback triggered at {time.time()}")
        return self.load_checkpoint(context_id)

    def cancel(self, context: GenerationContext) -> GenerationContext:
        _logger.error("Cancelling context %s", context.context_id)
        failed_context = context.evolve(state=GenerationState.FAILED)
        self.save_checkpoint(failed_context)
        return failed_context
