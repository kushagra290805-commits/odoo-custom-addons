from typing import List, Tuple
from graph_models import Node, Link
from base_enricher import BaseEnricher

class BuilderPipelineEnricher(BaseEnricher):
    def enrich(self) -> Tuple[List[Node], List[Link]]:
        new_links = []
        
        builder_components = {
            "BuilderSessionOrchestrator": None,
            "BuilderSession": None,
            "ProjectConfiguration": None,
            "WorkspaceFileService": None,
            "GitService": None,
            "PreviewRuntimeService": None
        }
        
        for n in self.existing_nodes:
            label = n.get('label')
            if label in builder_components:
                builder_components[label] = n['id']
                
        edges_to_create = [
            ("BuilderSessionOrchestrator", "BuilderSession", "BUILDER_PIPELINE"),
            ("BuilderSession", "ProjectConfiguration", "BUILDER_PIPELINE"),
            ("BuilderSession", "WorkspaceFileService", "BUILDER_PIPELINE"),
            ("BuilderSession", "GitService", "BUILDER_PIPELINE"),
            ("BuilderSession", "PreviewRuntimeService", "BUILDER_PIPELINE")
        ]
        
        for src, dst, rel in edges_to_create:
            if builder_components.get(src) and builder_components.get(dst):
                new_links.append(Link(
                    source=builder_components[src],
                    target=builder_components[dst],
                    relation=rel,
                    context="semantic_pipeline",
                    confidence="INFERRED",
                ))
                
        return [], new_links
