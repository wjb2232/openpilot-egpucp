import json

import pytest

from openpilot.selfdrive.navd import amap_route


BEIJING = (116.397128, 39.916527)
WGS_INPUT = [BEIJING, (116.407128, 39.926527)]


def test_gcj_round_trip_is_sub_metre():
  for lng, lat in (BEIJING, (121.473701, 31.230416), (-117.125565, 32.711601)):
    back = amap_route.gcj02_to_wgs84(*amap_route.wgs84_to_gcj02(lng, lat))
    assert back == pytest.approx((lng, lat), abs=2e-6)


def test_gcj_shift_is_not_zero_inside_china():
  shifted = amap_route.wgs84_to_gcj02(*BEIJING)
  assert shifted != pytest.approx(BEIJING, abs=1e-4)
  # Outside China the datum is plain WGS84.
  assert amap_route.wgs84_to_gcj02(-117.125565, 32.711601) == pytest.approx((-117.125565, 32.711601))


def test_request_params_converts_and_limits_waypoints():
  points = [BEIJING, *[(116.4 + i * .001, 39.9) for i in range(20)], (116.5, 39.95)]
  params = amap_route.request_params(points, 'key.test')
  assert params['key'] == 'key.test' and params['strategy'] == '0'
  assert params['origin'] == params['origin'].strip()
  lng, lat = (float(v) for v in params['origin'].split(','))
  assert amap_route.gcj02_to_wgs84(lng, lat) == pytest.approx(BEIJING, abs=2e-6)
  assert len(params['waypoints'].split(';')) == amap_route.MAX_WAYPOINTS


def test_request_params_omits_waypoints_without_stops():
  assert 'waypoints' not in amap_route.request_params(WGS_INPUT, 'key.test')
  with pytest.raises(ValueError):
    amap_route.request_params([BEIJING], 'key.test')


@pytest.mark.parametrize('action,assistant,expected', [
  ('左转', '进入建国路', ('turn', 'left')),
  ('右转', '', ('turn', 'right')),
  ('左前方转弯', '', ('turn', 'slight left')),
  ('右前方转弯', '', ('turn', 'slight right')),
  ('左后方转弯', '', ('turn', 'sharp left')),
  ('调头', '', ('turn', 'uturn')),
  ('靠左', '', ('fork', 'left')),
  ('进入环岛', '从第2出口驶出', ('rotary', 'straight')),
  ('进入环岛', '从第2出口驶出后右转', ('rotary', 'right')),
  ('驶出匝道', '', ('off ramp', 'right')),
  ('进入匝道', '', ('on ramp', 'left')),
  ('直行', '', ('turn', 'straight')),
  ('到达目的地', '', ('arrive', 'straight')),
])
def test_maneuver_maps_to_carrot_icon_vocabulary(action, assistant, expected):
  assert amap_route.maneuver(action, assistant) == expected


def amap_body(step_override=None):
  step = {
    'instruction': '沿建国路向东行驶500米后左转',
    'road': '建国路',
    'distance': '500',
    'duration': '60',
    'action': '左转',
    'assistant_action': '进入东三环',
    'polyline': ';'.join(f'{lng:.6f},{lat:.6f}' for lng, lat in
                         (amap_route.wgs84_to_gcj02(116.397128, 39.916527),
                          amap_route.wgs84_to_gcj02(116.407128, 39.926527))),
  }
  step.update(step_override or {})
  return {'status': '1', 'route': {'paths': [{'steps': [step]}]}}


def test_parse_returns_mapbox_shape_in_wgs84():
  route = amap_route.parse(amap_body())
  assert route is not None
  step = route['routes'][0]['legs'][0]['steps'][0]
  assert step['distance'] == 500 and step['duration'] == 60 and step['duration_typical'] is None
  assert step['geometry']['coordinates'][0] == pytest.approx(list(BEIJING), abs=2e-6)
  banner = step['bannerInstructions'][0]
  assert banner['distanceAlongGeometry'] == 500
  assert banner['primary'] == {'text': '沿建国路向东行驶500米后左转', 'type': 'turn', 'modifier': 'left'}
  assert banner['secondary'] == {'text': '建国路'}
  assert 'annotation' not in route['routes'][0]['legs'][0]


def test_parse_skips_broken_steps_and_reports_failures():
  assert amap_route.parse(amap_body({'polyline': 'bad'})) is None
  assert amap_route.parse(amap_body({'distance': 'x'})) is None
  assert amap_route.parse({'status': '0'}) is None
  assert amap_route.parse({'status': '1', 'route': {'paths': []}}) is None
  assert amap_route.parse(None) is None


def test_route_settings_reads_provider_and_key(tmp_path):
  path = tmp_path / 'nav_params.json'
  assert amap_route.route_settings('pk.test', path)[:2] == ('auto', 'mapbox')

  path.write_text(json.dumps({'NavRouteProvider': 'amap', 'AmapWebKey': ' amap.test '}), encoding='utf-8')
  _, provider, key = amap_route.route_settings('', path)
  assert provider == 'amap' and key == 'amap.test'

  # An explicit provider without its key must not silently fall back.
  path.write_text(json.dumps({'NavRouteProvider': 'amap', 'AmapWebKey': ''}), encoding='utf-8')
  assert amap_route.route_settings('pk.test', path)[1] is None

  path.write_text(json.dumps({'NavRouteProvider': 'mapbox', 'AmapWebKey': 'amap.test'}), encoding='utf-8')
  assert amap_route.route_settings('pk.test', path)[1] == 'mapbox'
