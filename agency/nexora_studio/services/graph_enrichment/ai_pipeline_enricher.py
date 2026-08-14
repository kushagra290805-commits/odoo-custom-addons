from typing import List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class AIPipelineEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_links = []
        
        ai_components = {
            "BuilderSessionOrchestrator": None,
            "ProjectPlannerService": None,
            "GenerationOrchestrator": None,
            "AIProviderManager": None,
            "CostRouter": None,
            "AIConfigurationService": None,
            "TestAIAdapter": None,
            "OpenRouterAdapter": None,
            "GitService": None,
        }
        
        for n in self.existing_nodes:
            label = n.get('label')
            if label in ai_components:
                ai_components[label] = n['id']
                
        edges_to_create = [
            ("ProjectPlannerService", "AIConfigurationService", "AI_PIPELINE"),
            ("GenerationOrchestrator", "AIProviderManager", "AI_PIPELINE"),
            ("AIProviderManager", "AIConfigurationService", "AI_PIPELINE"),
            ("AIProviderManager", "CostRouter", "AI_PIPELINE"),
            ("CostRouter", "AIConfigurationService", "AI_PIPELINE"),
            ("CostRouter", "OpenRouterAdapter", "AI_PIPELINE"),
            ("GenerationOrchestrator", "GitService", "AI_PIPELINE"),
        ]
        
        for src, dst, rel in edges_to_create:
            if ai_components.get(src) and ai_components.get(dst):
                new_links.append(Link(
                    source=ai_components[src],
                    target=ai_components[dst],
                    relation=rel,
                    context="semantic_pipeline",
                    confidence="INFERRED",
                ))
                
        return [], new_links
