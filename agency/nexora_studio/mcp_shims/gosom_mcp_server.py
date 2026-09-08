# -*- coding: utf-8 -*-
"""Gosom Business Intelligence — MCP stdio shim (ADR-0073).

Exposes ONE semantic tool (business_search) over the local gosom
google-maps-scraper REST API. Read-only, strictly bounded, internal-only.
Compatible with the dev-venv MCP SDK 2.0.0 (lowlevel Server API).

Environment:
  GOSOM_BASE_URL        default http://127.0.0.1:8090   (internal only!)
  GOSOM_TIMEOUT_S       default 480  (total wall clock per call)
  GOSOM_POLL_INTERVAL_S default 5
  GOSOM_MAX_QUERIES     default 5
  GOSOM_LANG            default en

Run:  python gosom_mcp_server.py      (stdio transport)
"""
import asyncio
import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

BASE_URL = os.environ.get("GOSOM_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
TIMEOUT_S = int(os.environ.get("GOSOM_TIMEOUT_S", "480"))
POLL_INTERVAL_S = float(os.environ.get("GOSOM_POLL_INTERVAL_S", "5"))
MAX_QUERIES = int(os.environ.get("GOSOM_MAX_QUERIES", "5"))
DEFAULT_LANG = os.environ.get("GOSOM_LANG", "en")

MAX_DEPTH = 1
MAX_RESULTS_TOTAL = 100
JOB_TIMEOUT_S = 300

TERMINAL_STATES = {"completed", "cancelled", "discarded", "failed", "error", "ok"}

CORE_FIELDS = (
    "title", "category", "address", "complete_address", "phone", "website",
    "latitude", "longitude", "place_id", "cid", "data_id", "link", "status",
    "open_hours", "price_range", "timezone",
)
OPTIONAL_FIELDS = (
    "review_rating", "review_count", "reviews_per_rating", "images",
    "thumbnail", "descriptions", "about", "menu", "order_online",
    "reservations", "street_view_url", "plus_code", "owner",
    "credit_cards_accepted", "reviews_link",
)
FRAGILE_FIELDS = ("user_reviews", "user_reviews_extended", "popular_times")

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Natural-language Google Maps queries (max 5).",
        },
        "limit_per_query": {
            "type": "integer", "minimum": 1, "maximum": 21,
            "description": "Max places per query (fast-mode ceiling 21).",
        },
        "lang": {"type": "string", "description": "Results language."},
        "include_reviews": {
            "type": "boolean",
            "description": "Include fragile review payloads (opt-in).",
        },
    },
    "required": ["queries"],
}


def validate_bounds(queries: List[str], limit_per_query: int) -> None:
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list of strings")
    if len(queries) > MAX_QUERIES:
        raise ValueError("queries exceeds cap of %d per request" % MAX_QUERIES)
    for q in queries:
        if not isinstance(q, str) or not q.strip():
            raise ValueError("empty query line")
        if len(q) > 240:
            raise ValueError("query longer than 240 chars")
    if limit_per_query > 21:
        raise ValueError("limit_per_query capped at 21 (fast-mode ceiling)")


def _http(method: str, path: str, body: Dict[str, Any] = None,
          timeout: int = 30, form: bool = False) -> Any:
    if form and body is not None:
        data = urllib.parse.urlencode(body, doseq=True).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    elif body is not None:
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
    else:
        data = None
        headers = {}
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload


def parse_places_csv(csv_text: str) -> List[Dict[str, Any]]:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    return [dict(r) for r in rows]


def shape_place(row: Dict[str, Any], include_fragile: bool) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in CORE_FIELDS:
        val = row.get(key)
        if val not in (None, ""):
            payload[key] = val
    for key in OPTIONAL_FIELDS:
        val = row.get(key)
        if val not in (None, "", "[]"):
            payload[key] = val
    if include_fragile:
        for key in FRAGILE_FIELDS:
            val = row.get(key)
            if val not in (None, "", "[]"):
                payload[key] = val
    place_id = row.get("place_id") or row.get("cid") or row.get("data_id") \
        or row.get("link") or ""
    data_id = place_id or ("gosom:" + str(row.get("input_id", "")))
    return {
        "_type": "business_data",
        "data_id": str(data_id),
        "category": "business_place",
        "payload": payload,
    }


