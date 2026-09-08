# -*- coding: utf-8 -*-
"""Phase 45 / ADR-0072 (decision 4): enforce the normative semantic capability
vocabulary on the XML-tracked CSF sources.

The two original source rows were created inside a noupdate="1" data block, so
their ir.model_data flag is sticky and a noupdate="0" re-declaration alone does
not refresh them on upgrade. This migration applies the reconciled declaration
(SEARCH,FETCH) via ORM-adjacent SQL — no manual data edits.

Scope guard: ONLY the two xmlid-tracked rows are touched. The legacy orphan
row (no xmlid) and all other registrations remain untouched.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE nexora_source_registry sr
        SET capabilities = 'SEARCH,FETCH'
        FROM ir_model_data d
        WHERE d.model = 'nexora.source_registry'
          AND d.res_id = sr.id
          AND d.module = 'nexora_studio'
          AND d.name IN ('source_react_bits', 'source_shadcn')
        """
    )
