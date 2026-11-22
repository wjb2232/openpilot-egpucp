import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace as NS

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from openpilot.selfdrive.carrot.server.features import navigation


@pytest.fixture(autouse=True)
def temporary_params(monkeypatch):
  values = {}
  def params(path):
    assert path == '/dev/shm/params'
    return NS(get=values.get, put=values.__setitem__, remove=lambda key: values.pop(key, None))
  monkeypatch.setattr(navigation, 'Params', params)
  return values


def test_destination_lifecycle_and_validation(monkeypatch, temporary_params):
  values = {}
  # 隔离 nav_params.json：车机上配了真实高德 key，不隔离会让 409 分支走成 502
  monkeypatch.setattr(navigation.nav_search, 'unified_nav_params', lambda: {})
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: values.get(key, default))
  monkeypatch.setattr(navigation, 'set_param_value', lambda key, value: values.__setitem__(key, value))

  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.post('/api/navigation/destination', json={'latitude': 37., 'longitude': 127., 'place_name': '<script>name</script>'})
      assert response.status == 200
      assert json.loads(temporary_params['NavDestinationTemporary'])['place_name'] == '<script>name</script>'
      assert 'NavDestinationTemporary' not in values
      assert response.headers['Cache-Control'] == 'no-store'
      assert values['NavDestination'] == ''
      response = await client.get('/api/navigation/destination')
      assert response.headers['Cache-Control'] == 'no-store'
      assert (await response.json())['destination']['latitude'] == 37.
      for payload in ([], {}, {'latitude': 91, 'longitude': 127}, {'latitude': None, 'longitude': 0}):
        assert (await client.post('/api/navigation/destination', json=payload)).status == 400
      assert (await client.get('/api/navigation/search?q=Seoul')).status == 409
      assert (await client.delete('/api/navigation/destination')).status == 200
      assert values['NavDestination'] == ''
      assert not temporary_params
  asyncio.run(run())


def test_navigation_page_is_served():
  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.get('/navigation')
      assert response.status == 200
      assert 'navigation_map.js' in await response.text()
  asyncio.run(run())


@pytest.mark.parametrize('fresh,reason,ready', [
  (True, 'route', False), (True, 'position', False), (True, 'ready', True), (False, 'ready', False),
])
def test_destination_requires_usable_preview(monkeypatch, fresh, reason, ready):
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: default)
  monkeypatch.setattr(navigation, 'preview_fresh', lambda: fresh)
  monkeypatch.setattr(navigation, 'preview_reason', lambda: reason)
  response = asyncio.run(navigation.get_destination(None))
  assert json.loads(response.text)['map_ready'] is ready


@pytest.mark.parametrize('onroad,reason', [(False, 'offroad'), (True, 'waiting')])
def test_missing_preview_explains_service_state(monkeypatch, tmp_path, onroad, reason):
  demand = tmp_path / 'demand'
  monkeypatch.setattr(navigation, 'WEB_DEMAND_PATH', demand)
  monkeypatch.setattr(navigation, 'preview_fresh', lambda: False)
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: onroad if key == 'IsOnroad' else default)
  response = asyncio.run(navigation.preview(None))
  assert response.status == 204
  assert response.headers['X-Nav-Map-Status'] == reason
  assert response.headers['Cache-Control'] == 'no-store'
  assert demand.exists()


def test_search_reads_fragmented_response_and_keeps_token_server_side(monkeypatch):
  monkeypatch.setattr(navigation.nav_search, 'unified_nav_params', lambda: {})
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: 'pk.private-test')
  payload = json.dumps({'features': [{'geometry': {'coordinates': [127., 37.]},
                                     'properties': {'full_address': 'Test destination'}}]}).encode()
  async def chunks(_):
    for i in range(0, len(payload), 7):
      yield payload[i:i + 7]
  @asynccontextmanager
  async def get(url, **kwargs):
    assert url == 'https://api.mapbox.com/search/geocode/v6/forward'
    assert kwargs['params']['access_token'] == 'pk.private-test'
    assert kwargs['params']['permanent'] == 'true'
    yield NS(status=200, content=NS(iter_chunked=chunks))
  async def run():
    app = web.Application()
    app['http'] = NS(get=get)
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.get('/api/navigation/search?q=Seoul')
      body = await response.text()
      assert response.status == 200 and 'pk.private-test' not in body
      assert response.headers['Cache-Control'] == 'no-store'
      assert json.loads(body)['results'][0]['latitude'] == 37.
      assert (await client.get('/api/navigation/search?q=Seoul')).status == 429
  asyncio.run(run())


def test_destination_whitelists_route_prefs(monkeypatch, temporary_params):
  values = {}
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: values.get(key, default))
  monkeypatch.setattr(navigation, 'set_param_value', lambda key, value: values.__setitem__(key, value))

  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      await client.post('/api/navigation/destination',
                        json={'latitude': 37., 'longitude': 127., 'strategy': 11, 'route_index': 2})
      stored = json.loads(temporary_params['NavDestinationTemporary'])
      assert stored['strategy'] == 11 and stored['route_index'] == 2
      # 越界值夹到合法区间
      await client.post('/api/navigation/destination',
                        json={'latitude': 37., 'longitude': 127., 'strategy': 99, 'route_index': -1})
      stored = json.loads(temporary_params['NavDestinationTemporary'])
      assert stored['strategy'] == 20 and stored['route_index'] == 0
      # 非法值不写键，旧目的地格式保持兼容
      await client.post('/api/navigation/destination',
                        json={'latitude': 37., 'longitude': 127., 'strategy': '快', 'route_index': None})
      stored = json.loads(temporary_params['NavDestinationTemporary'])
      assert 'strategy' not in stored and 'route_index' not in stored
  asyncio.run(run())


def test_candidates_endpoint(monkeypatch, temporary_params):
  temporary_params['LastGPSPosition'] = json.dumps({'latitude': 37., 'longitude': 127.})
  seen = {}

  def fake_candidates(origin, destination_point, *, amap_key='', timeout=8.):
    seen['origin'], seen['destination'] = origin, destination_point
    return [{'route_index': 1, 'strategy': 11, 'label': '最短', 'distance': 1000., 'duration': 60.,
             'tolls': 0., 'points': []}]

  monkeypatch.setattr(navigation.nav_plan, 'candidates', fake_candidates)

  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.get('/api/navigation/candidates?destination=37,127')
      assert response.status == 200
      assert response.headers['Cache-Control'] == 'no-store'
      body = json.loads(await response.text())
      assert body['candidates'][0]['route_index'] == 1
      # 出发地缺省时用当前定位（LastGPSPosition）
      assert seen['origin'] == (127., 37.) and seen['destination'] == (127., 37.)
      # 显式 origin 不需要定位
      response = await client.get('/api/navigation/candidates?destination=37,127&origin=38,126')
      assert response.status == 200 and seen['origin'] == (126., 38.)
      # 无定位也没有显式出发地 -> 400
      temporary_params.pop('LastGPSPosition', None)
      assert (await client.get('/api/navigation/candidates?destination=37,127')).status == 400
      # 候选规划失败 -> 502
      temporary_params['LastGPSPosition'] = json.dumps({'latitude': 37., 'longitude': 127.})

      def broken(*args, **kwargs):
        raise navigation.nav_plan.PlanError('没有可用的高德 Web 服务 Key')

      monkeypatch.setattr(navigation.nav_plan, 'candidates', broken)
      assert (await client.get('/api/navigation/candidates?destination=37,127')).status == 502
      # destination 非法 -> 400
      assert (await client.get('/api/navigation/candidates?destination=bad')).status == 400
  asyncio.run(run())
