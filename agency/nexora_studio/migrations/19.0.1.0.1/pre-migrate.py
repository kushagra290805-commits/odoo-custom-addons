# -*- coding: utf-8 -*-
"""
Adopt pre-existing Penpot/Tavily connector rows into the declarative seed.

Phases 43.8/43.9 configured `penpot_mcp` and `tavily_mcp` directly through the
Odoo UI, so those rows exist in live databases with no `ir.model.data` link.
The new `data/connector_penpot_data.xml` and `data/connector_tavily_data.xml`
seeds would therefore attempt an INSERT and violate the
`unique(connector_id)` constraint on `nexora.connector`.

This migration back-fills the missing external IDs so the loader recognises the
existing rows. Because both seed files declare `noupdate="1"`, the already
working configuration -- including encrypted credential values -- is left
untouched.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'nexora_studio'

# (xml_id, model, table, lookup_column, lookup_value)
_CONNECTOR_LINKS = [
    ('connector_penpot_mcp', 'nexora.connector', 'nexora_connector', 'connector_id', 'penpot_mcp'),
    ('connector_tavily_mcp', 'nexora.connector', 'nexora_connector', 'connector_id', 'tavily_mcp'),
]

# (xml_id, model, table, connector_id_value, credential_key or None)
_CHILD_LINKS = [
    ('config_penpot_mcp', 'nexora.mcp_server_config', 'nexora_mcp_server_config', 'penpot_mcp', None),
    ('config_tavily_mcp', 'nexora.mcp_server_config', 'nexora_mcp_server_config', 'tavily_mcp', None),
    ('credential_penpot_api_key', 'nexora.mcp_credential', 'nexora_mcp_credential', 'penpot_mcp', 'PENPOT_API_KEY'),
    ('credential_tavily_api_key', 'nexora.mcp_credential', 'nexora_mcp_credential', 'tavily_mcp', 'TAVILY_API_KEY'),
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
