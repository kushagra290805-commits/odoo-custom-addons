# -*- coding: utf-8 -*-
"""
Adopt pre-existing Context7/GitHub connector rows and the missing Firecrawl
credential into declarative external IDs (audit C-10 / G-18).

Context7 and GitHub were configured imperatively (never seeded), so their
connector/config/credential rows carry no `ir.model.data` link. Firecrawl was
seeded without its credential placeholder, so `FIRECRAWL_API_KEY` exists as a
row with no xmlid. The Phase 44.2 closure seeds
(`data/connector_context7_data.xml`, `data/connector_github_data.xml`) and the
firecrawl credential seed would therefore attempt INSERTs and violate the
`unique(connector_id)` / uniqueness constraints on live databases.

Following the pattern established by `migrations/19.0.1.0.1/pre-migrate.py`,
this migration back-fills the missing external IDs so the loader recognises
the existing rows. All target seeds declare `noupdate="1"`, so working
configurations -- including encrypted credential values -- are untouched.

Credential VALUES are never read, written, or logged here; only row identity
(`res_id`) is linked.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'nexora_studio'

# (xml_id, model, table, lookup_column, lookup_value)
_CONNECTOR_LINKS = [
    ('connector_context7_mcp', 'nexora.connector', 'nexora_connector', 'connector_id', 'context7_mcp'),
    ('connector_github_mcp', 'nexora.connector', 'nexora_connector', 'connector_id', 'github_mcp'),
]

# (xml_id, model, table, connector_id_value, credential_key or None)
_CHILD_LINKS = [
    ('config_context7_mcp', 'nexora.mcp_server_config', 'nexora_mcp_server_config', 'context7_mcp', None),
    ('config_github_mcp', 'nexora.mcp_server_config', 'nexora_mcp_server_config', 'github_mcp', None),
    ('credential_firecrawl_api_key', 'nexora.mcp_credential', 'nexora_mcp_credential', 'firecrawl_mcp', 'FIRECRAWL_API_KEY'),
    ('credential_context7_api_key', 'nexora.mcp_credential', 'nexora_mcp_credential', 'context7_mcp', 'CONTEXT7_API_KEY'),
    ('credential_github_personal_access_token', 'nexora.mcp_credential', 'nexora_mcp_credential', 'github_mcp', 'GITHUB_PERSONAL_ACCESS_TOKEN'),
]


def _already_linked(cr, xml_id):
    cr.execute(
        "SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s",
        (MODULE, xml_id),
    )
    return bool(cr.fetchone())


def _link(cr, xml_id, model, res_id):
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date)
        VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
        """,
        (MODULE, xml_id, model, res_id),
    )
    _logger.info("Adopted existing %s id=%s as %s.%s", model, res_id, MODULE, xml_id)


def migrate(cr, version):
    if not version:
        return

    for xml_id, model, table, column, value in _CONNECTOR_LINKS:
        if _already_linked(cr, xml_id):
            continue
        cr.execute(f"SELECT id FROM {table} WHERE {column} = %s LIMIT 1", (value,))
        row = cr.fetchone()
        if row:
            _link(cr, xml_id, model, row[0])

    for xml_id, model, table, connector_value, credential_key in _CHILD_LINKS:
        if _already_linked(cr, xml_id):
            continue
        params = [connector_value]
        sql = f"""
            SELECT child.id
              FROM {table} child
              JOIN nexora_connector conn ON conn.id = child.connector_id
             WHERE conn.connector_id = %s
        """
        if credential_key:
            sql += " AND child.credential_key = %s"
            params.append(credential_key)
        sql += " LIMIT 1"

        cr.execute(sql, tuple(params))
        row = cr.fetchone()
        if row:
            _link(cr, xml_id, model, row[0])
