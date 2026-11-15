"""离线 PMTiles 底图：来源切换、归档管理、mapsd 分派与 Mapbox polyline。"""
import importlib.util
import io
import os
import struct
import tarfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
  'offline_tiles_under_test',
  Path(__file__).resolve().parents[1] / 'carrot_offline_tiles.py')
offline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(offline)


class FakePMTiles:
  def __init__(self, source):
    self.source = source


class FakeMapboxTiles:
  def __init__(self, token):
    self.token = token


class FakeRemoteTiles:
  pass


def test_provider_roundtrip_and_validation(tmp_path):
  state = str(tmp_path / 'state.json')
  assert offline.get_provider(state) == 'amap'
  assert offline.set_provider('osm', state) == 'osm'
  assert offline.get_provider(state) == 'osm'
  with pytest.raises(offline.OfflineMapError):
    offline.set_provider('unknown', state)


def test_archives_active_and_delete(tmp_path):
  archive_dir = str(tmp_path / 'archives')
  state = str(tmp_path / 'state.json')
  os.makedirs(archive_dir)
  with open(os.path.join(archive_dir, 'beijing.pmtiles'), 'wb') as f:
    f.write(b'x' * 100)
  with open(os.path.join(archive_dir, 'shanghai.pmtiles'), 'wb') as f:
    f.write(b'y' * 200)
  data = offline.status(archive_dir, state)
  assert data['total_bytes'] == 300 and len(data['archives']) == 2
  assert offline.active_path(state, archive_dir).endswith('shanghai.pmtiles')
  offline.set_active('beijing.pmtiles', state, archive_dir)
  assert offline.active_path(state, archive_dir).endswith('beijing.pmtiles')
  offline.delete_archive('beijing.pmtiles', state, archive_dir)
  assert [a['name'] for a in offline.list_archives(archive_dir)] == ['shanghai.pmtiles']


def test_make_archive_dispatch(tmp_path):
  archive_dir = str(tmp_path / 'archives')
  state = str(tmp_path / 'state.json')
  os.makedirs(archive_dir)
  with open(os.path.join(archive_dir, 'city.pmtiles'), 'wb') as f:
    f.write(b'PMTiles\x03' + b'\0' * 119)
  make = lambda: offline.make_archive('pk.test', FakeMapboxTiles, FakePMTiles,
                                      FakeRemoteTiles, state, archive_dir)
  # 默认 amap / 显式 mapbox：车机渲染图仍用在线 Mapbox
  assert isinstance(make(), FakeMapboxTiles)
  offline.set_provider('mapbox', state)
  assert isinstance(make(), FakeMapboxTiles)
  # osm + 本地归档：切到完全离线的 LocalTiles
  offline.set_provider('osm', state)
  result = make()
  assert isinstance(result, FakePMTiles) and isinstance(result.source, offline.LocalTiles)
  result.source.close()


def test_make_archive_without_token_uses_remote(tmp_path):
  state = str(tmp_path / 'state.json')
  archive_dir = str(tmp_path / 'archives')
  os.makedirs(archive_dir)
  result = offline.make_archive('', FakeMapboxTiles, FakePMTiles,
                                FakeRemoteTiles, state, archive_dir)
  assert isinstance(result, FakePMTiles) and isinstance(result.source, FakeRemoteTiles)


def test_local_tiles_reads_byte_ranges(tmp_path):
  path = str(tmp_path / 'demo.pmtiles')
  with open(path, 'wb') as f:
    f.write(b'0123456789ABCDEF')
  source = offline.LocalTiles(path)
  assert source.size == 16
  assert source.read(4, 3) == b'456'
  source.prefetch([])
  source.close()


def test_start_download_validates_inputs(tmp_path, monkeypatch):
  missing = str(tmp_path / 'no-cli')
  monkeypatch.setattr(offline, 'PMTILES_BIN', missing)
  with pytest.raises(offline.OfflineMapError):
    offline.start_download('beijing', [116.2, 39.8, 116.6, 40.1], 15,
                           str(tmp_path / 'archives'), str(tmp_path / 'state.json'))


