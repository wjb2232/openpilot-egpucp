"""OSM 离线地图缓存：2° 分片网格、下载进度、缓存统计与解压安全。"""
import importlib.util
import io
import os
import tarfile
from pathlib import Path

import pytest

# osm_cache 只依赖标准库；直接按文件加载，避免 amapnavi/__init__.py 拉起设备上的 msgq。
_spec = importlib.util.spec_from_file_location(
  'osm_cache_under_test', Path(__file__).resolve().parents[1] / 'osm_cache.py')
osm_cache = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(osm_cache)

BEIJING_BBOX = [116.20, 39.80, 116.60, 40.10]


def test_beijing_maps_to_2deg_tiles():
  # 39.8~40.1 跨过 40° 网格边界，覆盖 38/116 与 40/116 两个分片。
  assert osm_cache.tiles_for_bbox(BEIJING_BBOX) == [(38, 116), (40, 116)]


def test_bbox_crossing_grid_boundary_expands():
  tiles = osm_cache.tiles_for_bbox([116.2, 39.9, 116.3, 40.1])
  assert (38, 116) in tiles and (40, 116) in tiles


def test_invalid_bbox_is_rejected():
  with pytest.raises(osm_cache.OsmError):
    osm_cache.tiles_for_bbox([181, 0, 182, 1])
  with pytest.raises(osm_cache.OsmError):
    osm_cache.tiles_for_bbox([10, 20, 9, 21])


def test_regions_are_local_and_resolvable():
  all_regions = osm_cache.regions()
  assert all(r['tiles'] >= 1 for r in all_regions)
  assert any(r['name'] == '北京' for r in all_regions)


def test_province_regions_cover_whole_provinces():
  all_regions = osm_cache.regions()
  provinces = {r['key']: r for r in all_regions if r['kind'] == 'province'}
  assert len(provinces) == 34
  assert osm_cache.find_region('province:guangdong')['kind'] == 'province'
  # 坪山坑梓（114.36586, 22.74586）在城市「深圳」bbox 之外，但必须落在广东省内
  bbox = provinces['province:guangdong']['bbox']
  assert bbox[0] <= 114.36586 <= bbox[2] and bbox[1] <= 22.74586 <= bbox[3]
  assert all(r['bbox'][0] < r['bbox'][2] and r['bbox'][1] < r['bbox'][3]
             for r in provinces.values())
  assert any(r['key'] == 'country:CN' for r in all_regions)
  assert osm_cache.find_region('beijing')['name'] == '北京'
  assert osm_cache.find_region('no-such-region') is None


def test_nationwide_is_allowed_but_global_bbox_is_limited(tmp_path):
  # 全国下载已放开：中国约 576 个 2° 分片，应在上限内。
  bbox = list(osm_cache.COUNTRY_REGIONS['CN'][1])
  tiles = osm_cache.tiles_for_bbox(bbox)
  assert 20 < len(tiles) <= osm_cache.MAX_TILES_PER_DOWNLOAD
  # 全球 bbox 仍然超限，且必须在启动下载线程之前就被拒绝。
  with pytest.raises(osm_cache.OsmError):
    osm_cache.start_download('全球', [-180, -85, 180, 85],
                             str(tmp_path / 'cache'), str(tmp_path / 'state.json'))


def test_download_updates_progress_manifest_and_status(tmp_path, monkeypatch):
  cache_dir = str(tmp_path / 'cache')
  state_path = str(tmp_path / 'state.json')
  monkeypatch.setattr(osm_cache, '_ACTIVE_THREAD', None)
  calls = []

  def fake_download(lat, lon, cache_dir=None, timeout=60.):
    target = os.path.join(cache_dir, str(lat), str(lon))
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, 'ways.bin'), 'wb') as f:
      f.write(b'x' * 2048)
    calls.append((lat, lon))
    return 2048

  monkeypatch.setattr(osm_cache, 'download_tile', fake_download)
  result = osm_cache.start_download('北京', BEIJING_BBOX, cache_dir, state_path)
  osm_cache._ACTIVE_THREAD.join(timeout=10)
  assert result['tiles'] == 2 and result['region'] == '北京'

  data = osm_cache.status(cache_dir, state_path)
  progress = data['progress']
  assert progress['state'] == 'done'
  assert progress['downloaded_files'] == progress['total_files'] == 2
  assert progress['bytes'] == 4096
  assert calls == [(38, 116), (40, 116)]
  assert data['cache_bytes'] == 4096
  assert all('北京' in tile['regions'] for tile in data['tiles'])


def test_clear_cache_resets_status(tmp_path, monkeypatch):
  cache_dir = str(tmp_path / 'cache')
  state_path = str(tmp_path / 'state.json')
  monkeypatch.setattr(osm_cache, '_ACTIVE_THREAD', None)
  os.makedirs(os.path.join(cache_dir, '38', '116'))
  with open(os.path.join(cache_dir, '38', '116', 'ways.bin'), 'wb') as f:
    f.write(b'x' * 100)
  assert osm_cache.status(cache_dir, state_path)['cache_bytes'] == 100
  data = osm_cache.clear_cache(cache_dir, state_path)
  assert data['cache_bytes'] == 0 and data['tiles'] == []


def test_safe_extract_blocks_path_traversal(tmp_path):
  archive = str(tmp_path / 'tile.tar.gz')
  with tarfile.open(archive, 'w:gz') as tar:
    for name, payload in (('offline/38/116/ways.bin', b'good'), ('../evil.bin', b'bad')):
      info = tarfile.TarInfo(name)
      info.size = len(payload)
      tar.addfile(info, io.BytesIO(payload))
  target = str(tmp_path / 'extracted')
  osm_cache._safe_extract(archive, target)
  assert sorted(os.listdir(target)) == ['ways.bin']
  assert not os.path.exists(str(tmp_path / 'evil.bin'))
