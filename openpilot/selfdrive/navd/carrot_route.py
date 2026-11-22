#!/usr/bin/env python3
"""carrot: 高德路线接入 navd 的唯一实现文件。

upstream 的 ``selfdrive/navd/navd.py`` 只保留两行接入点（import + install），
provider 选择、坐标系换算、限流、响应改写全在这里和 ``amap_route.py``。
合并 upstream 新提交时，navd.py 的业务逻辑不会产生冲突。

``install(RouteEngine)`` 只包装三个方法：

* ``refresh_token``   读 nav_params.json 的 NavRouteProvider / AmapWebKey；
* ``recompute_route`` 高德的最小请求间隔闸门；
* ``calculate_route`` 高德分支（境外回退 Mapbox）。

高德响应在线程池里就被改写成 Mapbox 形状，所以 upstream 的 ``poll_route``
``send_instruction`` 等完全不用改，Mapbox 用户的行为也完全不变。
"""
from __future__ import annotations

import json
import math
import os
import time

from openpilot.selfdrive.navd import amap_route

# 高德 Web 服务按次计费，即使偏航重算也不要比这更密。
AMAP_MIN_INTERVAL = 10.
MAPBOX_MAX_WAYPOINTS = 23
# upstream 用 self.mapbox_token 是否非空作为「能不能算路线」的闸门；只配了
# 高德 key 时给它一个占位值，真正的高德请求不会用到这个 token。
_AMAP_TOKEN_PLACEHOLDER = 'amap'


def _warn(message):
  try:
    from openpilot.common.swaglog import cloudlog
    cloudlog.warning(message)
  except Exception:
    pass


def _mapbox_token(engine):
  token = os.environ.get('MAPBOX_TOKEN') or engine.params.get('MapboxPublicKey') or ''
  return token.decode('utf-8') if isinstance(token, bytes) else token


def _middle_points(raw):
  """NavDestinationWaypoints -> (lon, lat) 列表；非法时返回 None。"""
  try:
    middle = json.loads(raw) if raw else []
    if (len(middle) > MAPBOX_MAX_WAYPOINTS or
        any(len(p) != 2 or not all(math.isfinite(v) for v in p)
            or abs(p[0]) > 180 or abs(p[1]) > 85.05112878 for p in middle)):
      return None
  except (ValueError, TypeError):
    return None
  return middle


def _destination_prefs(engine, destination):
  """NavDestinationTemporary 里的 strategy/route_index（网页候选卡片写入）。

  经纬度与当前目的地比对防串号（目的地下发晚于参数刷新的瞬间），不匹配
  或旧格式回 (0, 0) = upstream 默认的速度优先。
  """
  try:
    raw = json.loads(engine.params_memory.get('NavDestinationTemporary') or b'')
    if (abs(float(raw['latitude']) - destination.latitude) < 1e-6 and
        abs(float(raw['longitude']) - destination.longitude) < 1e-6):
      return int(raw.get('strategy', 0)), int(raw.get('route_index', 0))
  except (OSError, ValueError, TypeError, KeyError, AttributeError):
    pass
  return 0, 0


def install(engine_cls):
  """把高德 provider 装到 upstream 的 RouteEngine；重复调用无副作用。"""
  if getattr(engine_cls, '_carrot_route_installed', False):
    return engine_cls

  refresh_token = engine_cls.refresh_token
  recompute_route = engine_cls.recompute_route
  calculate_route = engine_cls.calculate_route
  request_route = engine_cls.request_route  # @staticmethod 取出后是普通函数

  def amap_request(url, params, path_index=0):
    parsed = amap_route.parse(request_route(url, params), path_index)
    if parsed is None:
      _warn('navd: AMap returned no usable route')
    return parsed

  def patched_refresh_token(self):
    token = _mapbox_token(self)
    # 复位上一轮可能写入的占位符，否则 upstream 会误以为 Mapbox key 变了。
    self.mapbox_token = token
    refresh_token(self)
    stored, provider, amap_key = amap_route.route_settings(token)
    settings = (stored, provider, amap_key, token)
    if settings != getattr(self, '_carrot_route_settings', None):
      self._carrot_route_settings = settings
      self._carrot_provider = provider
      self._carrot_amap_key = amap_key
      self._carrot_real_token = token
      self._carrot_next_route_at = 0.
      self.clear_route()
      self.reset_recompute_limits()
    if provider == 'amap' and not token:
      self.mapbox_token = _AMAP_TOKEN_PLACEHOLDER

  def patched_recompute_route(self):
    if (getattr(self, '_carrot_provider', None) == 'amap'
        and time.monotonic() < getattr(self, '_carrot_next_route_at', 0.)):
      return
    return recompute_route(self)

  def patched_calculate_route(self, destination):
    if getattr(self, '_carrot_provider', None) != 'amap':
      return calculate_route(self, destination)
    if self.pending is not None or self.last_position is None:
      return
    if destination != self.nav_destination:
      self.clear_route()
    raw_waypoints = self.params.get('NavDestinationWaypoints') or ''
    middle = _middle_points(raw_waypoints)
    if middle is None:
      return
    points = [(self.last_position.longitude, self.last_position.latitude), *middle,
              (destination.longitude, destination.latitude)]
    if any(amap_route.out_of_china(*point) for point in (points[0], points[-1])):
      # 高德只覆盖中国大陆，境外仍用 Mapbox（需要真实的 Mapbox key）。
      if not getattr(self, '_carrot_real_token', ''):
        return
      return calculate_route(self, destination)
    self.pending_waypoints = raw_waypoints
    self.pending_destination = destination
    self.pending_token = self.mapbox_token
    self._carrot_next_route_at = time.monotonic() + AMAP_MIN_INTERVAL
    strategy, route_index = _destination_prefs(self, destination)
    self.pending = self.executor.submit(amap_request, amap_route.AMAP_URL,
                                        amap_route.request_params(points, self._carrot_amap_key, strategy=str(strategy)),
                                        route_index)

  engine_cls.refresh_token = patched_refresh_token
  engine_cls.recompute_route = patched_recompute_route
  engine_cls.calculate_route = patched_calculate_route
  engine_cls._carrot_route_installed = True
  return engine_cls
