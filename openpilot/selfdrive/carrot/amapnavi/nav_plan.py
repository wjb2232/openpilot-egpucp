"""Route preview for the amapnavi Web page (served by :8088, no carrot_server).

The page can preview a route without a GPS fix: the origin is either the live
``LastGPSPosition`` or a place the user searched. Requests are made from this
process with urllib, so ``carrot_server`` and ``navd`` stay untouched.

AMap is preferred (it already has the Web service key used by the search page);
Mapbox is the fallback. Both return WGS84 points, which is what the browser
canvas draws.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from openpilot.selfdrive.navd import amap_route

AMAP_DRIVING_URL = amap_route.AMAP_URL
MAPBOX_DRIVING_URL = 'https://api.mapbox.com/directions/v5/mapbox/driving-traffic/'
MAX_RESPONSE = 4 * 1024 * 1024
PREVIEW_POINTS = 512  # the canvas does not need more than this
MAX_LATITUDE = 85.05112878

# Static basemap for the Web preview: one AMap request draws the roads, the
# route line and the start/end markers, and auto-fits the whole polyline.
STATIC_MAP_URL = 'https://restapi.amap.com/v3/staticmap'
STATIC_MAP_CACHE_DIR = '/data/carrot/state/nav_preview'
STATIC_MAP_MAX_POINTS = 60
STATIC_MAP_MAX_BYTES = 2 * 1024 * 1024
# 预览页 .frame 是正方形；高德 / Mapbox / OSM 离线三种底图统一这个尺寸，
# 否则 object-fit: contain 会在上下留黑边、路线比例看起来不对。
STATIC_MAP_SIZE = '720*720'


class PlanError(Exception):
  """A route that cannot be planned; the message is shown on the page."""


def parse_point(text: Any) -> tuple[float, float] | None:
  """'lat,lon' as used in the page URL -> (longitude, latitude), or None."""
  try:
    latitude, longitude = (float(value) for value in str(text).split(',')[:2])
  except (TypeError, ValueError):
    return None
  if not (math.isfinite(latitude) and math.isfinite(longitude)):
    return None
  if abs(latitude) > MAX_LATITUDE or abs(longitude) > 180:
    return None
  return longitude, latitude


def live_position(params) -> tuple[float, float] | None:
  """Current (longitude, latitude) from /dev/shm/params, or None without a fix."""
  try:
    value = params.get('LastGPSPosition')
  except Exception:
    return None
  if not value:
    return None
  try:
    data = json.loads(value)
    latitude, longitude = float(data['latitude']), float(data['longitude'])
  except (ValueError, TypeError, KeyError):
    return None
  if not (math.isfinite(latitude) and math.isfinite(longitude)):
    return None
  return longitude, latitude


def _get_json(url: str, timeout: float) -> dict[str, Any]:
  request = urllib.request.Request(url, method='GET')
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      body = response.read(MAX_RESPONSE + 1)
  except urllib.error.HTTPError as error:
    raise PlanError(f'服务返回 HTTP {error.code}') from None
  except OSError:
    raise PlanError('路线服务不可达（检查网络）') from None
  if len(body) > MAX_RESPONSE:
    raise PlanError('路线服务返回内容过大')
  try:
    parsed = json.loads(body)
  except ValueError:
    raise PlanError('路线服务返回格式错误') from None
  if not isinstance(parsed, dict):
    raise PlanError('路线服务返回格式错误')
  return parsed


def _payload(provider: str, coordinates, distance: float, duration: float, steps: int) -> dict[str, Any]:
  points = [(float(point[0]), float(point[1])) for point in coordinates]
  # ceil so the result never exceeds PREVIEW_POINTS; keep at least one point
  points = points[::max(1, -(-len(points) // PREVIEW_POINTS))]
  return {'provider': provider, 'steps': int(steps), 'distance': float(distance), 'duration': float(duration),
          'points': [[round(lon, 6), round(lat, 6)] for lon, lat in points]}


def _amap(origin, destination, key: str, timeout: float) -> dict[str, Any]:
  query = amap_route.request_params([origin, destination], key)
  body = _get_json(AMAP_DRIVING_URL + '?' + urllib.parse.urlencode(query), timeout)
  route = amap_route.parse(body)
  if route is None:
    raise PlanError(str(body.get('info') or '高德没有规划出这条路线'))
  steps = route['routes'][0]['legs'][0]['steps']
  coordinates = [point for step in steps for point in step['geometry']['coordinates']]
  return _payload('amap', coordinates,
                  sum(step['distance'] for step in steps), sum(step['duration'] for step in steps), len(steps))


def _mapbox(origin, destination, token: str, timeout: float) -> dict[str, Any]:
  coordinates = ';'.join(f'{lon},{lat}' for lon, lat in (origin, destination))
  query = urllib.parse.urlencode({'geometries': 'geojson', 'overview': 'full', 'steps': 'true',
                                  'access_token': token})
  body = _get_json(MAPBOX_DRIVING_URL + coordinates + '?' + query, timeout)
  routes = body.get('routes') or []
  if not routes:
    raise PlanError('Mapbox 没有规划出这条路线（检查 key 和网络）')
  route = routes[0]
  legs = route.get('legs') or [{}]
  return _payload('mapbox', route['geometry']['coordinates'],
                  float(route['distance']), float(route['duration']), len(legs[0].get('steps') or []))


def static_map_params(points, key: str) -> dict[str, str]:
  """WGS84 (lon, lat) points -> AMap static map query with the route and markers.

  AMap tiles are GCJ-02, so the polyline is shifted before it reaches the API.
  center/zoom are deliberately omitted: AMap auto-fits the whole route.
  """
  coordinates = [(float(point[0]), float(point[1])) for point in points]
  if len(coordinates) < 2:
    raise PlanError('路线点太少，无法生成地图')
  sampled = coordinates[::max(1, len(coordinates) // 45)]
  shifted = [amap_route.wgs84_to_gcj02(lon, lat) for lon, lat in sampled]
  line = ';'.join(f'{lon:.6f},{lat:.6f}' for lon, lat in shifted)
  start, end = shifted[0], shifted[-1]
  return {
    'size': STATIC_MAP_SIZE,
    'scale': '1',
    'key': key,
    # 高德静态图 paths 的样式字段是逗号分隔：weight,color,alpha,fillcolor,fillalpha
    'paths': f'6,0x1a73e8,1,,:{line}',
    'markers': (f'mid,0x00c853,S:{start[0]:.6f},{start[1]:.6f}'
                f'|mid,0xff5252,E:{end[0]:.6f},{end[1]:.6f}'),
  }


def static_map_png(points, key: str, cache_dir: str = STATIC_MAP_CACHE_DIR, timeout: float = 15.) -> bytes:
  """Download and cache the basemap PNG; the same route never costs a second request."""
  query = static_map_params(points, key)
  digest_source = urllib.parse.urlencode({name: value for name, value in query.items() if name != 'key'})
  digest = hashlib.sha256(digest_source.encode('ascii')).hexdigest()[:32]
  try:
    with open(os.path.join(cache_dir, digest + '.png'), 'rb') as cached:
      return cached.read()
  except OSError:
    pass

  url = STATIC_MAP_URL + '?' + urllib.parse.urlencode(query)
  try:
    with urllib.request.urlopen(urllib.request.Request(url, method='GET'), timeout=timeout) as response:
      body = response.read(STATIC_MAP_MAX_BYTES + 1)
  except (OSError, urllib.error.HTTPError):
    raise PlanError('底图服务不可达（检查网络）') from None
  if len(body) > STATIC_MAP_MAX_BYTES or not body.startswith(b'\x89PNG'):
    raise PlanError('底图服务没有返回图片（检查高德 Key 与配额）')

  try:
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir, digest + '.png')
    temporary = cached + '.tmp'
    with open(temporary, 'wb') as handle:
      handle.write(body)
    os.replace(temporary, cached)
  except OSError:  # 缓存写不了也要能显示
    pass
  return body


def plan(origin, destination, *, amap_key: str = '', mapbox_key: str = '', timeout: float = 8.) -> dict[str, Any]:
  """A preview route between two WGS84 (longitude, latitude) points."""
  if origin is None or destination is None:
    raise PlanError('缺少起点或终点')
  errors = []
  if amap_key:
    try:
      return _amap(origin, destination, amap_key, timeout)
    except PlanError as error:
      errors.append(f'高德：{error}')
  if mapbox_key:
    try:
      return _mapbox(origin, destination, mapbox_key, timeout)
    except PlanError as error:
      errors.append(f'Mapbox：{error}')
  if not errors:
    raise PlanError('没有可用的路线服务，请先在参数页填写高德 Web 服务 Key 或 Mapbox key')
  raise PlanError('；'.join(errors))
