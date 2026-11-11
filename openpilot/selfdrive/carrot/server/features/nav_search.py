"""Destination search backends for the Carrot Web navigation page.

Mapbox stays available, but its POI index is weak for mainland China, so AMap
(GCJ-02) and Baidu (BD-09) are offered as well. Both services return Chinese
datum coordinates, while navd expects WGS84, so every result is converted here
before it is written to NavDestination.

The API key never leaves the device: the server performs the request and only
the converted results are returned to the browser.
"""
from __future__ import annotations

import json
import math
import urllib.parse
from pathlib import Path
from typing import Any

import aiohttp

# Keys inside amapnavi/nav_params.json (UnifiedParams), edited on the
# http://<device>:8088/nav_params page. Mapbox stays a normal system Param.
PROVIDER_FIELD = "NavSearchProvider"
AMAP_KEY_FIELD = "AmapWebKey"
BAIDU_KEY_FIELD = "BaiduWebAk"
MAPBOX_KEY_PARAM = "MapboxPublicKey"

PROVIDERS = ("auto", "amap", "baidu", "mapbox")

# carrot/server/features/nav_search.py -> carrot/amapnavi/nav_params.json
NAV_PARAMS_PATH = Path(__file__).resolve().parents[2] / "amapnavi" / "nav_params.json"
_NAV_PARAMS_CACHE: dict[str, Any] = {"mtime": None, "data": {}}
PROVIDER_LABELS = {"amap": "AMap", "baidu": "Baidu", "mapbox": "Mapbox"}

AMAP_URL = "https://restapi.amap.com/v3/assistant/inputtips"
BAIDU_URL = "https://api.map.baidu.com/place/v2/search"
MAPBOX_URL = "https://api.mapbox.com/search/geocode/v6/forward"

MAX_RESPONSE = 1024 * 1024
MAX_RESULTS = 6


class SearchError(Exception):
  """Upstream failure that should be reported as HTTP 502."""


# ─────────────────────────────────────────────
# Chinese datum -> WGS84
# ─────────────────────────────────────────────
_A = 6378245.0
_EE = 0.00669342162296594323
_X_PI = math.pi * 3000.0 / 180.0


def _out_of_china(lng: float, lat: float) -> bool:
  return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
  ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
  ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
  ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
  ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
  return ret


def _transform_lng(x: float, y: float) -> float:
  ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
  ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
  ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
  ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
  return ret


def wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
  if _out_of_china(lng, lat):
    return lng, lat
  dlat = _transform_lat(lng - 105.0, lat - 35.0)
  dlng = _transform_lng(lng - 105.0, lat - 35.0)
  radlat = lat / 180.0 * math.pi
  magic = 1 - _EE * math.sin(radlat) ** 2
  sqrtmagic = math.sqrt(magic)
  dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
  dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
  return lng + dlng, lat + dlat


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
  if _out_of_china(lng, lat):
    return lng, lat
  # Fixed-point inverse of wgs84_to_gcj02: converges to well under a metre.
  wlng, wlat = lng, lat
  for _ in range(3):
    glng, glat = wgs84_to_gcj02(wlng, wlat)
    wlng += lng - glng
    wlat += lat - glat
  return wlng, wlat


def bd09_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
  x, y = lng - 0.0065, lat - 0.006
  z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
  theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
  return z * math.cos(theta), z * math.sin(theta)


def bd09_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
  return gcj02_to_wgs84(*bd09_to_gcj02(lng, lat))


# ─────────────────────────────────────────────
# provider selection
# ─────────────────────────────────────────────
def unified_nav_params(path: Path | None = None) -> dict[str, Any]:
  """Current nav_params.json, reloaded only when the file changes.

  carrot_server runs in a different process from the 8088 config page, so the
  singleton UnifiedParams would never see edits; reading the file is the only
  way to stay in sync. A missing/unreadable file yields {}.
  """
  target = Path(path) if path is not None else NAV_PARAMS_PATH
  try:
    mtime = target.stat().st_mtime_ns
  except OSError:
    return {}
  if _NAV_PARAMS_CACHE["mtime"] != mtime:
    try:
      data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
      data = {}
    _NAV_PARAMS_CACHE["data"] = data if isinstance(data, dict) else {}
    _NAV_PARAMS_CACHE["mtime"] = mtime
  return _NAV_PARAMS_CACHE["data"]


def resolve_provider(stored: str, amap_key: str, baidu_key: str, mapbox_key: str) -> str | None:
  """Return the backend to use, or None when no usable key is configured.

  "auto" prefers a mainland service with a key and falls back to Mapbox, so an
  existing Mapbox-only setup keeps working without touching any setting.
  """
  name = (stored or "auto").strip().lower()
  keys = {"amap": amap_key, "baidu": baidu_key, "mapbox": mapbox_key}
  if name in keys:
    return name if keys[name] else None
  for candidate in ("amap", "baidu", "mapbox"):
    if keys[candidate]:
      return candidate
  return None


