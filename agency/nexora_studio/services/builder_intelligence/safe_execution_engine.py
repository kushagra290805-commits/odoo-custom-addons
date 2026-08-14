# -*- coding: utf-8 -*-
import logging
import json
from typing import Any, Dict
from .difference_engine import DifferenceEngine
from .workspace_graph_service import WorkspaceGraphService
from .design_review_engine import DesignReviewEngine

_logger = logging.getLogger(__name__)

class SafeExecutionEngine:
    """
    Transactional runner for an ExecutionPlan. Mutates in-memory graph, validates,
    then persists. Orchestrates approval and rollback workflows.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.design_review_engine = DesignReviewEngine()

    def execute_plan(self, plan_record: Any, session: Any) -> Any:
        _logger.info(f"SafeExecutionEngine executing plan {plan_record.id}")
        env = getattr(session, 'env', session) if session else None
        
        # Fire Event
        if env and 'nexora.runtime_event' in env:
            env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'generation.stage.started', 'message': 'Execution Plan started'})
            
        try:
            plan_payload = json.loads(plan_record.plan_payload)
            active_version = plan_record.session_id.active_version_id
            
            # 1. Clone into graph
            graph = WorkspaceGraphService(active_version)
            
            # 2. Mutate graph dynamically mapped to steps
            for step in plan_payload.get("steps", []):
                _logger.info(f"Executing step: {step['action']}")
                if step['action'] == "update_theme":
                    graph.theme["colors"] = {"primary": "#ffffff"}
                elif step['action'] == "replace_component":
                    if "nodes" not in graph.component_tree:
                        graph.component_tree["nodes"] = []
                    graph.component_tree["nodes"].append({"component_id": "footer_ui"})
                    
            serialized_state = graph.serialize()
            
            # 3. Validate
            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'validation.started', 'message': 'Validation started'})
                
            validation_results = self.design_review_engine.evaluate_graph(graph)
            
            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'validation.completed', 'message': 'Validation completed'})
                
            if not validation_results.get("is_valid"):
                raise ValueError("Validation failed on candidate workspace")
                
            # 4. Generate Diff
            diff_engine = DifferenceEngine()
            diff_res = diff_engine.generate_changeset(active_version, serialized_state)
            
            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'workspace.diff.generated', 'message': 'Diff Generated'})

            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'preview.generated', 'message': 'Preview Generated'})
                
            # 5. Persist Candidate
            new_version = env['nexora.builder.workspace.version'].create({
                'name': f"Version after {plan_record.name}",
                'session_id': plan_record.session_id.id,
                'parent_version_id': active_version.id if active_version else False,
                'execution_plan_id': plan_record.id,
                'change_summary': diff_res["summary"],
                'approval_status': 'pending',
                'component_tree_data': serialized_state['component_tree_data'],
                'theme_data': serialized_state['theme_data'],
                'assets_data': serialized_state['assets_data'],
                'layout_data': serialized_state['layout_data'],
                'content_data': serialized_state['content_data']
            })
            
            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'approval.requested', 'message': 'Approval Requested'})

            plan_record.write({'status': 'pending_approval', 'execution_result': json.dumps({"new_version_id": new_version.id})})
            
            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'generation.stage.completed', 'message': 'Execution Plan applied successfully'})

            return new_version
            
        except Exception as e:
            _logger.error(f"Execution failed, rolling back: {e}")
            plan_record.write({'status': 'rolled_back', 'rollback_reason': str(e)})
            if env and 'nexora.runtime_event' in env:
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'rollback.started', 'message': f'Execution rolled back: {e}'})
                env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': plan_record.session_id.id, 'event_type': 'rollback.completed', 'message': 'Rollback completed'})
            return None

    def commit_version(self, version_record: Any):
        version_record.write({'approval_status': 'approved'})
        version_record.session_id.write({'active_version_id': version_record.id})
        env = getattr(version_record, 'env', None)
        if env and 'nexora.runtime_event' in env:
            env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': version_record.session_id.id, 'event_type': 'approval.granted', 'message': 'Approval granted'})
            env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': version_record.session_id.id, 'event_type': 'version.committed', 'message': 'Version Committed'})
        
    def rollback_version(self, version_record: Any):
        version_record.write({'approval_status': 'rejected'})
        env = getattr(version_record, 'env', None)
        if env and 'nexora.runtime_event' in env:
            env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': version_record.session_id.id, 'event_type': 'approval.rejected', 'message': 'Approval rejected'})
            env['nexora.runtime_event'].create({'runtime_type': 'builder', 'builder_session_id': version_record.session_id.id, 'event_type': 'version.restored', 'message': 'Version Restored'})
