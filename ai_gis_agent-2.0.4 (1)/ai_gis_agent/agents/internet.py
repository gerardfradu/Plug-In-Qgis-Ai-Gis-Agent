"""Internet / geodata specialist for AI GIS AGENT.

This agent deliberately separates internet access from the QGIS bridge:
- generic web search uses DuckDuckGo HTML (no API key required)
- named administrative/geographic polygons use OpenStreetMap Nominatim
- downloaded vector data is stored in a local AI GIS AGENT cache and then loaded into QGIS
"""
from __future__ import annotations

import html
import json
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "IA-GIS-AGENT-by-Gerard-Franch-Duxans/1.0 (GIS research tool)"
CACHE_DIR = Path.home() / ".ai_gis_agent" / "downloads"


def _request(url: str, timeout: int = 30) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are permitted.")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310 - scheme is explicitly allowlisted above
        return response.read()


def web_search(query: str, max_results: int = 8) -> dict[str, Any]:
    """Search the public web without requiring an API key."""
    if not query or not query.strip():
        raise ValueError("La búsqueda no puede estar vacía.")
    q = urllib.parse.quote_plus(query.strip())
    url = f"https://html.duckduckgo.com/html/?q={q}"
    raw = _request(url).decode("utf-8", errors="replace")

    # DuckDuckGo HTML result links have class result__a.
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.I | re.S,
    )
    results = []
    for href, title in pattern.findall(raw):
        title = re.sub(r"<[^>]+>", "", html.unescape(title)).strip()
        href = html.unescape(href)
        if href.startswith("//"):
            href = "https:" + href
        results.append({"title": title, "url": href})
        if len(results) >= max(1, min(max_results, 20)):
            break

    return {"query": query, "source": "DuckDuckGo", "results": results}


def find_polygon(place: str, countrycodes: str = "", limit: int = 5) -> dict[str, Any]:
    """Find a named place boundary through OpenStreetMap Nominatim.

    polygon_geojson=1 requests an actual polygon/multipolygon when available.
    """
    if not place or not place.strip():
        raise ValueError("Indica qué polígono geográfico quieres buscar.")

    params = {
        "q": place.strip(),
        "format": "jsonv2",
        "polygon_geojson": "1",
        "addressdetails": "1",
        "limit": str(max(1, min(limit, 10))),
    }
    if countrycodes:
        params["countrycodes"] = countrycodes

    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    data = json.loads(_request(url).decode("utf-8"))

    candidates = []
    for item in data:
        geometry = item.get("geojson")
        if not geometry:
            continue
        candidates.append({
            "place_id": item.get("place_id"),
            "display_name": item.get("display_name"),
            "type": item.get("type"),
            "osm_type": item.get("osm_type"),
            "osm_id": item.get("osm_id"),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
            "geojson": geometry,
            "source": "OpenStreetMap / Nominatim",
            "source_url": "https://www.openstreetmap.org/",
        })

    return {"query": place, "count": len(candidates), "candidates": candidates}


def download_polygon(place: str, candidate_index: int = 0, filename: str = "") -> dict[str, Any]:
    """Search a place boundary, save its GeoJSON locally and return the path."""
    found = find_polygon(place)
    candidates = found["candidates"]
    if not candidates:
        raise ValueError(
            f"No se encontró una geometría poligonal para '{place}'. "
            "Prueba con un nombre más específico."
        )
    if candidate_index < 0 or candidate_index >= len(candidates):
        raise IndexError("candidate_index fuera de rango.")

    candidate = candidates[candidate_index]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", filename or place).strip("_") or "polygon"
    path = CACHE_DIR / f"{safe}.geojson"

    feature = {
        "type": "Feature",
        "properties": {
            "source_name": candidate["display_name"],
            "source": candidate["source"],
            "osm_type": candidate.get("osm_type"),
            "osm_id": candidate.get("osm_id"),
        },
        "geometry": candidate["geojson"],
    }
    collection = {"type": "FeatureCollection", "features": [feature]}
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")

    return {
        "path": str(path),
        "name": candidate["display_name"],
        "geometry_type": candidate["geojson"].get("type"),
        "source": candidate["source"],
        "source_url": candidate["source_url"],
    }
