import hashlib
from typing import List, Dict, Any

class ComponentIntelligence:
    """Component Intelligence Engine for Design Analysis"""
    def compute_hash(self, code: str) -> str:
        return hashlib.md5(code.encode('utf-8')).hexdigest()

    def detect_duplicates(self, new_code: str, existing_components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_hash = self.compute_hash(new_code)
        duplicates = []
        for comp in existing_components:
            if self.compute_hash(comp.get("code", "")) == new_hash:
                duplicates.append(comp)
        return duplicates
        
    def similarity_search(self, query: str, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Jaccard similarity implementation
        q_tokens = set(query.lower().split())
        results = []
        for c in components:
            c_tokens = set((c.get("name", "") + " " + c.get("description", "")).lower().split())
            if not q_tokens or not c_tokens: continue
            score = len(q_tokens.intersection(c_tokens)) / len(q_tokens.union(c_tokens))
            if score > 0.1:
                results.append({"component": c, "score": score})
        return sorted(results, key=lambda x: x["score"], reverse=True)
        
    def dependency_graph(self, components: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        graph = {}
        for c in components:
            name = c.get("name", "")
            deps = c.get("dependencies", [])
            graph[name] = deps
        return graph
        
    def extract_metadata(self, code: str) -> Dict[str, Any]:
        has_hooks = "useState" in code or "useEffect" in code
        has_styles = "className" in code or "style=" in code
        return {"is_interactive": has_hooks, "has_styles": has_styles, "length": len(code)}
        
    def rank_components(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Rank by quality (simulated metric)
        return sorted(components, key=lambda x: x.get("quality_score", 0), reverse=True)
