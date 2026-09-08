# -*- coding: utf-8 -*-
"""Phase 47.16: production connector/source integration closure.

Ensures the tavily_knowledge source row (Tavily web-research -> SEARCH ->
KnowledgeDocument -> KnowledgeEnrichmentEngine) exists and is bound to the
tavily_mcp connector.

Why a migration at all: the XML record uses a connector_id *search* binding
(tavily_mcp is bootstrap-created from mcp_registry.json, not XML-defined, so
no ref is possible). On a FRESH install, source_registry_data.xml can load
before the connector rows exist, leaving connector_id unset (the exact
pre-existing defect visible on the legacy react_bits row). This migration is
the idempotent belt-and-suspenders: create the row when missing and always
re-bind the connector when it is null.

Scope guard: ONLY technical_name = 'tavily_knowledge'. No other source row,
connector, credential, config or capability row is touched.
"""

TAVILY_SOURCE_CONFIG = """{
    "capability_map": {
        "search": "tavily_search"
    },
    "default_payload": {
        "max_results": 5
    },
    "text_result_format": {
        "block_start_field": "Title",
        "fields": ["Title", "ID", "URL", "Content"]
    },
    "normalization": {
        "document_id": "URL",
        "title": "Title",
        "content": "Content"
    }
}"""


def migrate(cr, version):
    # 1. Ensure the row exists (idempotent insert on technical_name).
    cr.execute(
        """
        SELECT id FROM nexora_source_registry
        WHERE technical_name = 'tavily_knowledge'
        LIMIT 1
        """
    )
    row = cr.fetchone()

    if not row:
        cr.execute(
            """
            INSERT INTO nexora_source_registry
                (name, technical_name, adapter_class, sequence, capabilities,
                 config_json, is_mcp, active, create_uid, write_uid,
                 create_date, write_date)
            VALUES
                ('Tavily Knowledge Search', 'tavily_knowledge',
                 'McpSourceAdapter', 60, 'SEARCH', %s, true, true,
                 1, 1, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC')
            RETURNING id
            """,
            (TAVILY_SOURCE_CONFIG,),
        )
        print("Phase 47.16: created tavily_knowledge source row (id=%s)"
              % cr.fetchone()[0])
    else:
        # noupdate data records are never re-written on upgrade; the
        # migration is the only place the canonical config can be
        # synchronized for an existing row.
        cr.execute(
            """
            UPDATE nexora_source_registry
            SET config_json = %s,
                capabilities = 'SEARCH',
                adapter_class = 'McpSourceAdapter',
                name = 'Tavily Knowledge Search'
            WHERE technical_name = 'tavily_knowledge'
              AND (config_json IS DISTINCT FROM %s
                   OR capabilities IS DISTINCT FROM 'SEARCH')
            """,
            (TAVILY_SOURCE_CONFIG, TAVILY_SOURCE_CONFIG),
        )
        if cr.rowcount:
            print("Phase 47.16: synchronized tavily_knowledge config (%d row)"
                  % cr.rowcount)
        else:
            print("Phase 47.16: tavily_knowledge source row already exists (id=%s)"
                  % row[0])

    # 2. Always re-bind the connector when missing (fresh-install XML search
    #    may have run before the tavily_mcp connector was bootstrapped).
    cr.execute(
        """
        UPDATE nexora_source_registry s
        SET connector_id = c.id
        FROM nexora_connector c
        WHERE s.technical_name = 'tavily_knowledge'
          AND c.connector_id = 'tavily_mcp'
          AND (s.connector_id IS NULL OR s.connector_id != c.id)
        """
    )
    if cr.rowcount:
        print("Phase 47.16: bound tavily_knowledge to tavily_mcp (%d row)"
              % cr.rowcount)
    else:
        print("Phase 47.16: tavily_knowledge connector binding already correct")
