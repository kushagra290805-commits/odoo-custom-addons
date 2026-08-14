# Security & Safety Audit
- **JSON Validation Enforcement:** Provider responses strictly enforce bounding types, preventing hallucination cascades.
- **Workspace Isolation:** Graph mutation occurs dynamically in memory; the ctive_version_id is never mutated directly.
- **Rollback Safety:** Rollbacks restore pointers gracefully; rejected candidates are marked inert without impacting production trees.
- **Sanitization:** Mock/simulation placeholders (e.g., simulated mutation mapped to steps) were removed.
