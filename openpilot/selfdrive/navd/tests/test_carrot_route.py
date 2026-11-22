"""carrot_route.install() 的分派行为：upstream navd.py 本身不需要改动逻辑。"""
import json
import time
from types import SimpleNamespace

import pytest

from openpilot.selfdrive.navd import amap_route, carrot_route

AMAP_BODY = {
  'status': '1',
  'route': {'paths': [{'steps': [
    {'polyline': '116.397128,39.916527;116.407128,39.926527',
     'distance': '100', 'duration': '10', 'instruction': '左转进入建国路',
     'action': '左转', 'road': '建国路'},
  ]}]},
}
BEIJING = SimpleNamespace(longitude=116.397128, latitude=39.916527)
NEARBY = SimpleNamespace(longitude=116.407128, latitude=39.926527)
ABROAD = SimpleNamespace(longitude=-117.125565, latitude=32.711601)


class FakeParams:
  def __init__(self, **values):
    self.values = values

  def get(self, key):
    return self.values.get(key, '')


class FakeExecutor:
  def __init__(self):
    self.calls = []

  def submit(self, fn, *args):
    self.calls.append((fn, args))
    return object()


class FakeEngine:
  """只实现 upstream RouteEngine 被包装方法用到的接口。"""
  request_route = staticmethod(lambda url, params: AMAP_BODY)

  def __init__(self, mapbox_key=''):
    self.params = FakeParams(MapboxPublicKey=mapbox_key, NavDestinationWaypoints='')
    self.mapbox_token = ''
    self.mapbox_host = 'https://api.mapbox.com'
    self.last_position = BEIJING
    self.nav_destination = None
    self.pending = None
    self.pending_waypoints = None
    self.pending_destination = None
    self.pending_token = None
    self.executor = FakeExecutor()
    self.calls = []
    self.cleared = 0

  def refresh_token(self):
    self.calls.append('refresh_token')

  def recompute_route(self):
    self.calls.append('recompute_route')

  def calculate_route(self, destination):
    self.calls.append(('upstream_calculate_route', destination))

  def clear_route(self):
    self.cleared += 1

  def reset_recompute_limits(self):
    pass


@pytest.fixture
def hooked(monkeypatch):
  """每个用例用一份新的类，避免 install 的幂等标记互相影响。"""
  cls = type('HookedEngine', (FakeEngine,), {})
  carrot_route.install(cls)
  return cls


def set_provider(monkeypatch, provider, amap_key='key.test'):
  monkeypatch.setattr(amap_route, 'route_settings',
                      lambda token: ('auto', provider, amap_key))


def test_install_is_idempotent(hooked):
  assert hooked._carrot_route_installed
  refresh = hooked.refresh_token
  carrot_route.install(hooked)
  assert hooked.refresh_token is refresh


def test_mapbox_provider_keeps_upstream_behaviour(hooked, monkeypatch):
  set_provider(monkeypatch, 'mapbox')
  engine = hooked(mapbox_key='pk.test')
  engine.refresh_token()
  engine.calculate_route(NEARBY)
  assert engine.mapbox_token == 'pk.test'
  assert engine.calls[-1] == ('upstream_calculate_route', NEARBY)
  assert engine.executor.calls == []


def test_amap_request_is_rewritten_before_poll_route(hooked, monkeypatch):
  set_provider(monkeypatch, 'amap')
  engine = hooked()
  engine.refresh_token()
  # 只配高德 key 时也要能通过 upstream 的 "mapbox_token 非空" 闸门
  assert engine.mapbox_token == carrot_route._AMAP_TOKEN_PLACEHOLDER
  engine.calculate_route(NEARBY)
  fn, (url, params, path_index) = engine.executor.calls[0]
  assert url == amap_route.AMAP_URL and params['key'] == 'key.test'
  assert path_index == 0
  assert engine.pending_token == engine.mapbox_token
  response = fn(url, params)
  assert response['routes'][0]['legs'][0]['steps'][0]['bannerInstructions'][0]['primary']['modifier'] == 'left'
  assert all(len(p) == 2 for p in response['routes'][0]['legs'][0]['steps'][0]['geometry']['coordinates'])


def test_amap_min_interval_blocks_recompute(hooked, monkeypatch):
  set_provider(monkeypatch, 'amap')
  engine = hooked()
  engine.refresh_token()
  engine._carrot_next_route_at = time.monotonic() + 60
  engine.recompute_route()
  assert engine.calls == ['refresh_token']
  engine._carrot_next_route_at = 0.
  engine.recompute_route()
  assert engine.calls[-1] == 'recompute_route'


def test_out_of_china_falls_back_to_mapbox(hooked, monkeypatch):
  set_provider(monkeypatch, 'amap')
  engine = hooked(mapbox_key='pk.test')
  engine.refresh_token()
  engine.calculate_route(ABROAD)
  assert engine.calls[-1] == ('upstream_calculate_route', ABROAD)
  assert engine.executor.calls == []


def test_out_of_china_without_mapbox_key_skips(hooked, monkeypatch):
  set_provider(monkeypatch, 'amap')
  engine = hooked()
  engine.refresh_token()
  engine.calculate_route(ABROAD)
  assert engine.executor.calls == []
  assert ('upstream_calculate_route', ABROAD) not in engine.calls


def test_invalid_waypoints_are_rejected(hooked, monkeypatch):
  set_provider(monkeypatch, 'amap')
  engine = hooked()
  engine.params.values['NavDestinationWaypoints'] = '[[999, 2]]'
  engine.refresh_token()
  engine.calculate_route(NEARBY)
  assert engine.executor.calls == []


def test_destination_prefs_read_selected_route(hooked):
  engine = hooked()
  prefs = {'latitude': 39.926527, 'longitude': 116.407128, 'strategy': 11, 'route_index': 2}
  engine.params_memory = FakeParams(NavDestinationTemporary=json.dumps(prefs))
  assert carrot_route._destination_prefs(engine, NEARBY) == (11, 2)
  # 经纬度不匹配（参数刷新竞态）与坏 JSON 都回退默认速度优先
  assert carrot_route._destination_prefs(engine, BEIJING) == (0, 0)
  engine.params_memory = FakeParams(NavDestinationTemporary='not json')
  assert carrot_route._destination_prefs(engine, NEARBY) == (0, 0)


def test_calculate_route_passes_strategy_and_path_index(hooked, monkeypatch):
  set_provider(monkeypatch, 'amap')
  engine = hooked()
  engine.refresh_token()
  prefs = {'latitude': 39.926527, 'longitude': 116.407128, 'strategy': 11, 'route_index': 2}
  engine.params_memory = FakeParams(NavDestinationTemporary=json.dumps(prefs))
  engine.calculate_route(NEARBY)
  fn, args = engine.executor.calls[0]
  url, params, path_index = args
  assert url == amap_route.AMAP_URL
  assert params['strategy'] == '11' and path_index == 2
