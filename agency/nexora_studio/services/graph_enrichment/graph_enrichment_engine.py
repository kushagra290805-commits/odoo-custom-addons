import os
from typing import List
from graph_loader import GraphLoader
from odoo_registry_enricher import OdooRegistryEnricher
from xml_view_enricher import XMLViewEnricher
from fastapi_enricher import FastAPIEnricher
from ai_pipeline_enricher import AIPipelineEnricher
from builder_pipeline_enricher import BuilderPipelineEnricher
from graph_merger import GraphMerger
from graph_exporter import GraphExporter
from graph_metrics import GraphMetrics

class GraphEnrichmentEngine:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        
    def run(self):
        print("Starting Graph Enrichment Engine...")
        loader = GraphLoader(self.workspace_path)
        try:
            nodes, links, hyperedges = loader.load()
            print(f"Loaded {len(nodes)} nodes and {len(links)} edges from Graphify output.")
        except FileNotFoundError:
            print("graph.json not found. Run Graphify AST extraction first.")
            return
            
        enrichers = [
            OdooRegistryEnricher(self.workspace_path, nodes, links),
            XMLViewEnricher(self.workspace_path, nodes, links),
            FastAPIEnricher(self.workspace_path, nodes, links),
            AIPipelineEnricher(self.workspace_path, nodes, links),
            BuilderPipelineEnricher(self.workspace_path, nodes, links),
        ]
        
        all_new_nodes = []
        all_new_links = []
        
        for enricher in enrichers:
            name = enricher.__class__.__name__
            try:
                new_nodes, new_links = enricher.enrich()
                all_new_nodes.extend(new_nodes)
                all_new_links.extend(new_links)
                print(f"{name}: +{len(new_nodes)} nodes, +{len(new_links)} edges")
            except Exception as e:
                print(f"Error in {name}: {e}")
                
        merged_nodes, merged_links = GraphMerger.merge(nodes, links, all_new_nodes, all_new_links)
        print(f"Merge complete. Total nodes: {len(merged_nodes)}, Total edges: {len(merged_links)}")
        
        metrics = GraphMetrics.generate_metrics(self.workspace_path, all_new_nodes, all_new_links)
        print("Enrichment Metrics:", metrics)
        
        json_path, dot_path, mmd_path = GraphExporter.export(self.workspace_path, merged_nodes, merged_links, hyperedges)
        print(f"Exported enriched graph to:\n  - {json_path}\n  - {dot_path}\n  - {mmd_path}")

if __name__ == "__main__":
    engine = GraphEnrichmentEngine(os.getcwd())
    engine.run()
