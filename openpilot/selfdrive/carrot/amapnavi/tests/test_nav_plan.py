import json

import pytest

from openpilot.selfdrive.carrot.amapnavi import nav_plan
from openpilot.selfdrive.navd import amap_route


BEIJING = (116.397128, 39.916527)   # (longitude, latitude)
SHENZHEN = (114.380312, 22.721993)


def test_parse_point_reads_lat_lon_and_rejects_garbage():
  assert nav_plan.parse_point('39.916527,116.397128') == pytest.approx(BEIJING)
  for value in ('', 'x', '91,0', '0,181', 'nan,0'):
    assert nav_plan.parse_point(value) is None


def test_live_position_falls_back_to_none():
  class Params:
    def __init__(self, value):
      self.value = value

    def get(self, key):
      assert key == 'LastGPSPosition'
      return self.value

  assert nav_plan.live_position(Params(None)) is None
  assert nav_plan.live_position(Params('bad json')) is None
  assert nav_plan.live_position(Params(json.dumps({'latitude': 22.7, 'longitude': 114.3}))) == pytest.approx((114.3, 22.7))
  assert nav_plan.live_position(object()) is None


def test_payload_downsamples_and_rounds():
  points = [[116.3971284 + i * 1e-4, 39.9165275] for i in range(4000)]
  payload = nav_plan._payload('amap', points, 1000., 60., 4)
  assert payload['provider'] == 'amap' and payload['steps'] == 4
  assert payload['distance'] == 1000. and payload['duration'] == 60.
  assert nav_plan.PREVIEW_POINTS // 2 < len(payload['points']) <= nav_plan.PREVIEW_POINTS
  assert payload['points'][0] == [116.397128, 39.916528]


def test_amap_route_is_flattened_from_the_shared_adapter(monkeypatch):
  start, end = (amap_route.wgs84_to_gcj02(*BEIJING), amap_route.wgs84_to_gcj02(*SHENZHEN))
  body = {'status': '1', 'route': {'paths': [{'steps': [
    {'distance': '800', 'duration': '120', 'action': '左转', 'road': '测试路', 'instruction': '左转进入测试路',
     'polyline': f'{start[0]:.6f},{start[1]:.6f};{end[0]:.6f},{end[1]:.6f}'},
  ]}]}}
  seen = {}
  monkeypatch.setattr(nav_plan, '_get_json', lambda url, timeout: seen.setdefault('url', url) and body)
  payload = nav_plan._amap(BEIJING, SHENZHEN, 'amap.test', 5.)
  assert 'key=amap.test' in seen['url'] and 'origin=' in seen['url'] and 'destination=' in seen['url']
  assert payload['provider'] == 'amap' and payload['steps'] == 1
  assert payload['distance'] == 800 and payload['duration'] == 120
  assert payload['points'][0] == pytest.approx(list(BEIJING), abs=2e-6)


def test_mapbox_route_uses_geojson_geometry(monkeypatch):
  body = {'routes': [{'distance': 1200.5, 'duration': 300.5, 'legs': [{'steps': [{}, {}]}],
                      'geometry': {'coordinates': [list(BEIJING), list(SHENZHEN)]}}]}
  seen = {}
  monkeypatch.setattr(nav_plan, '_get_json', lambda url, timeout: seen.setdefault('url', url) and body)
  payload = nav_plan._mapbox(BEIJING, SHENZHEN, 'pk.test', 5.)
  assert seen['url'].startswith(nav_plan.MAPBOX_DRIVING_URL)
  assert 'access_token=pk.test' in seen['url']
  assert payload == {'provider': 'mapbox', 'steps': 2, 'distance': 1200.5, 'duration': 300.5,
                     'points': [[round(v, 6) for v in BEIJING], [round(v, 6) for v in SHENZHEN]]}


def test_plan_prefers_amap_and_reports_failures(monkeypatch):
  monkeypatch.setattr(nav_plan, '_amap', lambda *a: {'provider': 'amap', 'points': [], 'steps': 0,
                                                     'distance': 0., 'duration': 0.})
  assert nav_plan.plan(BEIJING, SHENZHEN, amap_key='k', mapbox_key='pk')['provider'] == 'amap'

  def broken(*args):
    raise nav_plan.PlanError('坏了')

  monkeypatch.setattr(nav_plan, '_amap', broken)
  monkeypatch.setattr(nav_plan, '_mapbox', lambda *a: {'provider': 'mapbox', 'points': []})
  assert nav_plan.plan(BEIJING, SHENZHEN, amap_key='k', mapbox_key='pk')['provider'] == 'mapbox'

  monkeypatch.setattr(nav_plan, '_mapbox', broken)
  with pytest.raises(nav_plan.PlanError) as error:
    nav_plan.plan(BEIJING, SHENZHEN, amap_key='k', mapbox_key='pk')
  assert '高德' in str(error.value) and 'Mapbox' in str(error.value)

  with pytest.raises(nav_plan.PlanError):
    nav_plan.plan(BEIJING, SHENZHEN)
  with pytest.raises(nav_plan.PlanError):
    nav_plan.plan(None, SHENZHEN, amap_key='k')


