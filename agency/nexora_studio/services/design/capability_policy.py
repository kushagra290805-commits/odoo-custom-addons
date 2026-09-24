# -*- coding: utf-8 -*-
from typing import List, Dict, Any

CAPABILITY_VOCABULARY = {
    "products": "The project requires product catalog or inventory management.",
    "customers": "The project requires customer accounts or profiles.",
    "orders": "The project requires order management or checkout.",
    "payments": "The project requires payment processing.",
    "inventory": "The project requires stock or inventory tracking.",
    "appointments": "The project requires appointment or booking scheduling.",
    "bookings": "The project requires reservation or booking management.",
    "subscriptions": "The project requires subscription or recurring billing.",
    "memberships": "The project requires membership or access control.",
    "leads": "The project requires lead or prospect tracking.",
    "contacts": "The project requires contact or address book management.",
    "invoicing": "The project requires invoicing or billing.",
    "website_content": "The project requires dynamic content management.",
    "forms": "The project requires form submissions with persistence.",
}

BACKEND_REQUIRED_CAPABILITIES = {
    "products": True,
    "customers": True,
    "orders": True,
    "payments": True,
    "inventory": True,
    "appointments": True,
    "bookings": True,
    "subscriptions": True,
    "memberships": True,
    "leads": True,
    "contacts": True,
    "invoicing": True,
    "website_content": True,
    "forms": True,
}

SERVICE_TO_CAPABILITY = {
    "products": "products",
    "catalog": "products",
    "store": "products",
    "ecommerce": "orders",
    "inventory": "inventory",
    "stock": "inventory",
    "customers": "customers",
    "customer": "customers",
    "client": "customers",
    "user": "customers",
    "portal": "customers",
    "orders": "orders",
    "order": "orders",
    "checkout": "orders",
    "cart": "orders",
    "payments": "payments",
    "payment": "payments",
    "billing": "payments",
    "appointments": "appointments",
    "booking": "bookings",
    "reservations": "bookings",
    "subscriptions": "subscriptions",
    "memberships": "memberships",
    "leads": "leads",
    "lead": "leads",
    "contacts": "contacts",
    "address": "contacts",
    "invoicing": "invoicing",
    "invoice": "invoicing",
    "content": "website_content",
    "blog": "website_content",
    "forms": "forms",
    "form": "forms",
}


_BACKEND_LINE_RE = __import__('re').compile(
    r'^\s*backend\s*:\s*(.+)$', __import__('re').IGNORECASE | __import__('re').MULTILINE
)


def _explicit_backend_statement(raw_input: str):
    """The Backend: line (the brief format's authoritative declaration) when present.

    Bare ``None`` -> no explicit statement; ``''`` -> ``Backend:`` with an
    empty body (still authoritative). Callers distinguish missing-line vs
    empty-statement.
    """
    if not raw_input:
        return None
    match = _BACKEND_LINE_RE.search(raw_input)
    return match.group(1).strip() if match else None


def infer_capabilities(
    business_category: str,
    services: List[str],
    features: List[str],
    goals: List[str],
    raw_input: str,
) -> List[str]:
    seen = set()
    capabilities = []

    # Phase 47.39A (verified defect): an explicit ``Backend:`` line is the
    # authoritative capability source for the labeled-brief format — the word-
    # substring approach produces false positives ("Content requirements:" ->
    # "content" -> website_content; "long-form essays" -> "form" -> forms;
    # "/reservations" page path / "Reserve a table" CTA -> "reservations" ->
    # bookings). Bare ``None`` -> no Backend declaration, preserving the
    # existing non-brief call surface.
    statement = _explicit_backend_statement(raw_input)
    if statement is not None:
        text = statement.lower()
        if not text or text.startswith('none') or not any(
            token in text for token in (
                'products', 'catalog', 'store', 'ecommerce', 'inventory',
                'stock', 'customers', 'customer', 'client', 'user', 'portal',
                'orders', 'order', 'checkout', 'cart', 'payments', 'payment',
                'billing', 'appointments', 'booking', 'reservations',
                'subscriptions', 'memberships', 'leads', 'lead', 'contacts',
                'address', 'invoicing', 'invoice', 'content', 'blog', 'forms',
                'form', 'crm',
            )
        ):
            return []
        for key, capability in SERVICE_TO_CAPABILITY.items():
            if key in text and capability not in seen:
                seen.add(capability)
                capabilities.append(capability)
        return capabilities

    # Back-compat: briefs without a Backend: line (or direct policy
    # callers passing only business_category/services).
    text_parts = [business_category] + services + features + goals + [raw_input]
    text = " ".join(filter(None, text_parts)).lower()

    for key, capability in SERVICE_TO_CAPABILITY.items():
        if key in text and capability not in seen:
            seen.add(capability)
            capabilities.append(capability)

    return capabilities


def backend_required(capabilities: List[str]) -> bool:
    for cap in capabilities:
        if BACKEND_REQUIRED_CAPABILITIES.get(cap, False):
            return True
    return False