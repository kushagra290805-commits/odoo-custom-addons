# -*- coding: utf-8 -*-
"""Phase 47.24 (ADR-0076): Pexels stock-photo provider — the ONE new
external resource provider.

Chosen over Unsplash on: instant free API key, 200 req/hour, free
commercial-use license with no attribution requirement, simple JSON API
(verified live). Consumed exclusively by the existing AssetEngine (the
canonical owner of provider selection / request / normalization /
caching / failure handling). The LLM never controls external image URLs:
the AssetEngine builds STRUCTURAL intents (role/subject/orientation)
and this provider resolves them.

Credential: `nexora.pexels.api_key` via ir.config_parameter (the existing
provider-key mechanism) — never in source code.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

_logger = logging.getLogger(__name__)

PEXELS_API_BASE = "https://api.pexels.com/v1"
PEXELS_PARAM_KEY = 'nexora.pexels.api_key'
_REQUEST_TIMEOUT = 20

# Process-level query cache: (query, orientation, per_page) -> normalized
# results. Repeated generation of the same site/brief never re-queries the
# API (cost control, ADR-0076). cache_hits exposes hit evidence.
_QUERY_CACHE: Dict[Tuple[str, str, int], List[Dict[str, Any]]] = {}
cache_hits = 0


def is_configured(env) -> bool:
    """True when the Pexels API key is configured (never raises)."""
    try:
        if env is None:
            return False
        key = env['ir.config_parameter'].sudo().get_param(PEXELS_PARAM_KEY)
        return bool(key)
    except Exception:
        return False


def _get_key(env) -> str:
    return (env['ir.config_parameter'].sudo().get_param(PEXELS_PARAM_KEY) or '')


def _normalize_photo(photo: Dict[str, Any]) -> Dict[str, Any]:
    src = photo.get('src') or {}
    return {
        'photo_id': photo.get('id'),
        'remote_url': src.get('large2x') or src.get('large')
                      or src.get('landscape') or src.get('original') or '',
        'alt': photo.get('alt') or '',
        'photographer': photo.get('photographer') or '',
        'source_url': photo.get('url') or '',
        'width': photo.get('width'),
        'height': photo.get('height'),
        'license': 'Pexels License (free, commercial use, no attribution required)',
    }


def search_photos(env, query: str, orientation: str = 'landscape',
                  per_page: int = 4) -> Tuple[List[Dict[str, Any]], bool]:
    """Search and normalize photos. Returns (results, from_cache).

    Never raises: any failure (missing key, network, API error) returns
    ([], False) so the caller falls back to the deterministic SVG path.
    """
    global cache_hits
    cache_key = (query, orientation, per_page)
    if cache_key in _QUERY_CACHE:
        cache_hits += 1
        return list(_QUERY_CACHE[cache_key]), True

    key = _get_key(env) if env is not None else ''
    if not key:
        return [], False
    try:
        # NOTE: Pexels (Cloudflare) rejects the default urllib user agent;
        # requests ships a UA that is accepted — verified live.
        response = requests.get(
            PEXELS_API_BASE + '/search',
            params={'query': query, 'per_page': per_page,
                    'orientation': orientation},
            headers={'Authorization': key},
            timeout=_REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            _logger.warning(
                "Pexels provider: search returned %s for query '%s'",
                response.status_code, query)
            return [], False
        data = response.json()
        results = [_normalize_photo(p) for p in (data.get('photos') or [])
                   if isinstance(p, dict) and (p.get('src') or {}).get('large2x')]
        _QUERY_CACHE[cache_key] = results
        return list(results), False
    except Exception as e:
        _logger.warning("Pexels provider: search failed for '%s': %s", query, e)
        return [], False


def download_photo(remote_url: str, max_bytes: int = 8 * 1024 * 1024) -> Optional[bytes]:
    """Download image bytes for materialization. Never raises; None on
    any failure (caller falls back)."""
    if not remote_url:
        return None
    try:
        response = requests.get(remote_url, timeout=30)
        if response.status_code != 200:
            return None
        content = response.content
        if not content or len(content) > max_bytes:
            return None
        return content
    except Exception as e:
        _logger.warning("Pexels provider: download failed: %s", e)
        return None


def reset_cache() -> None:
    """Test support: clear the process-level query cache."""
    global cache_hits
    _QUERY_CACHE.clear()
    cache_hits = 0