def test_static_map_params_shift_to_gcj02_and_cap_points():
  points = [[BEIJING[0] + i * 1e-4, BEIJING[1]] for i in range(200)]
  query = nav_plan.static_map_params(points, 'key.test')
  assert query['key'] == 'key.test' and query['size'] == nav_plan.STATIC_MAP_SIZE
  # 三种底图统一正方形，避免预览页 object-fit: contain 留黑边
  width, height = query['size'].split('*')
  assert width == height and query['scale'] == '1'
  # 不传 center/zoom，让高德自动适配整条路线
  assert 'location' not in query and 'zoom' not in query
  line = query['paths'].split(':', 1)[1]
  coordinates = line.split(';')
  assert 2 < len(coordinates) <= 50
  lng, lat = (float(value) for value in coordinates[0].split(','))
  assert amap_route.gcj02_to_wgs84(lng, lat) == pytest.approx(BEIJING, abs=2e-6)
  assert query['markers'].count('|') == 1
  with pytest.raises(nav_plan.PlanError):
    nav_plan.static_map_params([BEIJING], 'key.test')


class _FakeResponse:
  def __init__(self, body):
    self.body = body

  def __enter__(self):
    return self

  def __exit__(self, *args):
    return False

  def read(self, limit):
    return self.body[:limit]


def test_static_map_png_caches_by_route(monkeypatch, tmp_path):
  calls = []
  png = b'\x89PNG\r\n\x1a\n' + b'0' * 100
  monkeypatch.setattr(nav_plan.urllib.request, 'urlopen',
                      lambda request, timeout=None: (calls.append(1), _FakeResponse(png))[1])
  points = [(BEIJING[0], BEIJING[1]), (SHENZHEN[0], SHENZHEN[1])]
  body = nav_plan.static_map_png(points, 'key', cache_dir=str(tmp_path))
  assert body == png and len(calls) == 1
  assert nav_plan.static_map_png(points, 'key', cache_dir=str(tmp_path)) == png
  assert len(calls) == 1, 'the same route must not cost another AMap request'


def test_static_map_png_rejects_api_errors(monkeypatch, tmp_path):
  monkeypatch.setattr(nav_plan.urllib.request, 'urlopen',
                      lambda request, timeout=None: _FakeResponse(b'{"status":"0"}'))
  with pytest.raises(nav_plan.PlanError):
    nav_plan.static_map_png([BEIJING, SHENZHEN], 'key', cache_dir=str(tmp_path))


def candidates_body(distances):
  paths = []
  # 高德返回的 polyline 是 GCJ-02，fixture 也用 GCJ 坐标模拟真实数据
  start, end = amap_route.wgs84_to_gcj02(*BEIJING), amap_route.wgs84_to_gcj02(*SHENZHEN)
  for distance, duration in distances:
    paths.append({'distance': str(distance), 'duration': str(duration), 'tolls': '0',
                  'steps': [{'polyline': f'{start[0]:.6f},{start[1]:.6f};{end[0]:.6f},{end[1]:.6f}'}]})
  return {'status': '1', 'route': {'paths': paths}}


def test_candidates_returns_labelled_cards(monkeypatch):
  bodies = iter([candidates_body([(900, 60), (1000, 50), (1200, 70)])])
  monkeypatch.setattr(nav_plan, '_get_json', lambda url, timeout: next(bodies))
  cards = nav_plan.candidates(BEIJING, SHENZHEN, amap_key='amap.test')
  assert [card['label'] for card in cards] == list(amap_route.ROUTE_LABELS)
  assert [card['route_index'] for card in cards] == [0, 1, 2]
  assert all(card['strategy'] == 11 for card in cards)
  assert cards[0]['distance'] == 900 and cards[0]['duration'] == 60 and cards[0]['tolls'] == 0
  assert len(cards[0]['points']) == 2
  assert cards[0]['points'][0] == pytest.approx([BEIJING[0], BEIJING[1]], abs=2e-6)


def test_candidates_dedupes_and_requires_a_key(monkeypatch):
  # strategy=11 偶尔会给两条完全一样的路；同 distance+duration 只留一张卡片
  bodies = iter([candidates_body([(900, 60), (900, 60), (1200, 70)])])
  monkeypatch.setattr(nav_plan, '_get_json', lambda url, timeout: next(bodies))
  cards = nav_plan.candidates(BEIJING, SHENZHEN, amap_key='amap.test')
  assert [card['route_index'] for card in cards] == [0, 2]

  with pytest.raises(nav_plan.PlanError):
    nav_plan.candidates(BEIJING, SHENZHEN, amap_key='')


def test_candidates_pref_uses_pref_strategy_and_label(monkeypatch):
  # 偏好策略（如不走高速 strategy=14）通常只回单条路线，卡片直接用偏好名
  seen = {}
  bodies = iter([candidates_body([(950, 65)])])

  def fake_json(url, timeout):
    seen['url'] = url
    return next(bodies)

  monkeypatch.setattr(nav_plan, '_get_json', fake_json)
  cards = nav_plan.candidates(BEIJING, SHENZHEN, amap_key='amap.test', pref='avoid_highway')
  assert 'strategy=14' in seen['url']
  assert [card['label'] for card in cards] == ['不走高速']
  assert [card['strategy'] for card in cards] == [14]


def test_candidates_rejects_failed_body(monkeypatch):
  monkeypatch.setattr(nav_plan, '_get_json', lambda url, timeout: {'status': '0', 'info': 'INVALID_KEY'})
  with pytest.raises(nav_plan.PlanError) as error:
    nav_plan.candidates(BEIJING, SHENZHEN, amap_key='amap.test')
  assert 'INVALID_KEY' in str(error.value)