def missing_key_message(stored: str) -> str:
  name = (stored or "auto").strip().lower()
  if name in PROVIDER_LABELS:
    return f"Set the {PROVIDER_LABELS[name]} key on :8088/nav_params (导航搜索)."
  return "Set an AMap key, Baidu AK or Mapbox public key on :8088/nav_params (导航搜索)."





# ─────────────────────────────────────────────
# upstream requests
# ─────────────────────────────────────────────
async def _get_json(session: Any, url: str, params: dict[str, str]) -> dict[str, Any]:
  async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as response:
    if response.status != 200:
      raise SearchError(f"search service HTTP {response.status}")
    body = bytearray()
    async for chunk in response.content.iter_chunked(65536):
      body.extend(chunk)
      if len(body) > MAX_RESPONSE:
        raise SearchError("oversized response")
  try:
    parsed = json.loads(body)
  except ValueError as exc:
    raise SearchError("invalid response") from exc
  if not isinstance(parsed, dict):
    raise SearchError("invalid response")
  return parsed


def _place(lat: Any, lon: Any, label: str, query: str) -> dict[str, Any] | None:
  try:
    latitude, longitude = float(lat), float(lon)
  except (TypeError, ValueError):
    return None
  if not (math.isfinite(latitude) and math.isfinite(longitude)):
    return None
  if abs(latitude) > 85.05112878 or abs(longitude) > 180:
    return None
  return {"latitude": latitude, "longitude": longitude, "place_name": (label or query)[:256]}


def _join(*parts: str) -> str:
  return " · ".join(part.strip() for part in parts if str(part or "").strip())


def _parse_amap(body: dict[str, Any], query: str) -> list[dict[str, Any]]:
  if str(body.get("status")) != "1":
    raise SearchError(f"AMap search failed: {body.get('info') or 'unknown error'}")
  results = []
  for tip in body.get("tips") or []:
    if not isinstance(tip, dict):
      continue
    location = tip.get("location")
    if not isinstance(location, str) or "," not in location:
      continue  # bus lines and other non-POI tips have no coordinate
    try:
      lng, lat = (float(value) for value in location.split(",")[:2])
    except ValueError:
      continue
    lng, lat = gcj02_to_wgs84(lng, lat)
    place = _place(lat, lng, _join(tip.get("name", ""), tip.get("district", ""), tip.get("address", "")), query)
    if place:
      results.append(place)
    if len(results) >= MAX_RESULTS:
      break
  return results


def _parse_baidu(body: dict[str, Any], query: str) -> list[dict[str, Any]]:
  if body.get("status") != 0:
    raise SearchError(f"Baidu search failed: {body.get('message') or 'unknown error'}")
  results = []
  for item in body.get("results") or []:
    if not isinstance(item, dict):
      continue
    location = item.get("location") or {}
    if not isinstance(location, dict):
      continue
    lng, lat = bd09_to_wgs84(float(location.get("lng", 0)), float(location.get("lat", 0)))
    place = _place(lat, lng, _join(item.get("name", ""), item.get("city", ""), item.get("address", "")), query)
    if place:
      results.append(place)
    if len(results) >= MAX_RESULTS:
      break
  return results


def _parse_mapbox(body: dict[str, Any], query: str) -> list[dict[str, Any]]:
  results = []
  for feature in (body.get("features") or [])[:MAX_RESULTS]:
    try:
      lon, lat = feature["geometry"]["coordinates"][:2]
    except (KeyError, TypeError, IndexError):
      continue
    properties = feature.get("properties") or {}
    label = properties.get("full_address") or properties.get("name") or query
    place = _place(lat, lon, str(label), query)
    if place:
      results.append(place)
  return results


async def search(session: Any, provider: str, query: str, *, amap_key: str = "",
                 baidu_key: str = "", mapbox_key: str = "") -> list[dict[str, Any]]:
  """Return destinations as WGS84 lat/lon, whatever datum the provider used."""
  if provider == "amap":
    body = await _get_json(session, AMAP_URL, {
      "key": amap_key, "keywords": query, "city": "", "citylimit": "false", "datatype": "all",
    })
    return _parse_amap(body, query)
  if provider == "baidu":
    body = await _get_json(session, BAIDU_URL, {
      "query": query, "region": "全国", "region_limit": "false", "output": "json",
      "ak": baidu_key, "page_size": str(MAX_RESULTS), "scope": "2",
    })
    return _parse_baidu(body, query)
  if provider == "mapbox":
    body = await _get_json(session, MAPBOX_URL, {
      "q": query, "access_token": mapbox_key, "limit": str(MAX_RESULTS),
      "autocomplete": "false", "permanent": "true",
    })
    return _parse_mapbox(body, query)
  raise SearchError(f"unsupported provider: {provider}")


def forward_url(provider: str, query: str, key: str) -> str:
  """Readable URL for diagnostics; never returned to the browser."""
  if provider == "amap":
    return f"{AMAP_URL}?{urllib.parse.urlencode({'keywords': query})}"
  if provider == "baidu":
    return f"{BAIDU_URL}?{urllib.parse.urlencode({'query': query, 'region': '全国'})}"
  return MAPBOX_URL
