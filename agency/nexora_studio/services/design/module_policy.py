# -*- coding: utf-8 -*-
"""Phase 47.34 — Platform-owned capability → Odoo module policy.

Deterministic mapping from Phase 47.32 project capabilities to approved
Odoo technical module names. Module identifiers are PLATFORM DATA:

    Project Capability  ≠  Module Plan  ≠  Odoo Module Execution

Module names never originate from LLM output, user payloads, frontend
requests, or arbitrary API payloads. The trusted input is a capability
from the Phase 47.32 controlled vocabulary; the platform decides the
module. This module contains no LLM calls and no I/O — it is pure,
deterministic policy data.

Separation of concerns:
- ``capability_policy.py`` (Phase 47.32) owns the capability vocabulary.
- This file owns the capability → approved-module allowlist and the
  deterministic Module Plan contract.
- ``nexora.client_environment_service`` (Phase 47.33/47.34) owns plan
  execution against the isolated client Odoo DB.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE_PLAN_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Platform-owned capability → module allowlist.
#
# Only Odoo modules that are (a) actually available in the target Odoo 19
# runtime addons path, (b) intentionally supported, and (c) safe for client
# provisioning are listed here. Do NOT add every Odoo module.
#
# Verified availability (community/odoo/addons): product, contacts,
# sale_management, payment, stock, crm, account, website.
# ---------------------------------------------------------------------------
CAPABILITY_MODULE_ALLOWLIST = {
    "products": {
        "module": "product",
        "reason": "Approved product/catalog implementation (Odoo core 'product').",
    },
    "customers": {
        "module": "contacts",
        "reason": "Approved customer directory implementation (Odoo core 'contacts').",
    },
    "contacts": {
        "module": "contacts",
        "reason": "Approved contact directory implementation (Odoo core 'contacts').",
    },
    "orders": {
        "module": "sale_management",
        "reason": "Approved order management implementation (Odoo core 'sale_management').",
    },
    "payments": {
        "module": "payment",
        "reason": "Approved payment framework implementation (Odoo core 'payment').",
    },
    "inventory": {
        "module": "stock",
        "reason": "Approved inventory implementation (Odoo core 'stock').",
    },
    "leads": {
        "module": "crm",
        "reason": "Approved lead tracking implementation (Odoo core 'crm').",
    },
    "invoicing": {
        "module": "account",
        "reason": "Approved invoicing implementation (Odoo core 'account').",
    },
    "website_content": {
        "module": "website",
        "reason": "Approved website/CMS implementation (Odoo core 'website').",
    },
    "forms": {
        "module": "website",
        "reason": "Approved form persistence implementation (Odoo 'website' form builder).",
    },
}

# Capabilities from the Phase 47.32 vocabulary that intentionally have NO
# approved Odoo implementation in this runtime. They are explicit — never
# silently mapped to an unrelated module.
UNMAPPED_CAPABILITY_REASONS = {
    "appointments": "No approved Odoo implementation in the target runtime (enterprise-only).",
    "bookings": "No approved Odoo implementation in the target runtime.",
    "subscriptions": "No approved Odoo implementation in the target runtime (enterprise-only).",
    "memberships": "No approved Odoo implementation in the target runtime.",
}


class ModulePolicyError(ValueError):
    """Raised when a capability/module request violates the module policy."""


def _capability_vocabulary():
    from odoo.addons.nexora_studio.services.design.capability_policy import (
        CAPABILITY_VOCABULARY,
    )
    return CAPABILITY_VOCABULARY


def is_module_allowed(module_name):
    """Defense-in-depth check used by the privileged installer.

    Only module names explicitly represented in the platform-owned
    allowlist may ever reach the Odoo installation primitive. Any other
    identifier (LLM-produced, user-supplied, arbitrary) is rejected.
    """
    return module_name in approved_module_names()


def approved_module_names():
    """Frozenset of approved technical module names (platform data)."""
    return frozenset(entry["module"] for entry in CAPABILITY_MODULE_ALLOWLIST.values())


def build_module_plan(capabilities):
    """Deterministically build an approved Module Plan from capabilities.

    :param capabilities: iterable of capability strings (Phase 47.32 vocabulary)
    :return: plan dict (schema_version, capabilities, modules,
             unresolved_capabilities, supported)
    :raises ModulePolicyError: when a capability is not part of the
        controlled vocabulary (unknown/arbitrary capability — rejected,
        no plan, no installation).
    """
    if capabilities is None:
        capabilities = []
    if isinstance(capabilities, str):
        capabilities = [capabilities]

    vocabulary = _capability_vocabulary()

    # Normalize + deduplicate; reject unknown capabilities outright.
    seen = set()
    normalized = []
    for capability in capabilities:
        if not isinstance(capability, str) or not capability.strip():
            raise ModulePolicyError(
                "Invalid capability entry: capabilities must be non-empty strings."
            )
        capability = capability.strip()
        if capability not in vocabulary:
            raise ModulePolicyError(
                "Unknown capability '%s' is not part of the controlled "
                "vocabulary; no module plan can be built." % capability
            )
        if capability not in seen:
            seen.add(capability)
            normalized.append(capability)

    # Deterministic ordering.
    normalized = sorted(normalized)

    modules_by_name = {}
    unresolved = []
    for capability in normalized:
        entry = CAPABILITY_MODULE_ALLOWLIST.get(capability)
        if entry is None:
            unresolved.append({
                "capability": capability,
                "reason": UNMAPPED_CAPABILITY_REASONS.get(
                    capability,
                    "No approved Odoo module mapping for this capability.",
                ),
            })
            continue
        name = entry["module"]
        if name in modules_by_name:
            # Duplicate module elimination (e.g. customers + contacts).
            if capability not in modules_by_name[name]["source_capabilities"]:
                modules_by_name[name]["source_capabilities"].append(capability)
        else:
            modules_by_name[name] = {
                "name": name,
                "source_capabilities": [capability],
                "reason": entry["reason"],
                "required": True,
                "supported": True,
            }

    plan = {
        "schema_version": MODULE_PLAN_SCHEMA_VERSION,
        "capabilities": normalized,
        "modules": [modules_by_name[name] for name in sorted(modules_by_name)],
        "unresolved_capabilities": unresolved,
        "supported": bool(modules_by_name),
    }
    _logger.debug("Module plan built for %s -> %s", normalized, list(modules_by_name))
    return plan
