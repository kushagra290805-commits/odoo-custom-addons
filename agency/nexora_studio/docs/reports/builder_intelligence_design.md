# Builder Intelligence Design

## Overview
The Builder Intelligence Platform adds a continuous, interactive AI layer on top of the Nexora Studio infrastructure. It transforms the system from a "one-shot" generation tool into a collaborative Workspace Editor.

## Component Architecture
- **IntelligenceEngine**: Interprets natural language, determines scope, complexity, and estimates structural impact on the active version.
- **ChangePlanningEngine**: Converts impact into an immutable ExecutionPlan. Steps are generated deterministically based on targeted component IDs and desired theme configurations.
- **DifferenceEngine**: Computes a structural diff (ChangeSet) by comparing proposed state trees against the current version.
- **WorkspaceGraphService**: A utility providing direct graph traversal over raw version payloads (get_component_node, get_asset_by_id).
- **ComponentReplacementEngine**: Wraps the ComponentDiscoveryEngine to fetch targeted replacements directly via the Design Intelligence matrix without regenerating neighboring nodes.