# ─────────────────────────────────────────────
# 裁剪工具（go-pmtiles）部署
# ─────────────────────────────────────────────
ASSET_BASE = 'https://github.com/protomaps/go-pmtiles/releases/download/v1.25.0/'
ASSETS = [ASSET_BASE + 'go-pmtiles_1.25.0_Windows_x86_64.zip',
          ASSET_BASE + 'go-pmtiles_1.25.0_Darwin_arm64.tar.gz',
          ASSET_BASE + 'go-pmtiles_1.25.0_Linux_x86_64.tar.gz',
          ASSET_BASE + 'go-pmtiles_1.25.0_Linux_arm64.tar.gz',
          ASSET_BASE + 'checksums.txt']


def test_cli_arch_maps_device_machines():
  assert offline.cli_arch('x86_64') == 'x86_64'
  assert offline.cli_arch('AMD64') == 'x86_64'
  assert offline.cli_arch('aarch64') == 'arm64'
  assert offline.cli_arch('armv7l') == 'armv6'
  assert offline.cli_arch('mips') == ''


def test_pick_cli_asset_skips_other_platforms():
  assert offline.pick_cli_asset(ASSETS, 'arm64').endswith('Linux_arm64.tar.gz')
  assert offline.pick_cli_asset(ASSETS, 'x86_64').endswith('Linux_x86_64.tar.gz')
  # armv6 没有对应的 Linux 包，不能退回去装错架构
  assert offline.pick_cli_asset(ASSETS, 'armv6') == ''
  assert offline.pick_cli_asset(ASSETS, '') == ''


class _StreamingResponse:
  """按 read(size) 逐块吐数据，模拟 urlopen 的响应体。"""

  def __init__(self, body, status=200):
    self._body = body
    self.status = status
    self.headers = {'Content-Length': str(len(body))}

  def __enter__(self):
    return self

  def __exit__(self, *args):
    return False

  def read(self, size=-1):
    chunk, self._body = self._body[:size], self._body[size:]
    return chunk


def test_download_with_resume_appends_from_offset(monkeypatch, tmp_path):
  target = str(tmp_path / 'pkg.tar.gz')
  with open(target, 'wb') as f:
    f.write(b'0123456789')
  seen = {}

  def fake_urlopen(request, timeout=None):
    seen['range'] = request.get_header('Range')
    return _StreamingResponse(b'abcdefghij', status=206)

  monkeypatch.setattr(offline.urllib.request, 'urlopen', fake_urlopen)
  progress = {}
  assert offline._download_with_resume('http://x/pkg.tar.gz', target, progress) == 20
  assert seen['range'] == 'bytes=10-'
  with open(target, 'rb') as f:
    assert f.read() == b'0123456789abcdefghij'
  assert progress['bytes'] == 20 and progress['total_bytes'] == 20
  assert progress['percent'] == 99


def test_download_with_resume_restarts_when_range_ignored(monkeypatch, tmp_path):
  target = str(tmp_path / 'pkg.tar.gz')
  with open(target, 'wb') as f:
    f.write(b'stale-partial')
  monkeypatch.setattr(offline.urllib.request, 'urlopen',
                      lambda request, timeout=None: _StreamingResponse(b'fresh', status=200))
  assert offline._download_with_resume('http://x', target) == 5
  with open(target, 'rb') as f:
    assert f.read() == b'fresh'


def test_install_cli_archive_extracts_executable(monkeypatch, tmp_path):
  archive = str(tmp_path / 'pkg.tar.gz')
  payload = b'#!/bin/sh\necho pmtiles\n'
  with tarfile.open(archive, 'w:gz') as tar:
    info = tarfile.TarInfo('go-pmtiles_1.25.0_Linux_arm64/pmtiles')
    info.size, info.mode = len(payload), 0o644
    tar.addfile(info, io.BytesIO(payload))
    readme = tarfile.TarInfo('README.md')
    readme.size = 3
    tar.addfile(readme, io.BytesIO(b'hi\n'))
  monkeypatch.setattr(offline, '_verify_cli', lambda path: None)
  target = str(tmp_path / 'pmtiles')
  offline._install_cli_archive(archive, target)
  with open(target, 'rb') as f:
    assert f.read() == payload
  assert not os.path.exists(target + '.new')


