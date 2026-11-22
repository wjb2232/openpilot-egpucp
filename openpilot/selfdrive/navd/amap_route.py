"""AMap (高德) driving route backend, used only when navd resolves the AMap provider.

Mapbox Directions stays the default. AMap speaks GCJ-02 while navd, mapsd and
the destination search all work in WGS84, so the origin/destination are shifted
on the way out and every returned polyline point is shifted back on the way in.

The AMap response is rewritten into the Mapbox shape (routes/legs/steps) so
navd's instruction, banner and reroute code stays shared between providers.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# navd.py -> selfdrive -> carrot/amapnavi/nav_params.json (UnifiedParams file,
# written by the :8088/nav_params page; the key set there is shared with search).
PROVIDER_FIELD = 'NavRouteProvider'
AMAP_KEY_FIELD = 'AmapWebKey'
PROVIDERS = ('auto', 'mapbox', 'amap')

AMAP_URL = 'https://restapi.amap.com/v3/direction/driving'
MAX_WAYPOINTS = 16  # AMap's own limit for driving waypoints

NAV_PARAMS_PATH = Path(__file__).resolve().parents[1] / 'carrot' / 'amapnavi' / 'nav_params.json'
_CACHE: dict[str, Any] = {'mtime': None, 'data': {}}


# ─────────────────────────────────────────────
# settings
# ─────────────────────────────────────────────
def nav_params(path: Path | None = None) -> dict[str, Any]:
  """nav_params.json, re-read only when the file changes; {} when unavailable."""
  target = Path(path) if path is not None else NAV_PARAMS_PATH
  try:
    stat = target.stat()
    # mtime 在部分文件系统上粒度粗（连续两次写入可能同值），补上文件大小
    signature = (stat.st_mtime_ns, stat.st_size)
  except OSError:
    return {}
  if _CACHE['mtime'] != signature:
    try:
      data = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError):
      data = {}
    _CACHE['data'] = data if isinstance(data, dict) else {}
    _CACHE['mtime'] = signature
  return _CACHE['data']


def resolve_provider(stored: str, amap_key: str, mapbox_key: str) -> str | None:
  """'amap', 'mapbox', or None when the selected provider has no key.

  "auto" prefers AMap (better routes in mainland China) and falls back to
  Mapbox so a Mapbox-only setup keeps working without touching any setting.
  """
  name = (stored or 'auto').strip().lower()
  keys = {'amap': amap_key, 'mapbox': mapbox_key}
  if name in keys:
    return name if keys[name] else None
  for candidate in ('amap', 'mapbox'):
    if keys[candidate]:
      return candidate
  return None


def route_settings(mapbox_key: str, path: Path | None = None) -> tuple[str, str | None, str]:
  """(stored provider, resolved provider, AMap key) from nav_params.json."""
  data = nav_params(path)
  stored = str(data.get(PROVIDER_FIELD) or 'auto').strip().lower()
  amap_key = str(data.get(AMAP_KEY_FIELD) or '').strip()
  return stored, resolve_provider(stored, amap_key, mapbox_key), amap_key


# ─────────────────────────────────────────────
# WGS84 <-> GCJ-02
# ─────────────────────────────────────────────
_A = 6378245.0
_EE = 0.00669342162296594323


def out_of_china(lng: float, lat: float) -> bool:
  """AMap only covers mainland China; navd falls back to Mapbox outside this box."""
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
  if out_of_china(lng, lat):
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
  if out_of_china(lng, lat):
    return lng, lat
  # Fixed-point inverse of wgs84_to_gcj02: converges to well under a metre.
  wlng, wlat = lng, lat
  for _ in range(3):
    glng, glat = wgs84_to_gcj02(wlng, wlat)
    wlng += lng - glng
    wlat += lat - glat
  return wlng, wlat


# ─────────────────────────────────────────────
# request
# ─────────────────────────────────────────────
def _coordinate(pair) -> str:
  """A WGS84 (longitude, latitude) pair as AMap's GCJ-02 "lng,lat" text."""
  lng, lat = wgs84_to_gcj02(float(pair[0]), float(pair[1]))
  return f'{lng:.6f},{lat:.6f}'


# 路线候选策略：v3 strategy=11 一次请求固定返回三条路径（时间最短/距离最短/躲避拥堵），
# paths 顺序与 ROUTE_LABELS 一一对应；网页候选卡片与 navd 重规划共用同一 strategy，
# 同参数短时间重请求的路径是确定的，保证「点哪条走哪条」。
ROUTE_STRATEGY = '11'
ROUTE_LABELS = ('最快', '最短', '躲避拥堵')

# 网页「路线偏好」：偏好名 -> (高德高级策略号, 卡片展示名)。这些策略通常只回
# 单条路线，候选接口按原样透传 strategy，navd 重规划同参数取同一条路。
ROUTE_PREFS = {
    'avoid_highway': ('14', '不走高速'),
    'less_toll': ('15', '少收费'),
    'prefer_big_road': ('16', '大路优先'),
    'prefer_highway': ('18', '高速优先'),
}


