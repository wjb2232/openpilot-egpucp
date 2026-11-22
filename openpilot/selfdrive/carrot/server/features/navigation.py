"""Destination search/destination UI and the shared nav-model preview.

Search is delegated to ``nav_search`` so the backend can be Mapbox, AMap or
Baidu; every result is WGS84 regardless of the provider's native datum.

The provider and the AMap/Baidu keys live in UnifiedParams
(amapnavi/nav_params.json) so they are edited on the existing
``http://<device>:8088/nav_params`` page. Mapbox keeps using MapboxPublicKey.
"""
import asyncio
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
import time

from aiohttp import web

from openpilot.common.params import Params
from openpilot.selfdrive.navd import amap_route
from openpilot.selfdrive.carrot.amapnavi import nav_plan
from ..config import WEB_DIR
from ..services.params import get_param_value, set_param_value
from openpilot.selfdrive.navigation.preview import PREVIEW_PATH, WEB_DEMAND_PATH, preview_fresh, preview_reason
from . import nav_search

NO_STORE = {'Cache-Control': 'no-store'}


@dataclass
class SearchState:
  lock: asyncio.Lock = field(default_factory=asyncio.Lock)
  next_request: float = 0.


SEARCH_STATE = web.AppKey('navigation_search', SearchState)


def destination(value):
  if not isinstance(value, dict):
    raise ValueError('invalid destination')
  lat, lon = float(value['latitude']), float(value['longitude'])
  if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 85.05112878 or abs(lon) > 180:
    raise ValueError('invalid coordinates')
  result = {'latitude': lat, 'longitude': lon, 'place_name': str(value.get('place_name', 'Destination'))[:256]}
  # carrot: 网页候选卡片选中的路线（高德 strategy + paths 下标），navd 重规划时使用；
  # 缺省/非法时不写入这两个键，旧目的地格式保持兼容。
  try:
    result['strategy'] = min(20, max(0, int(value.get('strategy', 0))))
    result['route_index'] = min(len(amap_route.ROUTE_LABELS) - 1, max(0, int(value.get('route_index', 0))))
  except (TypeError, ValueError):
    pass
  return result


def _search_settings():
  """(stored provider, amap key, baidu key, mapbox key) from nav_params.json."""
  data = nav_search.unified_nav_params()
  return (
    str(data.get(nav_search.PROVIDER_FIELD) or 'auto'),
    str(data.get(nav_search.AMAP_KEY_FIELD) or '').strip(),
    str(data.get(nav_search.BAIDU_KEY_FIELD) or '').strip(),
    str(get_param_value(nav_search.MAPBOX_KEY_PARAM, '') or '').strip(),
  )


def _effective_provider():
  stored, amap_key, baidu_key, mapbox_key = _search_settings()
  return stored, nav_search.resolve_provider(stored, amap_key, baidu_key, mapbox_key)


async def page(request):
  return web.FileResponse(str(Path(WEB_DIR) / 'navigation.html'), headers={'Cache-Control': 'no-cache'})


async def search(request):
  query = request.query.get('q', '').strip()
  if not 2 <= len(query) <= 200:
    return web.json_response({'error': 'Enter 2–200 characters.'}, status=400, headers=NO_STORE)
  stored, provider = _effective_provider()
  if provider is None:
    return web.json_response({'error': nav_search.missing_key_message(stored)}, status=409, headers=NO_STORE)
  state = request.app[SEARCH_STATE]
  if state.lock.locked() or time.monotonic() < state.next_request:
    return web.json_response({'error': 'Please wait before searching again.'}, status=429, headers=NO_STORE)
  async with state.lock:
    state.next_request = time.monotonic() + 1.
    _, amap_key, baidu_key, mapbox_key = _search_settings()
    try:
      results = await nav_search.search(request.app['http'], provider, query,
                                        amap_key=amap_key, baidu_key=baidu_key, mapbox_key=mapbox_key)
      return web.json_response({'results': results, 'provider': provider}, headers=NO_STORE)
    except nav_search.SearchError as exc:
      return web.json_response({'error': str(exc)}, status=502, headers=NO_STORE)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
      return web.json_response({'error': 'Search is unavailable.'}, status=502, headers=NO_STORE)


async def get_destination(request):
  try:
    value = Params('/dev/shm/params').get('NavDestinationTemporary') or get_param_value('NavDestination', '')
    current = destination(json.loads(value)) if value else None
  except (ValueError, KeyError, TypeError):
    current = None
  _, provider = _effective_provider()
  return web.json_response({'destination': current, 'map_ready': preview_fresh() and preview_reason() == 'ready',
                            'key_configured': provider is not None, 'search_provider': provider or ''},
                           headers=NO_STORE)


async def set_destination(request):
  try:
    value = destination(await request.json())
  except (ValueError, KeyError, TypeError):
    return web.json_response({'error': 'Invalid destination.'}, status=400)
  # Keep the active destination in RAM. Manager clears it when the drive ends.
  set_param_value('NavDestination', '')
  set_param_value('NavDestinationWaypoints', '')
  Params('/dev/shm/params').put('NavDestinationTemporary', json.dumps(value, ensure_ascii=False))
  return web.json_response({'destination': value}, headers=NO_STORE)


async def clear_destination(request):
  set_param_value('NavDestination', '')
  Params('/dev/shm/params').remove('NavDestinationTemporary')
  set_param_value('NavDestinationWaypoints', '')
  return web.json_response({'destination': None})


async def candidates(request):
  """Alternative routes for the selection cards; origin defaults to the live fix."""
  destination_point = nav_plan.parse_point(request.query.get('destination'))
  if destination_point is None:
    return web.json_response({'error': 'destination 需要 lat,lon 格式'}, status=400, headers=NO_STORE)
  origin = nav_plan.parse_point(request.query.get('origin'))
  if origin is None:
    origin = nav_plan.live_position(Params('/dev/shm/params'))
  if origin is None:
    return web.json_response({'error': '暂时没有定位，稍后再试'}, status=400, headers=NO_STORE)
  _, amap_key, _, _ = _search_settings()
  try:
    result = await asyncio.get_running_loop().run_in_executor(
      None, lambda: nav_plan.candidates(origin, destination_point, amap_key=amap_key))
  except nav_plan.PlanError as exc:
    return web.json_response({'error': str(exc)}, status=502, headers=NO_STORE)
  except (ValueError, KeyError, TypeError, IndexError, AttributeError):
    return web.json_response({'error': '候选路线不可用.'}, status=502, headers=NO_STORE)
  return web.json_response({'candidates': result}, headers=NO_STORE)


async def preview(request):
  try:
    WEB_DEMAND_PATH.touch()
  except OSError:
    pass
  if not preview_fresh():
    reason = 'waiting' if get_param_value('IsOnroad', False) else 'offroad'
    return web.Response(status=204, headers={'Cache-Control': 'no-store', 'X-Nav-Map-Status': reason})
  return web.FileResponse(PREVIEW_PATH, headers={'Cache-Control': 'no-store', 'X-Nav-Map-Status': preview_reason()})


def register(app):
  app[SEARCH_STATE] = SearchState()
  app.router.add_get('/navigation', page)
  app.router.add_get('/api/navigation/search', search)
  app.router.add_get('/api/navigation/destination', get_destination)
  app.router.add_post('/api/navigation/destination', set_destination)
  app.router.add_delete('/api/navigation/destination', clear_destination)
  app.router.add_get('/api/navigation/candidates', candidates)
  app.router.add_get('/api/navigation/map.png', preview)