def test_install_cli_archive_rejects_package_without_binary(monkeypatch, tmp_path):
  archive = str(tmp_path / 'pkg.tar.gz')
  with tarfile.open(archive, 'w:gz') as tar:
    info = tarfile.TarInfo('LICENSE')
    info.size = 3
    tar.addfile(info, io.BytesIO(b'hi\n'))
  monkeypatch.setattr(offline, '_verify_cli', lambda path: None)
  target = str(tmp_path / 'pmtiles')
  with pytest.raises(offline.OfflineMapError):
    offline._install_cli_archive(archive, target)
  assert not os.path.exists(target)


def test_prepare_partial_keeps_only_same_url(tmp_path):
  archive = str(tmp_path / '.pmtiles-install.tar.gz')
  with open(archive, 'wb') as f:
    f.write(b'no-marker-yet')
  offline._prepare_partial(archive, 'http://x/v1/pkg.tar.gz')
  assert not os.path.exists(archive)  # 来历不明的半包直接作废
  with open(archive, 'wb') as f:
    f.write(b'half')
  offline._prepare_partial(archive, 'http://x/v1/pkg.tar.gz')
  assert os.path.exists(archive)  # 同版本，可续传
  offline._prepare_partial(archive, 'http://x/v2/pkg.tar.gz')
  assert not os.path.exists(archive)  # 换版本，残留作废


def test_install_cli_failure_keeps_partial_download(monkeypatch, tmp_path):
  archive = tmp_path / '.pmtiles-install.tar.gz'
  archive.write_bytes(b'partial')
  (tmp_path / '.pmtiles-install.tar.gz.url').write_text('http://x/pkg.tar.gz', encoding='utf-8')
  monkeypatch.setattr(offline, 'cli_download_url', lambda *a, **k: 'http://x/pkg.tar.gz')

  def broken(url, target, progress=None, timeout=60.):
    raise OSError('network down')

  monkeypatch.setattr(offline, '_download_with_resume', broken)
  state = str(tmp_path / 'state.json')
  progress = offline.install_cli(str(tmp_path / 'pmtiles'), state)
  assert progress['state'] == 'error' and 'network down' in progress['message']
  # 半包留着，下次点安装直接续传
  assert archive.exists()
  assert offline.read_state(state)['cli']['state'] == 'error'


def test_install_cli_success_removes_partial(monkeypatch, tmp_path):
  monkeypatch.setattr(offline, 'cli_download_url', lambda *a, **k: 'http://x/pkg.tar.gz')
  monkeypatch.setattr(offline, '_download_with_resume',
                      lambda url, target, progress=None, timeout=60.: 2048)
  monkeypatch.setattr(offline, '_install_cli_archive', lambda archive, target: None)
  state = str(tmp_path / 'state.json')
  progress = offline.install_cli(str(tmp_path / 'pmtiles'), state)
  assert progress['state'] == 'done' and progress['percent'] == 100
  assert not (tmp_path / '.pmtiles-install.tar.gz').exists()
  assert offline.read_state(state)['cli']['state'] == 'done'


def test_start_cli_install_rejects_unsupported_arch(monkeypatch, tmp_path):
  monkeypatch.setattr(offline, 'cli_arch', lambda machine=None: '')
  with pytest.raises(offline.OfflineMapError):
    offline.start_cli_install(str(tmp_path / 'pmtiles'), str(tmp_path / 'state.json'))


def test_encode_polyline_matches_google_example():
  # 官方示例坐标为 (lat, lon)，本模块统一用 (lon, lat)。
  points = [(-120.2, 38.5), (-120.95, 40.7), (-126.453, 43.252)]
  assert offline.encode_polyline(points) == '_p~iF~ps|U_ulLnnqC_mqNvxq`@'


