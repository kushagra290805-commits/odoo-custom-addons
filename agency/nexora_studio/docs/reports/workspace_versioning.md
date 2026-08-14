# Workspace Versioning

## Canonical Source of Truth
The 
exora.builder.workspace.version Odoo Model acts as the definitive source of truth for the entire platform. 
exora.builder_session merely holds an ctive_version_id pointer. 

## Payload Architecture
Each version stores:
- component_tree_data: The raw JSON of all hierarchical components.
- 	heme_data: The JSON token mapping.
- ssets_data: SVGs, Images, and Fonts payloads.
- layout_data: Layout tree structures.

## Metadata & Auditing
Every version carries strict production metadata including snapshot_hash, uthor_id, ersion_number, and pproval_status. This satisfies the "Version Control Platform" requirement, natively supporting branching, history timelines, and single-click restores.
