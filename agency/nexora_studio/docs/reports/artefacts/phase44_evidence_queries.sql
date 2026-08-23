-- Phase 44.1 §11 evidence queries — canonical, reproducible snapshot source.
-- Used for PC-4 (pre-certification snapshot) and for the §18.11 before/after diff.
-- SAFETY: read-only. Never selects a credential value, only ciphertext length.
-- Invoke: psql -U odoo -h localhost -d <db> -f phase44_evidence_queries.sql

\pset pager off
\pset footer off

\echo == Q1 core inventory (11.1) ==
SELECT c.connector_id, m.transport_type, c.state, c.health_status, c.enabled,
       m.authentication_location AS auth_loc, m.authentication_name AS auth_name,
       m.credential_key, m.session_binding, m.timeout_seconds
FROM nexora_connector c
LEFT JOIN nexora_mcp_server_config m ON m.connector_id = c.id
ORDER BY c.connector_id;

\echo == Q2 launch configuration (11.2) ==
SELECT c.connector_id, m.command, m.args_json, m.env_vars_json, m.working_directory,
       m.startup_policy
FROM nexora_connector c
LEFT JOIN nexora_mcp_server_config m ON m.connector_id = c.id
ORDER BY c.connector_id;

\echo == Q3 manifest and capability index (11.3) ==
SELECT c.connector_id,
       length(c.manifest_json) AS manifest_len,
       (SELECT count(*) FROM nexora_connector_capability k WHERE k.connector_id = c.id) AS capability_rows,
       (SELECT count(*) FROM nexora_mcp_discovered_tool d WHERE d.connector_id = c.id) AS discovered_tools
FROM nexora_connector c ORDER BY c.connector_id;
SELECT count(*) AS capability_row_total FROM nexora_connector_capability;
SELECT count(*) AS capability_definition_total FROM nexora_capability_definition;

\echo == Q4 discovered tool totals (11.4) ==
SELECT c.connector_id, count(*) AS tools
FROM nexora_mcp_discovered_tool d
JOIN nexora_connector c ON c.id = d.connector_id
GROUP BY c.connector_id ORDER BY c.connector_id;
SELECT count(*) AS discovered_tool_total FROM nexora_mcp_discovered_tool;

\echo == Q5 credentials (11.5) -- lengths only, never values ==
SELECT c.connector_id, r.credential_key, r.is_set, length(r.encrypted_value) AS ciphertext_len
FROM nexora_mcp_credential r
LEFT JOIN nexora_connector c ON c.id = r.connector_id
ORDER BY c.connector_id, r.credential_key;

\echo == Q6 capability registry enablement ==
SELECT capability_id, provider, state, enabled, supports_local, supports_remote
FROM nexora_capability_registry ORDER BY capability_id;

\echo == Q7 declarative seed coverage (ir_model_data) ==
SELECT model, count(*) AS xmlid_rows
FROM ir_model_data
WHERE module = 'nexora_studio' AND model IN
      ('nexora.connector', 'nexora.mcp_server_config', 'nexora.mcp_credential')
GROUP BY model ORDER BY model;
SELECT model, name FROM ir_model_data
WHERE module = 'nexora_studio' AND model IN
      ('nexora.connector', 'nexora.mcp_server_config', 'nexora.mcp_credential')
ORDER BY model, name;

\echo == Q8 nexora config parameters (keys only, never values) ==
SELECT key, length(value) AS value_len FROM ir_config_parameter
WHERE key LIKE 'nexora%' ORDER BY key;
