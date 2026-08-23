# -*- coding: utf-8 -*-
"""
Correct the live Penpot MCP authentication boundary and drop an orphan credential.

Phase 43.8 originally configured `penpot_mcp` to send its durable API key as an
`Authorization: Bearer` header. Live verification against the bundled Penpot MCP
server (`/opt/penpot/mcp/index.js`) proved that server never parses
`Authorization`/`Bearer` at all -- it reads the token exclusively from the
`userToken` HTTP query parameter. The header configuration was therefore
silently ignored and project-bound tools such as `export_shape` failed with
"No userToken found in session context".

`data/connector_penpot_data.xml` declares the corrected contract, but it is
loaded with `noupdate="1"`, so already-adopted rows are not rewritten by the
loader. This migration applies the correction in place.

The encrypted `PENPOT_API_KEY` value is never read, written, or logged here.
"""
import logging

_logger = logging.getLogger(__name__)


def _correct_penpot_auth(env):
    """Repoint Penpot authentication from the ignored header to the query parameter."""
    config = env['nexora.mcp_server_config'].search([
        ('connector_id.connector_id', '=', 'penpot_mcp'),
    ], limit=1)
    if not config:
        return

    values = {
        'authentication_location': 'query',
        'authentication_name': 'userToken',
        'authentication_scheme': 'none',
        'allowed_request_context_fields_json': '["userToken"]',
    }
    changed = {k: v for k, v in values.items() if config[k] != v}
    if changed:
        config.write(changed)
        _logger.info(
            "penpot_mcp authentication corrected to query/userToken (fields: %s)",
            ', '.join(sorted(changed)),
        )


def _remove_orphan_penpot_credential(env):
    """Delete the empty lowercase `penpot_api_key` duplicate, if it is unreferenced.

    Credential lookup in OdooCredentialResolver is an exact, case-sensitive key
    match, so a lowercase variant can never satisfy `credential_key`.
    """
    Credential = env['nexora.mcp_credential']
    orphan = Credential.search([
        ('connector_id.connector_id', '=', 'penpot_mcp'),
        ('credential_key', '=', 'penpot_api_key'),
    ], limit=1)
    if not orphan:
        return

    if orphan.is_set:
        _logger.warning("Orphan credential 'penpot_api_key' holds a value; leaving it untouched.")
        return

    referenced = env['nexora.mcp_server_config'].search_count([
        ('credential_key', '=', 'penpot_api_key'),
    ])
    if referenced:
        _logger.warning(
            "Credential 'penpot_api_key' is referenced by %s server config(s); leaving it untouched.",
            referenced,
        )
        return

    orphan.unlink()
    _logger.info("Removed unreferenced empty credential 'penpot_api_key' for penpot_mcp.")


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _correct_penpot_auth(env)
    _remove_orphan_penpot_credential(env)