def request_params(points: list[tuple[float, float]], key: str, strategy: str = '0') -> dict[str, str]:
  """AMap driving query for WGS84 (longitude, latitude) origin/waypoints/destination."""
  if len(points) < 2:
    raise ValueError('a route needs an origin and a destination')
  params = {
    'key': key,
    'origin': _coordinate(points[0]),
    'destination': _coordinate(points[-1]),
    # 0 = 速度优先: closest to Mapbox's driving-traffic default.
    # 11 = 一次返回三条候选（最快/最短/躲避拥堵），候选卡片用。
    'strategy': strategy,
    'extensions': 'base',
    'output': 'json',
  }
  middle = points[1:-1][:MAX_WAYPOINTS]
  if middle:
    params['waypoints'] = ';'.join(_coordinate(point) for point in middle)
  return params


# ─────────────────────────────────────────────
# response
# ─────────────────────────────────────────────
def _side(text: str, default: str) -> str:
  if '左' in text:
    return 'left'
  if '右' in text:
    return 'right'
  return default


def maneuver(action: str, assistant: str = '') -> tuple[str, str]:
  """AMap action/assistant_action -> the (type, modifier) pair carrot's icon table uses."""
  text = f'{action}{assistant}'
  if '到达' in text or '终点' in text:
    return 'arrive', 'straight'
  if '环岛' in text or '环道' in text:
    return 'rotary', _side(text, 'straight')
  if any(word in text for word in ('匝道', '主路', '辅路', '高速')):
    if any(word in text for word in ('驶出', '下高速', '出口', '离开')):
      return 'off ramp', _side(text, 'right')
    return 'on ramp', _side(text, 'left')
  if '靠左' in text or '靠右' in text:
    return 'fork', _side(text, 'left')
  if '调头' in text:
    return 'turn', 'uturn'
  if '左前方' in text:
    return 'turn', 'slight left'
  if '右前方' in text:
    return 'turn', 'slight right'
  if '左后方' in text:
    return 'turn', 'sharp left'
  if '右后方' in text:
    return 'turn', 'sharp right'
  if '左' in text:
    return 'turn', 'left'
  if '右' in text:
    return 'turn', 'right'
  return 'turn', 'straight'


def _number(value: Any) -> float | None:
  try:
    number = float(value)
  except (TypeError, ValueError):
    return None
  return number if math.isfinite(number) and number >= 0 else None


def _polyline(text: str) -> list[list[float]]:
  """AMap "lng,lat;lng,lat" (GCJ-02) -> WGS84 [longitude, latitude] pairs."""
  points: list[list[float]] = []
  for part in str(text or '').split(';'):
    if ',' not in part:
      continue
    try:
      lng, lat = (float(value) for value in part.split(',')[:2])
    except ValueError:
      continue
    if not (math.isfinite(lng) and math.isfinite(lat)) or abs(lat) > 85.05112878 or abs(lng) > 180:
      continue
    lng, lat = gcj02_to_wgs84(lng, lat)
    points.append([lng, lat])
  return points


def parse(body: Any, path_index: int = 0) -> dict[str, Any] | None:
  """AMap driving response -> Mapbox-shaped {'routes': [{'legs': [{'steps': [...]}]}]}.

  path_index selects one of the alternative paths returned by multi-result
  strategies (e.g. strategy=11); it falls back to paths[0] when out of range.
  """
  if not isinstance(body, dict) or str(body.get('status', '0')) != '1':
    return None
  route = body.get('route')
  if not isinstance(route, dict):
    return None
  paths = route.get('paths')
  if not isinstance(paths, list) or not paths or not isinstance(paths[0], dict):
    return None
  selected = paths[path_index] if 0 < path_index < len(paths) and isinstance(paths[path_index], dict) else paths[0]

  steps: list[dict[str, Any]] = []
  for raw in selected.get('steps') or []:
    if not isinstance(raw, dict):
      continue
    points = _polyline(raw.get('polyline', ''))
    distance, duration = _number(raw.get('distance')), _number(raw.get('duration'))
    if len(points) < 2 or distance is None or duration is None:
      continue
    action = str(raw.get('action') or '')
    assistant = str(raw.get('assistant_action') or '')
    maneuver_type, modifier = maneuver(action, assistant)
    road = str(raw.get('road') or '')
    steps.append({
      'distance': distance,
      'duration': duration,
      'duration_typical': None,
      # AMap has no per-segment maxspeed, so navd keeps the previous speed limit.
      'geometry': {'coordinates': points},
      'bannerInstructions': [{
        'distanceAlongGeometry': distance,
        'primary': {'text': str(raw.get('instruction') or action), 'type': maneuver_type, 'modifier': modifier},
        'secondary': {'text': road} if road else None,
      }],
    })
  if not steps:
    return None
  return {'routes': [{'legs': [{'steps': steps}]}]}
