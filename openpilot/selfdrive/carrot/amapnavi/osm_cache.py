#!/usr/bin/env python3
"""OSM 离线地图缓存（移植自 sunnypilot 的 mapd 下载机制，纯 amapnavi 模块）。

sunnypilot 的 ``download.go`` 把 OSM 路网数据预先切成 2°×2° 分片，地址是
``https://map-data.pfeifer.dev/offline/{lat}/{lon}.tar.gz``，网格起点为
``floor(coord / 2) * 2``。这里用同一套分片，按城市/自定义 bbox 下载到本地，
并提供缓存大小、分片清单和下载进度，供 :8088/nav_params 页面使用。

注意：这些分片是 **OSM 路网数据**（限速、路名、曲率，sunnypilot 的 mapd 消费），
不是用来画底图的栅格/矢量瓦片；carrot 目前只做离线缓存与状态展示。

所有函数都可以传入 cache_dir / state_path，方便在 PC 上做单元测试。
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request

TILE_URL = 'https://map-data.pfeifer.dev/offline/{lat}/{lon}.tar.gz'
REGIONS_URL = 'https://raw.githubusercontent.com/pfeiferj/openpilot-mapd/main/nation_bounding_boxes.json'
GROUP_DEGREES = 2
CACHE_DIR = '/data/carrot/state/osm_offline'
STATE_PATH = '/data/carrot/state/osm_download.json'
MANIFEST_NAME = 'manifest.json'
MAX_TILES_PER_DOWNLOAD = 800  # 放开全国下载（中国约 576 个 2° 分片）
MAX_TILE_BYTES = 256 * 1024 * 1024
MIN_FREE_BYTES = 300 * 1024 * 1024  # 下载过程中始终给 /data 留出余量

# (key, 名称, min_lon, min_lat, max_lon, max_lat)
CITY_REGIONS = [
  ('beijing', '北京', 116.20, 39.80, 116.60, 40.10),
  ('shanghai', '上海', 121.30, 31.10, 121.70, 31.40),
  ('guangzhou', '广州', 113.10, 23.00, 113.50, 23.30),
  # 旧 bbox 只到 114.20/22.70，不含坪山、龙岗、大鹏（坑梓在 114.36/22.75），
  # 裁出来的城市归档在那里一个瓦片都没有，只能回退到全国 z12 低精度底图。
  ('shenzhen', '深圳', 113.90, 22.45, 114.60, 22.85),
  ('hangzhou', '杭州', 120.05, 30.20, 120.30, 30.40),
  ('nanjing', '南京', 118.70, 32.00, 118.90, 32.20),
  ('chengdu', '成都', 104.00, 30.55, 104.20, 30.80),
  ('chongqing', '重庆', 106.45, 29.45, 106.65, 29.70),
  ('wuhan', '武汉', 114.20, 30.50, 114.45, 30.70),
  ('xian', '西安', 108.85, 34.20, 109.05, 34.40),
  ('suzhou', '苏州', 120.55, 31.25, 120.75, 31.45),
  ('tianjin', '天津', 117.10, 39.05, 117.35, 39.25),
  ('qingdao', '青岛', 120.30, 36.00, 120.50, 36.20),
  ('shenyang', '沈阳', 123.35, 41.70, 123.55, 41.90),
  ('changsha', '长沙', 112.90, 28.15, 113.10, 28.35),
  ('zhengzhou', '郑州', 113.55, 34.70, 113.75, 34.90),
  ('hefei', '合肥', 117.20, 31.75, 117.40, 31.95),
  ('fuzhou', '福州', 119.25, 26.00, 119.45, 26.20),
  ('kunming', '昆明', 102.65, 25.00, 102.85, 25.20),
  ('dalian', '大连', 121.55, 38.85, 121.75, 39.05),
  ('hongkong', '香港', 114.10, 22.25, 114.25, 22.40),
  ('seoul', '首尔', 126.90, 37.50, 127.10, 37.65),
  ('tokyo', '东京', 139.65, 35.65, 139.85, 35.80),
]

# 省级行政区外接矩形。离线底图瓦片面板用它整省裁 z15（省道、县乡道都在），
# 比单个城市更适合跨市/长途；大省体积请按页面上的估算值判断。
PROVINCE_REGIONS = [
  ('beijing', '北京市', 115.42, 39.44, 117.51, 41.06),
  ('tianjin', '天津市', 116.70, 38.55, 118.07, 40.25),
  ('hebei', '河北省', 113.45, 36.03, 119.85, 42.62),
  ('shanxi', '山西省', 110.24, 34.58, 114.55, 40.73),
  ('neimenggu', '内蒙古自治区', 97.20, 37.40, 126.07, 53.38),
  ('liaoning', '辽宁省', 118.84, 38.72, 125.79, 43.49),
  ('jilin', '吉林省', 121.64, 40.87, 131.32, 46.30),
  ('heilongjiang', '黑龙江省', 121.18, 43.42, 135.09, 53.56),
  ('shanghai', '上海市', 120.85, 30.67, 122.20, 31.88),
  ('jiangsu', '江苏省', 116.35, 30.75, 121.95, 35.33),
  ('zhejiang', '浙江省', 118.34, 27.04, 123.16, 31.18),
  ('anhui', '安徽省', 114.88, 29.40, 119.65, 34.65),
  ('fujian', '福建省', 115.85, 23.52, 120.72, 28.32),
  ('jiangxi', '江西省', 113.57, 24.49, 118.48, 30.08),
  ('shandong', '山东省', 114.79, 34.38, 122.71, 38.40),
  ('henan', '河南省', 110.36, 31.38, 116.65, 36.37),
  ('hubei', '湖北省', 108.36, 29.03, 116.13, 33.28),
  ('hunan', '湖南省', 108.79, 24.64, 114.26, 30.13),
  ('guangdong', '广东省', 109.66, 20.22, 117.31, 25.52),
  ('guangxi', '广西壮族自治区', 104.45, 20.90, 112.07, 26.39),
  ('hainan', '海南省', 108.61, 18.15, 111.06, 20.15),
  ('chongqing', '重庆市', 105.29, 28.16, 110.20, 32.21),
  ('sichuan', '四川省', 97.35, 26.05, 108.55, 34.32),
  ('guizhou', '贵州省', 103.60, 24.62, 109.59, 29.22),
  ('yunnan', '云南省', 97.53, 21.14, 106.20, 29.25),
  ('xizang', '西藏自治区', 78.39, 26.85, 99.12, 36.54),
  ('shaanxi', '陕西省', 105.49, 31.71, 111.25, 37.54),
  ('gansu', '甘肃省', 92.35, 32.52, 108.71, 42.80),
  ('qinghai', '青海省', 89.32, 31.60, 103.07, 39.21),
  ('ningxia', '宁夏回族自治区', 104.28, 35.24, 107.65, 39.38),
  ('xinjiang', '新疆维吾尔自治区', 73.50, 34.33, 96.40, 49.18),
  ('taiwan', '台湾省', 119.51, 21.90, 122.10, 25.30),
  ('xianggang', '香港特别行政区', 113.83, 22.15, 114.45, 22.57),
  ('aomen', '澳门特别行政区', 113.53, 22.10, 113.60, 22.22),
]

# 常用国家 bbox 摘自 sunnypilot 的 nation_bounding_boxes.json，内置在设备里，
# 页面打开时无需再联网拉清单（8088 是单线程 HTTPServer，不能被外部请求拖住）。
COUNTRY_REGIONS = {
  'CN': ('中国', (73.68, 18.20, 135.03, 53.46)),
  'KR': ('韩国', (126.12, 34.39, 129.47, 38.61)),
  'JP': ('日本', (129.41, 31.03, 145.54, 45.55)),
  'US': ('美国', (-125.0, 25.0, -66.96, 49.5)),
  'CA': ('加拿大', (-141.0, 41.68, -52.65, 73.23)),
  'DE': ('德国', (5.99, 47.30, 15.02, 54.98)),
  'FR': ('法国', (-5.0, 42.50, 9.56, 51.15)),
  'GB': ('英国', (-7.57, 49.96, 1.68, 58.64)),
  'AU': ('澳大利亚', (113.34, -43.63, 153.57, -10.67)),
  'IN': ('印度', (68.18, 7.97, 97.40, 35.49)),
  'TH': ('泰国', (97.38, 5.69, 105.59, 20.42)),
}

_LOCK = threading.Lock()
_ACTIVE_THREAD = None


class OsmError(Exception):
  pass


# ─────────────────────────────────────────────
# 网格
# ─────────────────────────────────────────────
def _snap(value: float) -> int:
  return int(math.floor(value / GROUP_DEGREES)) * GROUP_DEGREES


def tiles_for_bbox(bbox) -> list[tuple[int, int]]:
  """按 sunnypilot adjustedBounds() 的规则列出覆盖 bbox 的 (lat, lon) 分片。"""
  min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox)
  if not (-180 <= min_lon < max_lon <= 180 and -85 <= min_lat < max_lat <= 85):
    raise OsmError('经纬度范围无效')
  lo_lat, hi_lat = _snap(min_lat), _snap(max_lat)
  lo_lon, hi_lon = _snap(min_lon), _snap(max_lon)
  if max_lat > hi_lat:
    hi_lat += GROUP_DEGREES
  if max_lon > hi_lon:
    hi_lon += GROUP_DEGREES
  return [(lat, lon) for lat in range(lo_lat, hi_lat, GROUP_DEGREES)
                     for lon in range(lo_lon, hi_lon, GROUP_DEGREES)]


def tile_key(lat: int, lon: int) -> str:
  return f'{lat}/{lon}'


# ─────────────────────────────────────────────
# 区域清单
# ─────────────────────────────────────────────
def countries(timeout: float = 8.) -> dict[str, tuple[str, tuple]]:
  """内置国家清单（数据来自 sunnypilot 的 nation_bounding_boxes.json）。"""
  return dict(COUNTRY_REGIONS)


def regions(timeout: float = 8.) -> list[dict]:
  out = [{'key': key, 'name': name, 'bbox': list(bbox), 'tiles': len(tiles_for_bbox(bbox)), 'kind': 'city'}
         for key, name, *bbox in CITY_REGIONS]
  for key, name, *bbox in PROVINCE_REGIONS:
    try:
      out.append({'key': 'province:' + key, 'name': name, 'bbox': list(bbox),
                  'tiles': len(tiles_for_bbox(bbox)), 'kind': 'province'})
    except OsmError:
      continue
  for code, (name, bbox) in sorted(countries().items()):
    try:
      out.append({'key': 'country:' + code, 'name': name, 'bbox': list(bbox),
                  'tiles': len(tiles_for_bbox(bbox)), 'kind': 'country'})
    except OsmError:
      continue
  return out


def find_region(key: str, timeout: float = 8.) -> dict | None:
  return next((r for r in regions() if r['key'] == key), None)


# ─────────────────────────────────────────────
# 状态 / 缓存统计
# ─────────────────────────────────────────────
def _empty_progress() -> dict:
  return {'state': 'idle', 'region': '', 'total_files': 0, 'downloaded_files': 0,
          'current': '', 'bytes': 0, 'message': '', 'started_at': 0., 'finished_at': 0.}


def _read_state(state_path: str) -> dict:
  try:
    with open(state_path, 'r', encoding='utf-8') as f:
      data = json.load(f)
    return data if isinstance(data, dict) else {}
  except (OSError, ValueError):
    return {}


def _write_state(state_path: str, state: dict) -> None:
  os.makedirs(os.path.dirname(state_path), exist_ok=True)
  fd, temporary = tempfile.mkstemp(prefix='osm_', dir=os.path.dirname(state_path))
  try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
      json.dump(state, f, ensure_ascii=False)
    os.replace(temporary, state_path)
  finally:
    if os.path.exists(temporary):
      os.remove(temporary)


def _write_progress(state_path: str, progress: dict) -> None:
  state = _read_state(state_path)
  state['progress'] = progress
  _write_state(state_path, state)


def _dir_size(path: str) -> int:
  total = 0
  for root, _, files in os.walk(path):
    for name in files:
      try:
        total += os.path.getsize(os.path.join(root, name))
      except OSError:
        pass
  return total


def status(cache_dir: str = CACHE_DIR, state_path: str = STATE_PATH) -> dict:
  state = _read_state(state_path)
  manifest = state.get('manifest') or {}
  tiles = []
  if os.path.isdir(cache_dir):
    for lat in sorted(os.listdir(cache_dir)):
      lat_dir = os.path.join(cache_dir, lat)
      if not os.path.isdir(lat_dir) or not lat.lstrip('-').isdigit():
        continue
      for lon in sorted(os.listdir(lat_dir)):
        tile_dir = os.path.join(lat_dir, lon)
        if not os.path.isdir(tile_dir) or not lon.lstrip('-').isdigit():
          continue
        key = f'{lat}/{lon}'
        tiles.append({'key': key, 'bytes': _dir_size(tile_dir),
                      'regions': (manifest.get(key) or {}).get('regions', [])})
  progress = state.get('progress') or _empty_progress()
  # 设备重启会丢掉下载线程，把悬挂的 running 标成已中断。
  if progress.get('state') == 'running' and time.time() - float(progress.get('started_at') or 0) > 1800:
    progress = dict(progress, state='error', message='下载被中断（设备可能重启过）')
  return {'cache_dir': cache_dir, 'cache_bytes': sum(t['bytes'] for t in tiles),
          'tiles': tiles, 'progress': progress, 'max_tiles': MAX_TILES_PER_DOWNLOAD}


def clear_cache(cache_dir: str = CACHE_DIR, state_path: str = STATE_PATH) -> dict:
  with _LOCK:
    if _ACTIVE_THREAD is not None and _ACTIVE_THREAD.is_alive():
      raise OsmError('正在下载，请先等待完成')
    if os.path.isdir(cache_dir):
      shutil.rmtree(cache_dir, ignore_errors=True)
    _write_state(state_path, {'manifest': {}, 'progress': dict(_empty_progress(), message='缓存已清空')})
  return status(cache_dir, state_path)


# ─────────────────────────────────────────────
# 下载
# ─────────────────────────────────────────────
def _safe_extract(archive: str, target_dir: str) -> None:
  """只把普通文件解到 target_dir，杜绝 tar 成员里的 ../ 和绝对路径。"""
  os.makedirs(target_dir, exist_ok=True)
  with tarfile.open(archive, 'r:gz') as tar:
    for member in tar.getmembers():
      if not member.isfile():
        continue
      name = os.path.normpath(member.name).lstrip('/')
      if name.startswith('..') or os.path.isabs(name):
        continue
      destination = os.path.join(target_dir, os.path.basename(name))
      source = tar.extractfile(member)
      if source is None:
        continue
      with source, open(destination, 'wb') as out:
        shutil.copyfileobj(source, out)


def download_tile(lat: int, lon: int, cache_dir: str = CACHE_DIR, timeout: float = 60.) -> int:
  url = TILE_URL.format(lat=lat, lon=lon)
  os.makedirs(cache_dir, exist_ok=True)
  fd, temporary = tempfile.mkstemp(prefix='osm_tile_', suffix='.tar.gz', dir=cache_dir)
  os.close(fd)
  downloaded = 0
  try:
    with urllib.request.urlopen(url, timeout=timeout) as response, open(temporary, 'wb') as out:
      while True:
        chunk = response.read(65536)
        if not chunk:
          break
        downloaded += len(chunk)
        if downloaded > MAX_TILE_BYTES:
          raise OsmError(f'分片 {lat}/{lon} 超过大小上限')
        out.write(chunk)
    if downloaded < 100:
      raise OsmError(f'分片 {lat}/{lon} 内容异常')
    _safe_extract(temporary, os.path.join(cache_dir, str(lat), str(lon)))
  finally:
    if os.path.exists(temporary):
      os.remove(temporary)
  return downloaded


def _run_download(name: str, tiles: list[tuple[int, int]], cache_dir: str, state_path: str) -> None:
  progress = dict(_empty_progress(), state='running', region=name,
                  total_files=len(tiles), started_at=time.time())
  _write_progress(state_path, progress)
  state = _read_state(state_path)
  manifest = state.get('manifest') or {}
  os.makedirs(cache_dir, exist_ok=True)
  for index, (lat, lon) in enumerate(tiles):
    key = tile_key(lat, lon)
    progress['current'] = key
    progress['message'] = f'下载 {key}.tar.gz'
    _write_progress(state_path, progress)
    try:
      free_bytes = shutil.disk_usage(cache_dir).free
    except OSError:
      free_bytes = MIN_FREE_BYTES + 1
    if free_bytes < MIN_FREE_BYTES:
      progress['failed_files'] = len(tiles) - index
      progress['downloaded_files'] = index
      progress['message'] = '设备剩余空间不足，已停止下载（可先清空缓存）'
      break
    try:
      size = download_tile(lat, lon, cache_dir)
      progress['bytes'] += size
      entry = manifest.setdefault(key, {'regions': []})
      if name not in entry['regions']:
        entry['regions'].append(name)
      state = _read_state(state_path)
      state['manifest'] = manifest
      _write_state(state_path, state)
    except Exception as error:
      progress['failed_files'] = progress.get('failed_files', 0) + 1
      progress['message'] = f'{key} 下载失败: {error}'
    progress['downloaded_files'] = index + 1
    _write_progress(state_path, progress)
  progress['state'] = 'done' if not progress.get('failed_files') else 'error'
  progress['message'] = '下载完成' if progress['state'] == 'done' else '部分分片下载失败'
  progress['finished_at'] = time.time()
  _write_progress(state_path, progress)


def start_download(name: str, bbox, cache_dir: str = CACHE_DIR,
                   state_path: str = STATE_PATH) -> dict:
  """启动后台下载线程；同一时刻只允许一个任务。返回立即状态。"""
  global _ACTIVE_THREAD
  tiles = tiles_for_bbox(bbox)
  if not tiles:
    raise OsmError('区域没有覆盖到任何分片')
  if len(tiles) > MAX_TILES_PER_DOWNLOAD:
    raise OsmError(f'区域需要 {len(tiles)} 个分片，超过单次上限 {MAX_TILES_PER_DOWNLOAD}；请改用城市或更小范围')
  with _LOCK:
    if _ACTIVE_THREAD is not None and _ACTIVE_THREAD.is_alive():
      raise OsmError('已有下载任务在进行中')
    thread = threading.Thread(target=_run_download, args=(name, tiles, cache_dir, state_path),
                              name='osm-map-download', daemon=True)
    _ACTIVE_THREAD = thread
    thread.start()
  return {'started': True, 'region': name, 'tiles': len(tiles),
          'progress': dict(_empty_progress(), state='running', region=name,
                           total_files=len(tiles), started_at=time.time())}