async def _run_job(keyword: str, limit_per_query: int,
                   include_reviews: bool, language: str) -> List[Dict[str, Any]]:
    # Gosom image compatibility: try JSON API first (POST /api/v1/scrape),
    # fallback to form UI (POST /scrape) which is the current image's working endpoint.
    started = time.monotonic()
    job_id = None
    # Attempt 1: JSON API (newer gosom)
    try:
        body = {
            "keyword": keyword,
            "lang": language,
            "max_depth": MAX_DEPTH,
            "timeout": JOB_TIMEOUT_S,
            "fast_mode": False,
        }
        resp = _http("POST", "/api/v1/scrape", body, timeout=30)
        if isinstance(resp, dict):
            job_id = resp.get("job_id") or resp.get("ID") or resp.get("id")
        elif isinstance(resp, str):
            m = re.search(r'[a-f0-9-]{36}', resp)
            if m:
                job_id = m.group(0)
    except urllib.error.HTTPError as e:
        if e.code != 405:
            raise
        job_id = None
    # Attempt 2: form UI (current image)
    if not job_id:
        form_body = {
            "name": "business_search",
            "keywords": keyword,
            "lang": language,
            "depth": str(MAX_DEPTH),
            "maxtime": "%ds" % JOB_TIMEOUT_S,
            "radius": "10000",
            "zoom": "15",
            "latitude": "0",
            "longitude": "0",
        }
        data = urllib.parse.urlencode(form_body).encode()
        req = urllib.request.Request(
            BASE_URL + "/scrape",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            m = re.search(r'[a-f0-9-]{36}', html)
            if not m:
                raise RuntimeError("gosom did not return a job_id (form fallback)")
            job_id = m.group(0)
    if not job_id:
        raise RuntimeError("gosom did not return a job_id")
    while True:
        if time.monotonic() - started > TIMEOUT_S:
            raise TimeoutError(
                "gosom job %s exceeded %ss wall clock" % (job_id, TIMEOUT_S))
        detail = _http("GET", "/api/v1/jobs/%s" % job_id, timeout=30)
        # Current image uses 'Status' capital, new API uses 'status' lower
        if isinstance(detail, dict):
            status = (detail.get("status") or detail.get("Status") or "").lower()
            # Also handle nested Data case
            if not status and isinstance(detail.get("Data"), dict):
                status = (detail.get("Data", {}).get("status") or "").lower()
        else:
            status = ""
        if status in {"completed", "available", "ok"}:
            break
        if status in (s.lower() for s in TERMINAL_STATES if s.lower() not in {"completed", "available", "ok"}):
            # Check for error
            err = detail.get("error") or detail.get("Error") or ""
            raise RuntimeError(
                "gosom job %s ended in state %s: %s" %
                (job_id, status, err))
        # Also handle pending/running - continue polling
        if status in {"pending", "running", ""}:
            await asyncio.sleep(POLL_INTERVAL_S)
            continue
        # Fallback: check if detail is list-wrapped
        await asyncio.sleep(POLL_INTERVAL_S)

    # Results: new API has 'results' in detail, old API requires separate download
    results = None
    if isinstance(detail, dict):
        results = detail.get("results") or detail.get("Results")
        # Old API: try to download CSV via /download?id=
        if results is None:
            try:
                csv_text = _http("GET", "/download?id=%s" % job_id, timeout=60)
                if isinstance(csv_text, str) and csv_text and not csv_text.startswith("<!DOCTYPE"):
                    results = csv_text
                else:
                    results = None
            except Exception:
                results = None
    if isinstance(results, list):
        places = results[:max(0, limit_per_query)]
    elif isinstance(results, dict):
        rows = results.get("items") or results.get("results") or []
        places = rows[:max(0, limit_per_query)] if isinstance(rows, list) else []
    elif isinstance(results, str):
        places = parse_places_csv(results)[:max(0, limit_per_query)]
    else:
        places = []
    if include_reviews:
        for p in places:
            p["include_reviews"] = True
    return places


async def business_search_impl(queries: List[str],
                               limit_per_query: int = 16,
                               lang: str = "",
                               include_reviews: bool = False) -> str:
    validate_bounds(queries, limit_per_query)
    all_places: List[Dict[str, Any]] = []
    language = lang or DEFAULT_LANG
    for q in queries:
        places = await _run_job(q.strip(), min(limit_per_query, 21),
                                include_reviews, language)
        all_places.extend(shape_place(p, include_reviews) for p in places)
        if len(all_places) >= MAX_RESULTS_TOTAL:
            all_places = all_places[:MAX_RESULTS_TOTAL]
            break
    return json.dumps(all_places)


server = Server("gosom-business")


@server.list_tools()
async def _handle_list_tools() -> list[types.Tool]:
    return [types.Tool(
        name="business_search",
        description=(
            "Search Google Maps for businesses matching natural-language "
            "queries. Returns bounded business_data records with identity, "
            "contact, location, hours and social-proof fields."),
        inputSchema=TOOL_SCHEMA,
    )]


@server.call_tool()
async def _handle_call_tool(tool_name: str, arguments: dict) -> types.CallToolResult:
    if tool_name != "business_search":
        raise ValueError("unknown tool: %s" % tool_name)
    result_json = await business_search_impl(**arguments)
    return types.CallToolResult(content=[
        types.TextContent(type="text", text=result_json)])


async def _run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="gosom-business",
                server_version="1.0.0",
                capabilities=types.ServerCapabilities(
                    tools=types.ToolsCapability(listChanged=False)
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(_run_stdio())