def test_estimate_bytes_matches_dry_run_magnitude():
  jiangsu = (116.35, 30.75, 121.95, 35.33)
  z15 = offline.estimate_bytes(jiangsu, 15)
  z14 = offline.estimate_bytes(jiangsu, 14)
  z13 = offline.estimate_bytes(jiangsu, 13)
  # 设备 dry-run 实测：z15 165 MB / z14 88 MB / z13 52 MB
  assert 100 * 1024 ** 2 < z15 < 300 * 1024 ** 2
  assert 50 * 1024 ** 2 < z14 < 150 * 1024 ** 2
  assert 25 * 1024 ** 2 < z13 < 100 * 1024 ** 2
  assert z13 < z14 < z15
  assert offline.estimate_bytes((116.35, 30.75, 116.45, 30.85), 15) < z15


def test_png_header():
  raw = bytearray(b'\x1a\x21\x2b' * 4)
  png = offline._png(2, 2, raw)
  assert png.startswith(b'\x89PNG\r\n\x1a\n')
  assert png[12:16] == b'IHDR'
  assert png[16:24] == b'\x00\x00\x00\x02\x00\x00\x00\x02'


class _FakeResponse:
  def __init__(self, body):
    self.body = body

  def __enter__(self):
    return self

  def __exit__(self, *args):
    return False

  def read(self, limit):
    return self.body[:limit]


def test_mapbox_static_png_uses_square_canvas(monkeypatch, tmp_path):
  seen = []
  png = b'\x89PNG\r\n\x1a\n' + b'0' * 100

  def fake_urlopen(url, timeout=None):
    seen.append(url)
    return _FakeResponse(png)

  monkeypatch.setattr(offline.urllib.request, 'urlopen', fake_urlopen)
  points = [(116.3, 39.9), (116.5, 40.0)]
  assert offline.mapbox_static_png(points, 'pk.test', cache_dir=str(tmp_path)) == png
  assert f'/auto/{offline.PREVIEW_SIZE}x{offline.PREVIEW_SIZE}' in seen[0]


def test_render_zoom_fits_route_into_square_canvas(monkeypatch):
  class FakeArchive:
    max_zoom = min_zoom = 15

    def get(self, z, x, y):
      return b'tile'

    def close(self):
      pass

  monkeypatch.setattr(offline, '_mvt_road_lines',
                      lambda tile, max_lines=0, kinds=None: [([(0., 0.), (1., 1.)], 1)])
  drawn = []
  real_line = offline._line

  def spy(buf, width, height, a, b, color, thickness=1):
    if color == (255, 140, 32):
      drawn.extend((a, b))
    real_line(buf, width, height, a, b, color, thickness)

  monkeypatch.setattr(offline, '_line', spy)
  xy = [offline.mercator(lon, lat) for lon, lat in
        ((116.30, 39.90), (116.35, 39.95), (116.40, 40.00))]
  coverage, png = offline._render_zoom(FakeArchive(), 15, xy, 720, 720)
  assert coverage > 0 and png[16:24] == struct.pack('>II', 720, 720)
  assert drawn and all(0 <= value <= 720 for point in drawn for value in point)


def test_render_preview_without_archive(tmp_path):
  with pytest.raises(offline.OfflineMapError, match='归档'):
    offline.render_preview([(116.3, 39.9), (116.5, 40.0)],
                           state_path=str(tmp_path / 'state.json'),
                           archive_dir=str(tmp_path / 'none'))


def test_render_preview_falls_back_to_nationwide_archive(tmp_path, monkeypatch):
  archive_dir = str(tmp_path / 'archives')
  state = str(tmp_path / 'state.json')
  os.makedirs(archive_dir)
  for name, size in (('city.pmtiles', 10), ('quanguo.pmtiles', 1000)):
    with open(os.path.join(archive_dir, name), 'wb') as f:
      f.write(b'x' * size)
  offline.set_active('city.pmtiles', state, archive_dir)
  calls = []
  png = b'\x89PNG\r\n\x1a\n' + b'0' * 10

  def fake_render(path, points, width, height):
    calls.append((os.path.basename(path), width, height))
    return (0., None) if path.endswith('city.pmtiles') else (.9, png)

  monkeypatch.setattr(offline, '_render_archive', fake_render)
  assert offline.render_preview([(116.3, 39.9), (116.5, 40.0)],
                                state_path=state, archive_dir=archive_dir) == png
  assert calls == [('city.pmtiles', 720, 720), ('quanguo.pmtiles', 720, 720)]
