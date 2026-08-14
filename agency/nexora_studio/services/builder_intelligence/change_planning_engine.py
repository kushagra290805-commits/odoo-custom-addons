# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict

_logger = logging.getLogger(__name__)

class ChangePlanningEngine:
    """
    Consumes the impact assessment and generates a deterministic, immutable ExecutionPlan.
    """
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def generate_plan(self, impact: Dict[str, Any], session: Any) -> Any:
        _logger.info(f"ChangePlanningEngine generating execution plan for impact: {impact.get('instruction')}")
        
        # Deterministic planning
        steps = []
        if impact.get("affected_components"):
            for comp in impact["affected_components"]:
                steps.append({
                    "action": "replace_component",
                    "target": comp,
                    "strategy": "search_and_replace"
                })
                
        if impact.get("theme_changes"):
            steps.append({
                "action": "update_theme",
                "strategy": "regenerate_tokens"
            })
            
        plan_payload = {
            "instruction": impact.get("instruction"),
            "steps": steps,
            "validation_required": True
        }
        
        import json
        env = getattr(session, 'env', session) if session else None
        
        if env and hasattr(env, '__getitem__') and 'nexora.builder.execution_plan' in env:
            plan_record = env['nexora.builder.execution_plan'].create({
                'name': f"Plan for: {impact.get('instruction', 'Update')[:30]}",
                'session_id': session.id if hasattr(session, 'id') else session,
                'plan_payload': json.dumps(plan_payload),
                'status': 'draft',
                'impact_estimate': json.dumps(impact),
                'cost_estimate': impact.get("estimated_cost", 0.0)
            })
            return plan_record
        return None
