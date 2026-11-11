import asyncio
import json
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace as NS

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from openpilot.selfdrive.carrot.server.features import nav_search, navigation


def reset_nav_params_cache():
  nav_search._NAV_PARAMS_CACHE.update({"mtime": None, "data": {}})


def test_gcj02_transform_roundtrip_and_offset():
  # Tiananmen: GCJ-02 sits a few hundred metres east/north of the WGS84 point.
  wgs = (116.391248, 39.907898)
  gcj_lng, gcj_lat = nav_search.wgs84_to_gcj02(*wgs)
  assert gcj_lng - wgs[0] == pytest.approx(0.00624, abs=5e-4)
  assert gcj_lat - wgs[1] == pytest.approx(0.00140, abs=5e-4)

  back_lng, back_lat = nav_search.gcj02_to_wgs84(gcj_lng, gcj_lat)
  assert back_lng == pytest.approx(wgs[0], abs=1e-6)
  assert back_lat == pytest.approx(wgs[1], abs=1e-6)

  bd_lng, bd_lat = 116.403963, 39.915119
  lng, lat = nav_search.bd09_to_wgs84(bd_lng, bd_lat)
  assert lng < bd_lng and lat < bd_lat


def test_out_of_china_coordinates_are_untouched():
  assert nav_search.gcj02_to_wgs84(-122.4, 37.8) == (-122.4, 37.8)
  assert nav_search.wgs84_to_gcj02(-122.4, 37.8) == (-122.4, 37.8)


def test_auto_prefers_chinese_providers_then_mapbox():
  assert nav_search.resolve_provider('auto', 'amap-key', '', 'pk.key') == 'amap'
  assert nav_search.resolve_provider('auto', '', 'baidu-key', 'pk.key') == 'baidu'
  assert nav_search.resolve_provider('auto', '', '', 'pk.key') == 'mapbox'
  assert nav_search.resolve_provider('', '', '', 'pk.key') == 'mapbox'
  assert nav_search.resolve_provider('auto', '', '', '') is None
  assert nav_search.resolve_provider('baidu', 'amap-key', '', 'pk.key') is None


def test_unified_nav_params_reads_file_and_reloads(tmp_path):
  reset_nav_params_cache()
  path = tmp_path / "nav_params.json"
  path.write_text(json.dumps({"NavSearchProvider": "baidu", "BaiduWebAk": "ak-1"}), encoding="utf-8")
  assert nav_search.unified_nav_params(path)["BaiduWebAk"] == "ak-1"

  path.write_text(json.dumps({"NavSearchProvider": "amap"}), encoding="utf-8")
  later = path.stat().st_mtime + 5
  os.utime(path, (later, later))
  data = nav_search.unified_nav_params(path)
  assert data["NavSearchProvider"] == "amap" and "BaiduWebAk" not in data

  assert nav_search.unified_nav_params(tmp_path / "missing.json") == {}


def test_unified_nav_params_tolerates_broken_json(tmp_path):
  reset_nav_params_cache()
  path = tmp_path / "nav_params.json"
  path.write_text("{not json", encoding="utf-8")
  assert nav_search.unified_nav_params(path) == {}


def test_amap_results_are_returned_as_wgs84():
  body = {'status': '1', 'info': 'OK', 'tips': [
    {'name': '天安门', 'district': '东城区', 'address': '东长安街', 'location': '116.397428,39.909230'},
    {'name': '特1路', 'location': []},
    {'name': '无坐标', 'location': 'bad'},
  ]}
  results = nav_search._parse_amap(body, '天安门')
  assert len(results) == 1
  assert results[0]['place_name'] == '天安门 · 东城区 · 东长安街'
  expected_lng, expected_lat = nav_search.gcj02_to_wgs84(116.397428, 39.909230)
  assert results[0]['latitude'] == pytest.approx(expected_lat, abs=1e-9)
  assert results[0]['longitude'] == pytest.approx(expected_lng, abs=1e-9)


def test_baidu_results_are_returned_as_wgs84():
  body = {'status': 0, 'results': [
    {'name': '天安门', 'city': '北京市', 'address': '东长安街',
     'location': {'lng': 116.403963, 'lat': 39.915119}},
  ]}
  results = nav_search._parse_baidu(body, '天安门')
  assert len(results) == 1
  assert results[0]['place_name'] == '天安门 · 北京市 · 东长安街'
  expected_lng, expected_lat = nav_search.bd09_to_wgs84(116.403963, 39.915119)
  assert results[0]['latitude'] == pytest.approx(expected_lat, abs=1e-9)
  assert results[0]['longitude'] == pytest.approx(expected_lng, abs=1e-9)


def test_provider_errors_surface_as_search_errors():
  with pytest.raises(nav_search.SearchError):
    nav_search._parse_amap({'status': '0', 'info': 'INVALID_USER_KEY'}, 'q')
  with pytest.raises(nav_search.SearchError):
    nav_search._parse_baidu({'status': 302, 'message': 'Invalid AK'}, 'q')


def test_search_uses_configured_amap_key(monkeypatch):
  monkeypatch.setattr(nav_search, 'unified_nav_params',
                      lambda path=None: {'NavSearchProvider': 'amap', 'AmapWebKey': 'amap-secret-key'})
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: default)

  payload = json.dumps({'status': '1', 'tips': [
    {'name': '天安门', 'location': '116.397428,39.909230'},
  ]}).encode()
  seen = {}

  async def chunks(_):
    for index in range(0, len(payload), 5):
      yield payload[index:index + 5]

  @asynccontextmanager
  async def get(url, **kwargs):
    seen['url'], seen['params'] = url, kwargs['params']
    yield NS(status=200, content=NS(iter_chunked=chunks))

  async def run():
    app = web.Application()
    app['http'] = NS(get=get)
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.get('/api/navigation/search?q=天安门')
      body = await response.json()
      assert response.status == 200
      assert body['provider'] == 'amap'
      assert body['results'][0]['place_name'].startswith('天安门')
      assert 'amap-secret-key' not in json.dumps(body)

  asyncio.run(run())
  assert seen['url'] == nav_search.AMAP_URL
  assert seen['params']['key'] == 'amap-secret-key'


def test_search_without_any_key_explains_where_to_configure(monkeypatch):
  monkeypatch.setattr(nav_search, 'unified_nav_params', lambda path=None: {})
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: default)

  async def run():
    app = web.Application()
    app['http'] = NS()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.get('/api/navigation/search?q=Seoul')
      assert response.status == 409
      assert '8088/nav_params' in (await response.json())['error']

  asyncio.run(run())
