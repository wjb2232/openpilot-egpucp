#!/usr/bin/env python3
"""carrot: 离线 Protomaps/PMTiles 底图（OSM 矢量瓦片）。

数据源是 Protomaps 官方每日 planet 归档（ODbL，来自 OpenStreetMap），
用 ``pmtiles extract --bbox`` 按城市/全国裁出小归档，落到设备本地。
归档是标准 PMTiles v3 + gzip MVT，设备现有的 ``pmtiles.py`` reader 和
``vector_tile.decode_roads`` 都能直接读（roads layer 原生兼容），所以
``mapsd`` 只要把瓦片源换成本文件里的 ``LocalTiles``，导航渲染图就能
完全离线出图。

upstream 的 ``mapsd.py`` 只加两行（import + make_archive），
``tiles.py`` / ``renderer.py`` / ``mapbox_tiles.py`` 零改动。

本模块只用标准库：既被 mapsd 导入，也被 8088 的 amapnavi 页面导入，
不能拉起 numpy / zmq / msgq 等运行时依赖。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

STATIC_CACHE_DIR = '/data/carrot/state/nav_preview'
STATIC_MAX_BYTES = 2 * 1024 * 1024

ARCHIVE_DIR = '/data/carrot/state/nav_offline'
STATE_PATH = '/data/carrot/state/nav_offline.json'
PMTILES_BIN = '/data/carrot/bin/pmtiles'
DEFAULT_PLANET = 'https://build.protomaps.com/20261109.pmtiles'
CITY_ZOOM = 15          # 和 renderer.py 的 ZOOM 一致，导航渲染图的实际精度
NATIONAL_ZOOM = 12      # 全国 z15 有上千万瓦片，降到 z12 约 1 GB
PROVIDERS = ('amap', 'mapbox', 'osm')
MIN_FREE_BYTES = 300 * 1024 * 1024
PREVIEW_SIZE = 720          # 预览页 .frame 是正方形；三种底图统一输出该尺寸
MIN_COVERAGE = .25          # 覆盖率达标就采用该归档/层级，否则换更粗的层级或全国归档
MAX_PREVIEW_TILES = 256     # 与 renderer.view_tiles 一致
PREVIEW_LINE_BUDGET = 12000      # 整张预览图的道路线预算，按视野瓦片数分配到每瓦片
PREVIEW_ROAD_KINDS = ('highway', 'major_road', 'minor_road')  # 低细节时跳过其它小路

# 裁剪工具（go-pmtiles）部署：设备上没有预装，参数页按需下载安装。
PMTILES_RELEASE_API = 'https://api.github.com/repos/protomaps/go-pmtiles/releases/latest'
PMTILES_ASSET_RE = re.compile(r'^go-pmtiles_.*_Linux_(x86_64|arm64|armv6)\.tar\.gz$')
PMTILES_MAX_BYTES = 96 * 1024 * 1024   # 安装包实际不到 40 MB，只防异常响应
DOWNLOAD_CHUNK = 65536                 # 下载分块大小；进度按块落盘，断线可续传
# build.protomaps.com 首字节要 1~3 秒，是延迟受限而不是带宽受限：实测 4 连接
# 0.6 MB/s、16 连接 2.4 MB/s、32 连接不再涨，所以取 16。
DOWNLOAD_THREADS = 16

_LOCK = threading.Lock()
_ACTIVE: subprocess.Popen | None = None
_CLI_THREAD: threading.Thread | None = None
_CLI_URL_CACHE = {'url': '', 'checked_at': 0.}


class OfflineMapError(Exception):
  pass


def estimate_bytes(bbox, zoom: int) -> int:
  """下载前估算裁剪产物大小，供参数页提示（避免点了 1 GB 才知道）。

  系数来自江苏省 dry-run：z15 165 MB / z14 88 MB / z13 52 MB，瓦片数每级
  /4 但低层级单片更满，总量约 /2，所以每降一级把单片系数翻倍。
  城区偏准、西部稀疏区偏高，宁可高估一点。
  """
  min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox)
  n = 1 << int(zoom)

  def mercator_y(lat):
    lat = max(-85., min(85., lat))
    return (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2

  cols = max(0., (max_lon - min_lon) / 360 * n)
  rows = max(0., abs(mercator_y(max_lat) - mercator_y(min_lat)) * n)
  per_tile = 820 * (2 ** max(0, CITY_ZOOM - int(zoom)))
  return int(cols * rows * 0.8 * per_tile * 1.15)


# ─────────────────────────────────────────────
# 状态
# ─────────────────────────────────────────────
def _empty_progress() -> dict:
  return {'state': 'idle', 'name': '', 'percent': 0, 'bytes': 0, 'total_bytes': 0,
          'message': '', 'started_at': 0., 'finished_at': 0.}


def read_state(state_path: str = STATE_PATH) -> dict:
  try:
    with open(state_path, 'r', encoding='utf-8') as f:
      data = json.load(f)
    return data if isinstance(data, dict) else {}
  except (OSError, ValueError):
    return {}


def write_state(state: dict, state_path: str = STATE_PATH) -> None:
  os.makedirs(os.path.dirname(state_path), exist_ok=True)
  fd, temporary = tempfile.mkstemp(prefix='nav_offline_', dir=os.path.dirname(state_path))
  try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
      json.dump(state, f, ensure_ascii=False)
    os.replace(temporary, state_path)
  finally:
    if os.path.exists(temporary):
      os.remove(temporary)


def _save_progress(progress: dict, state_path: str = STATE_PATH) -> None:
  state = read_state(state_path)
  state['progress'] = progress
  write_state(state, state_path)


def get_provider(state_path: str = STATE_PATH) -> str:
  value = read_state(state_path).get('provider', 'amap')
  return value if value in PROVIDERS else 'amap'


def set_provider(value: str, state_path: str = STATE_PATH) -> str:
  if value not in PROVIDERS:
    raise OfflineMapError(f'未知底图来源: {value}')
  state = read_state(state_path)
  state['provider'] = value
  write_state(state, state_path)
  return value


def planet_url(state_path: str = STATE_PATH) -> str:
  return read_state(state_path).get('planet_url') or DEFAULT_PLANET


# ─────────────────────────────────────────────
# 归档
# ─────────────────────────────────────────────
class LocalTiles:
  """PMTiles 的字节范围源，直接读本地归档；接口与 RemoteTiles 一致。"""

  def __init__(self, path: str):
    self._f = open(path, 'rb')
    self.size = os.path.getsize(path)

  def read(self, offset: int, length: int) -> bytes:
    self._f.seek(offset)
    return self._f.read(length)

  def prefetch(self, ranges) -> None:
    pass

  def close(self) -> None:
    self._f.close()


def list_archives(archive_dir: str = ARCHIVE_DIR) -> list[dict]:
  result = []
  if os.path.isdir(archive_dir):
    for name in sorted(os.listdir(archive_dir)):
      if not name.endswith('.pmtiles'):
        continue
      path = os.path.join(archive_dir, name)
      if not os.path.isfile(path):
        continue
      result.append({'name': name, 'bytes': os.path.getsize(path),
                     'mtime': os.path.getmtime(path)})
  return result


def active_path(state_path: str = STATE_PATH, archive_dir: str = ARCHIVE_DIR) -> str | None:
  archives = list_archives(archive_dir)
  if not archives:
    return None
  wanted = read_state(state_path).get('active')
  for item in archives:
    if item['name'] == wanted:
      return os.path.join(archive_dir, item['name'])
  return os.path.join(archive_dir, archives[-1]['name'])


def set_active(name: str, state_path: str = STATE_PATH, archive_dir: str = ARCHIVE_DIR) -> str:
  if not any(item['name'] == name for item in list_archives(archive_dir)):
    raise OfflineMapError('归档不存在')
  state = read_state(state_path)
  state['active'] = name
  write_state(state, state_path)
  return name


def delete_archive(name: str, state_path: str = STATE_PATH, archive_dir: str = ARCHIVE_DIR) -> None:
  with _LOCK:
    if _ACTIVE is not None and _ACTIVE.poll() is None:
      raise OfflineMapError('正在下载，请先等待完成')
    path = os.path.join(archive_dir, os.path.basename(name))
    if os.path.isfile(path):
      os.remove(path)
    state = read_state(state_path)
    if state.get('active') == os.path.basename(name):
      state.pop('active', None)
    write_state(state, state_path)


def make_archive(mapbox_token, MapboxTiles, PMTiles, RemoteTiles,
                 state_path: str = STATE_PATH, archive_dir: str = ARCHIVE_DIR):
  """mapsd 的唯一接入点：按页面选择的底图来源挑瓦片源。

  * osm    -> 本地 PMTiles 归档（完全离线；没下载过时回退在线）
  * amap   -> 高德没有 MVT 瓦片，车机渲染图回退 Mapbox / PMTiles
  * mapbox -> online Mapbox Streets v8
  """
  provider = get_provider(state_path)
  if provider == 'osm':
    path = active_path(state_path, archive_dir)
    if path:
      try:
        return PMTiles(LocalTiles(path))
      except Exception:
        pass  # 归档损坏时退回在线，不让 mapsd 起不来
  if mapbox_token:
    return MapboxTiles(mapbox_token)
  return PMTiles(RemoteTiles())


def status(archive_dir: str = ARCHIVE_DIR, state_path: str = STATE_PATH) -> dict:
  state = read_state(state_path)
  archives = list_archives(archive_dir)
  progress = state.get('progress') or _empty_progress()
  if progress.get('state') == 'running' and time.time() - float(progress.get('started_at') or 0) > 3600:
    progress = dict(progress, state='error', message='下载被中断（设备可能重启过）')
  cli = state.get('cli') or {}
  # 安装线程随进程消失，超时未更新的 running 一律当失败，避免页面一直转圈。
  if cli.get('state') == 'running' and time.time() - float(cli.get('started_at') or 0) > 900:
    cli = dict(cli, state='error', message='安装被中断（设备可能重启过）')
  try:
    free = shutil.disk_usage(archive_dir if os.path.isdir(archive_dir) else '/data').free
  except OSError:
    free = 0
  return {'provider': get_provider(state_path), 'providers': list(PROVIDERS),
          'active': state.get('active') or (archives[-1]['name'] if archives else ''),
          'archives': archives, 'total_bytes': sum(a['bytes'] for a in archives),
          'free_bytes': free, 'progress': progress,
          'cli_ready': pmtiles_installed(),
          'cli_progress': cli, 'cli_arch': cli_arch(),
          'cli_supported': bool(cli_arch()),
          'planet_url': planet_url(state_path),
          'city_zoom': CITY_ZOOM, 'national_zoom': NATIONAL_ZOOM}


# ─────────────────────────────────────────────
# 裁剪工具（go-pmtiles CLI）
# ─────────────────────────────────────────────
_ARCH_ALIASES = {'x86_64': 'x86_64', 'amd64': 'x86_64', 'x64': 'x86_64',
                 'aarch64': 'arm64', 'arm64': 'arm64', 'armv8l': 'arm64',
                 'armv6l': 'armv6', 'armv7l': 'armv6'}


def cli_arch(machine: str | None = None) -> str:
  """设备 CPU 架构 -> release 包里的架构后缀；空串表示没有对应安装包。"""
  return _ARCH_ALIASES.get((machine if machine is not None else platform.machine()).strip().lower(), '')


def pmtiles_installed(bin_path: str | None = None) -> bool:
  return os.access(bin_path or PMTILES_BIN, os.X_OK)


def pick_cli_asset(urls, arch: str) -> str:
  """从 release 的资产列表里挑出该架构的 Linux tar.gz，跳过 Windows/Darwin。"""
  if not arch:
    return ''
  for url in urls:
    name = os.path.basename(urllib.parse.urlparse(url).path)
    match = PMTILES_ASSET_RE.match(name)
    if match and match.group(1) == arch:
      return url
  return ''


def cli_download_url(timeout: float = 10., refresh: bool = False) -> str:
  """最新 release 里对应架构的下载地址；查不到返回空串（结果缓存一小时）。"""
  if not refresh and _CLI_URL_CACHE['url'] and time.time() - _CLI_URL_CACHE['checked_at'] < 3600:
    return _CLI_URL_CACHE['url']
  arch = cli_arch()
  if not arch:
    return ''
  request = urllib.request.Request(PMTILES_RELEASE_API, headers={
    'User-Agent': 'carrot-nav', 'Accept': 'application/vnd.github+json'})
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      body = response.read(2 * 1024 * 1024)
    assets = json.loads(body).get('assets') or []
  except (OSError, ValueError, urllib.error.URLError):
    return ''
  url = pick_cli_asset([str(item.get('browser_download_url') or '')
                        for item in assets if isinstance(item, dict)], arch)
  _CLI_URL_CACHE.update(url=url, checked_at=time.time())
  return url


def _download_with_resume(url: str, target: str, progress: dict | None = None,
                          timeout: float = 60.) -> int:
  """分块写 target；target 已有内容时用 Range 从断点续传。

  车机常年 4G，几十 MB 的包中途掉线很常见，所以按块落盘：重跑时直接
  从已有长度接着下，服务端不支持 Range（回 200）才从头再来。
  """
  have = os.path.getsize(target) if os.path.isfile(target) else 0
  request = urllib.request.Request(url, headers={'User-Agent': 'carrot-nav'})
  if have:
    request.add_header('Range', f'bytes={have}-')
  try:
    response = urllib.request.urlopen(request, timeout=timeout)
  except urllib.error.HTTPError as error:
    if error.code == 416 and have:
      return have  # 服务端认为已经下完了
    raise
  with response:
    total = have + int(response.headers.get('Content-Length') or 0)
    if getattr(response, 'status', 200) != 206 and have:
      have, total = 0, int(response.headers.get('Content-Length') or 0)
    with open(target, 'ab' if have else 'wb') as out:
      if progress is not None:
        progress.update(bytes=have, total_bytes=total)
      while True:
        chunk = response.read(DOWNLOAD_CHUNK)
        if not chunk:
          break
        have += len(chunk)
        if have > PMTILES_MAX_BYTES:
          raise OfflineMapError('裁剪工具安装包大小异常')
        out.write(chunk)
        if progress is not None:
          progress['bytes'] = have
          progress['percent'] = min(99, int(have * 100 / total)) if total else 0
  return have


def _verify_cli(path: str) -> None:
  """装完先跑一次 --help：架构不匹配时 exec 会直接失败。"""
  try:
    result = subprocess.run([path, 'extract', '--help'], capture_output=True, timeout=15)
  except (OSError, subprocess.SubprocessError) as error:
    raise OfflineMapError(f'下载的 pmtiles 无法运行: {error}')
  if result.returncode != 0:
    raise OfflineMapError('下载的 pmtiles 无法运行（可能与设备架构不匹配）')


def _install_cli_archive(archive: str, bin_path: str) -> None:
  """从 release 的 tar.gz 里取出 pmtiles 可执行文件，落到 bin_path。"""
  staged = bin_path + '.new'
  try:
    with tarfile.open(archive, 'r:gz') as tar:
      member = next((item for item in tar.getmembers()
                     if item.isfile() and os.path.basename(item.name) == 'pmtiles'), None)
      if member is None:
        raise OfflineMapError('安装包里没有 pmtiles')
      source = tar.extractfile(member)
      if source is None:
        raise OfflineMapError('安装包内容异常')
      with source, open(staged, 'wb') as out:
        shutil.copyfileobj(source, out, DOWNLOAD_CHUNK)
    os.chmod(staged, 0o755)
    _verify_cli(staged)
    os.replace(staged, bin_path)
  except Exception:
    if os.path.exists(staged):
      os.remove(staged)
    raise


def _save_cli_progress(progress: dict, state_path: str) -> None:
  state = read_state(state_path)
  state['cli'] = progress
  write_state(state, state_path)


def _prepare_partial(archive: str, url: str) -> None:
  """半包只对同一个 URL 有效；换了版本就把上一版的残留删掉，避免拼错包。"""
  marker = archive + '.url'
  try:
    with open(marker, 'r', encoding='utf-8') as f:
      same = f.read().strip() == url
  except OSError:
    same = False
  if same:
    return
  for path in (archive, marker):
    if os.path.exists(path):
      os.remove(path)
  with open(marker, 'w', encoding='utf-8') as f:
    f.write(url)


def install_cli(bin_path: str | None = None, state_path: str = STATE_PATH) -> dict:
  """下载并安装裁剪工具（阻塞式；进度写进 state 供页面轮询）。"""
  target = bin_path or PMTILES_BIN
  progress = dict(_empty_progress(), state='running', name='pmtiles',
                  started_at=time.time(), message='正在查询最新版本')
  _save_cli_progress(progress, state_path)
  bin_dir = os.path.dirname(target) or '.'
  archive = os.path.join(bin_dir, '.pmtiles-install.tar.gz')
  try:
    url = cli_download_url()
    if not url:
      raise OfflineMapError('无法获取 pmtiles 下载地址（设备无网络或架构不受支持）')
    os.makedirs(bin_dir, exist_ok=True)
    _prepare_partial(archive, url)
    progress['message'] = '正在下载裁剪工具'
    _save_cli_progress(progress, state_path)
    size = _download_with_resume(url, archive, progress)
    if size < 1024:
      raise OfflineMapError('下载的安装包不完整')
    progress['message'] = '正在安装裁剪工具'
    _save_cli_progress(progress, state_path)
    _install_cli_archive(archive, target)
    progress.update(state='done', percent=100, bytes=size, message='裁剪工具已安装')
  except Exception as error:
    # 半包留着，下次点安装从断点续传；只有装成功才删。
    progress.update(state='error', message=str(error))
  finally:
    if progress['state'] == 'done':
      for path in (archive, archive + '.url'):
        if os.path.exists(path):
          os.remove(path)
    progress['finished_at'] = time.time()
    _save_cli_progress(progress, state_path)
  return progress


def start_cli_install(bin_path: str | None = None, state_path: str = STATE_PATH) -> dict:
  """后台安装裁剪工具；同一时刻只允许装一个。"""
  global _CLI_THREAD
  if not cli_arch():
    raise OfflineMapError(f'当前平台 {platform.machine()} 没有对应的 pmtiles 安装包')
  with _LOCK:
    if _CLI_THREAD is not None and _CLI_THREAD.is_alive():
      raise OfflineMapError('正在安装裁剪工具，请稍候')
    thread = threading.Thread(target=install_cli, args=(bin_path, state_path),
                              name='offline-map-cli', daemon=True)
    _CLI_THREAD = thread
    thread.start()
  return {'started': True, 'progress': dict(_empty_progress(), state='running', name='pmtiles',
                                            started_at=time.time(), message='正在查询最新版本')}


# ─────────────────────────────────────────────
# 下载（pmtiles extract）
# ─────────────────────────────────────────────
def _safe_name(name: str) -> str:
  # \w 保留中文，避免「全国」被清成空串。
  cleaned = re.sub(r'[^\w.-]+', '_', name).strip(' ._')[:64]
  return cleaned or 'region'


def _parse_progress(line: str, progress: dict) -> None:
  match = re.search(r'fetching chunks\s+(\d+)%', line)
  if match:
    progress['percent'] = min(100, int(match.group(1)))
  sizes = re.search(r'\(([\d.]+)\s*/\s*([\d.]+)\s*(MB|GB|kB|B)', line)
  if sizes:
    unit = {'B': 1, 'kB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3}[sizes.group(3)]
    progress['bytes'] = int(float(sizes.group(1)) * unit)
    progress['total_bytes'] = int(float(sizes.group(2)) * unit)


def _run_extract(name: str, bbox, zoom: int, output: str,
                 archive_dir: str, state_path: str) -> None:
  progress = dict(_empty_progress(), state='running', name=name, started_at=time.time(),
                  message='正在裁剪 Protomaps 归档')
  _save_progress(progress, state_path)
  temporary = output + '.part'
  if os.path.exists(temporary):
    os.remove(temporary)
  bbox_arg = ','.join(str(float(v)) for v in bbox)
  cmd = [PMTILES_BIN, 'extract', planet_url(state_path), temporary,
         f'--bbox={bbox_arg}', f'--minzoom={zoom}', f'--maxzoom={zoom}',
         f'--download-threads={DOWNLOAD_THREADS}']
  error_tail = []
  stopped_for_space = False
  try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors='replace', bufsize=1)
    with _LOCK:
      global _ACTIVE
      _ACTIVE = proc
    buffer = ''
    while True:
      char = proc.stdout.read(1)
      if not char:
        break
      if char in '\r\n':
        if buffer.strip():
          previous = progress['percent']
          _parse_progress(buffer, progress)
          error_tail.append(buffer.strip()[-200:])
          error_tail = error_tail[-5:]
          if progress['percent'] != previous:
            progress['message'] = f'裁剪中 {progress["percent"]}%'
            _save_progress(progress, state_path)
            # 归档是边下边写的，空间告急就提前收手，别把 /data 写满
            try:
              if shutil.disk_usage(archive_dir).free < MIN_FREE_BYTES:
                stopped_for_space = True
                error_tail.append('设备剩余空间不足')
                proc.kill()
            except OSError:
              pass
        buffer = ''
      else:
        buffer += char
    returncode = proc.wait()
    if stopped_for_space:
      raise OfflineMapError('设备剩余空间不足，下载已停止（可先删除旧归档）')
    if returncode != 0 or not os.path.isfile(temporary):
      if returncode is not None and returncode < 0:
        raise OfflineMapError('下载被中断（进程被外部终止）')
      raise OfflineMapError(f'pmtiles 裁剪失败: {" | ".join(error_tail[-2:])}')
    os.replace(temporary, output)
    state = read_state(state_path)
    state['active'] = os.path.basename(output)
    write_state(state, state_path)
    progress['state'] = 'done'
    progress['percent'] = 100
    progress['bytes'] = os.path.getsize(output)
    progress['total_bytes'] = progress['bytes']
    progress['message'] = '下载完成，可在预览界面选 OSM 地图使用'
  except Exception as error:
    progress['state'] = 'error'
    progress['message'] = str(error)
    if os.path.exists(temporary):
      os.remove(temporary)
  finally:
    progress['finished_at'] = time.time()
    _save_progress(progress, state_path)
    with _LOCK:
      _ACTIVE = None


def start_download(name: str, bbox, zoom: int | None = None,
                   archive_dir: str = ARCHIVE_DIR, state_path: str = STATE_PATH) -> dict:
  """后台裁剪一个区域。城市用 z15，全国用 z12。"""
  global _ACTIVE
  if not pmtiles_installed():
    raise OfflineMapError('设备缺少 pmtiles 裁剪工具，请先在参数页点「安装裁剪工具」')
  if len(bbox) != 4:
    raise OfflineMapError('bbox 需要四个值: min_lon,min_lat,max_lon,max_lat')
  min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox)
  if not (-180 <= min_lon < max_lon <= 180 and -85 <= min_lat < max_lat <= 85):
    raise OfflineMapError('经纬度范围无效')
  if zoom is None:
    zoom = NATIONAL_ZOOM if (max_lon - min_lon) * (max_lat - min_lat) > 20 else CITY_ZOOM
  if zoom not in range(0, 16):
    raise OfflineMapError('zoom 超出范围')
  os.makedirs(archive_dir, exist_ok=True)
  if shutil.disk_usage(archive_dir).free < MIN_FREE_BYTES:
    raise OfflineMapError('设备剩余空间不足 300 MB')
  with _LOCK:
    if _ACTIVE is not None and _ACTIVE.poll() is None:
      raise OfflineMapError('已有下载任务在进行中')
    output = os.path.join(archive_dir, _safe_name(name) + '.pmtiles')
    thread = threading.Thread(target=_run_extract,
                              args=(name, (min_lon, min_lat, max_lon, max_lat), zoom,
                                    output, archive_dir, state_path),
                              name='offline-map-extract', daemon=True)
    thread.start()
  return {'started': True, 'name': name, 'zoom': zoom,
          'progress': dict(_empty_progress(), state='running', name=name,
                           started_at=time.time())}


# ─────────────────────────────────────────────
# 离线底图预览（纯标准库 PNG，不依赖 numpy / PIL）
# ─────────────────────────────────────────────
def _png(width: int, height: int, rgb: bytearray) -> bytes:
  def chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack('>I', len(data)) + kind + data
            + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
  raw = b''.join(b'\x00' + bytes(rgb[y * width * 3:(y + 1) * width * 3]) for y in range(height))
  return (b'\x89PNG\r\n\x1a\n'
          + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
          + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def _line(buf: bytearray, width: int, height: int, a, b, color: tuple, thickness: int = 1) -> None:
  x0, y0 = a
  x1, y1 = b
  steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
  for i in range(steps + 1):
    x = int(x0 + (x1 - x0) * i / steps)
    y = int(y0 + (y1 - y0) * i / steps)
    for dy in range(-(thickness // 2), thickness // 2 + 1):
      for dx in range(-(thickness // 2), thickness // 2 + 1):
        px, py = x + dx, y + dy
        if 0 <= px < width and 0 <= py < height:
          index = (py * width + px) * 3
          buf[index:index + 3] = bytes(color)


def mercator(lon: float, lat: float) -> tuple[float, float]:
  return ((lon + 180) / 360,
          (1 - math.asinh(math.tan(math.radians(max(-85., min(85., lat))))) / math.pi) / 2)


def _varint(data: bytes, offset: int) -> tuple[int, int]:
  value = 0
  for shift in range(0, 70, 7):
    if offset >= len(data):
      raise ValueError('Truncated varint')
    byte = data[offset]
    offset += 1
    value |= (byte & 127) << shift
    if byte < 128:
      return value, offset
  raise ValueError('Varint exceeds 64 bits')


def _fields(data: bytes):
  offset = 0
  while offset < len(data):
    tag, offset = _varint(data, offset)
    number, wire = tag >> 3, tag & 7
    if number == 0:
      raise ValueError('Invalid protobuf field')
    if wire == 0:
      value, offset = _varint(data, offset)
    elif wire in (1, 2, 5):
      if wire == 2:
        length, offset = _varint(data, offset)
      else:
        length = 8 if wire == 1 else 4
      if offset + length > len(data):
        raise ValueError('Truncated protobuf field')
      value = data[offset:offset + length]
      offset += length
    else:
      raise ValueError('Unsupported protobuf wire type')
    yield number, wire, value


def _integers(data: bytes) -> list[int]:
  result, offset = [], 0
  while offset < len(data):
    value, offset = _varint(data, offset)
    result.append(value)
  return result


def _decode_value(data: bytes):
  for number, wire, value in _fields(data):
    if number == 1 and wire == 2:
      return value.decode('utf-8')
    if number == 7 and wire == 0:
      return bool(value)
  return None


def _mvt_road_lines(data: bytes, max_lines: int = 0, kinds=None):
  """从 Protomaps MVT 的 roads layer 取出折线（纯标准库，不导入 numpy）。

  ``max_lines`` 给低分辨率预览用：解析到足够多的路就停，不用把整块瓦片
  几千个 feature 全解一遍。``kinds`` 可只保留主要道路，跳过小路几何的解码。
  """
  def decode_lines(commands):
    lines, line, x, y, offset = [], [], 0, 0, 0
    while offset < len(commands):
      command = commands[offset]
      offset += 1
      kind, count = command & 7, command >> 3
      if kind not in (1, 2) or count == 0 or offset + 2 * count > len(commands):
        break
      for _ in range(count):
        x += (commands[offset] >> 1) ^ -(commands[offset] & 1)
        y += (commands[offset + 1] >> 1) ^ -(commands[offset + 1] & 1)
        offset += 2
        if kind == 1:
          if len(line) >= 2:
            lines.append(line)
          line = []
        line.append((x, y))
    if len(line) >= 2:
      lines.append(line)
    return lines

  for number, wire, layer in _fields(data):
    if number != 3 or wire != 2:
      continue
    layer_fields = list(_fields(layer))
    name = next((v.decode('utf-8') for n, w, v in layer_fields if n == 1 and w == 2), '')
    if name != 'roads':
      continue
    extent = next((v for n, w, v in layer_fields if n == 5 and w == 0), 4096)
    keys = [v.decode('utf-8') for n, w, v in layer_fields if n == 3 and w == 2]
    values = [_decode_value(v) for n, w, v in layer_fields if n == 4 and w == 2]
    emitted = 0
    for n, w, feature in layer_fields:
      if n != 2 or w != 2:
        continue
      tags, geometry_type, raw_geometry = [], 0, None
      for fn, fw, fv in _fields(feature):
        if fn == 2:
          if fw == 2:
            tags.extend(_integers(fv))
          elif fw == 0:
            tags.append(fv)
        elif fn == 3 and fw == 0:
          geometry_type = fv
        elif fn == 4 and fw == 2:
          raw_geometry = fv  # 先不解码几何，等道路等级判断完再说
      if geometry_type != 2 or len(tags) % 2 or raw_geometry is None:
        continue
      properties = {}
      for i in range(0, len(tags), 2):
        if tags[i] < len(keys) and tags[i + 1] < len(values):
          properties[keys[tags[i]]] = values[tags[i + 1]]
      kind = properties.get('kind', '')
      if kind not in ('highway', 'major_road', 'minor_road', 'other'):
        continue
      if kinds is not None and kind not in kinds:
        continue
      width = {'highway': 3, 'major_road': 2}.get(kind, 1)
      for points in decode_lines(_integers(raw_geometry)):
        yield [(x / extent, y / extent) for x, y in points], width
        emitted += 1
        if max_lines and emitted >= max_lines:
          return


_PMTILES_CLASS = None


def _pmtiles_class():
  """按需加载设备自带的 reader，避免 8088 页面进程引入其它模块依赖。"""
  global _PMTILES_CLASS
  if _PMTILES_CLASS is None:
    spec = importlib.util.spec_from_file_location(
      '_carrot_pmtiles', os.path.join(os.path.dirname(__file__), 'pmtiles.py'))
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    _PMTILES_CLASS = pm.PMTiles
  return _PMTILES_CLASS


def _candidate_archives(state_path: str, archive_dir: str) -> list[str]:
  """选中的归档优先，其余按体积升序：城市 z15 在前，全国 z12 兜底。"""
  active = active_path(state_path, archive_dir)
  active_name = os.path.basename(active) if active else ''
  others = sorted((item for item in list_archives(archive_dir) if item['name'] != active_name),
                  key=lambda item: item['bytes'])
  return ([active] if active else []) + [os.path.join(archive_dir, item['name']) for item in others]


def _zoom_has_tiles(archive, zoom: int, xy) -> bool:
  """廉价探针：确认该层级有瓦片，避免对空层级做几百次无效读取。"""
  n = 1 << zoom
  xs, ys = [x for x, _ in xy], [y for _, y in xy]
  samples = ((sum(xs) / len(xs), sum(ys) / len(ys)), (xs[0], ys[0]), (xs[-1], ys[-1]))
  for x, y in samples:
    tx, ty = int(x * n), int(y * n)
    if 0 <= tx < n and 0 <= ty < n and archive.get(zoom, tx, ty):
      return True
  return False


def _render_zoom(archive, zoom: int, xy, width: int, height: int):
  """把整条路线 fit 进正方形画布，返回 (瓦片覆盖率, PNG)。"""
  n = 1 << zoom
  tile_px = 256
  gx = [x * n * tile_px for x, _ in xy]
  gy = [y * n * tile_px for _, y in xy]
  min_x, max_x, min_y, max_y = min(gx), max(gx), min(gy), max(gy)
  center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
  span_x, span_y = max(max_x - min_x, 1.), max(max_y - min_y, 1.)
  # 四周留 14% 余量；scale 是 PMTiles 源像素 -> 屏幕像素的倍数。
  scale = min(width * .72 / span_x, height * .72 / span_y)
  scale = max(.002, min(scale, 8.))

  def bounds():
    half_w, half_h = width / (2 * scale), height / (2 * scale)
    return (max(0, int((center_x - half_w) // tile_px) - 1),
            min(n - 1, int((center_x + half_w) // tile_px) + 1),
            max(0, int((center_y - half_h) // tile_px) - 1),
            min(n - 1, int((center_y + half_h) // tile_px) + 1))

  x0, x1, y0, y1 = bounds()
  # 覆盖率按完整视野统计。不能靠放大 scale 来减少瓦片数——那等于放大地图，
  # 会把路线两端裁出画布，正是之前「比例不对」的根因之一。
  full_expected = (x1 - x0 + 1) * (y1 - y0 + 1)
  # 视野里瓦片越多，每瓦片分到的线数越少：城市短路线画全路网，跨城长路线
  # 自动降细节；全国 z12 归档瓦片少，也能把它自带的道路全画出来。
  cap = max(24, min(240, PREVIEW_LINE_BUDGET // max(1, full_expected)))
  kinds = None if cap >= 120 else PREVIEW_ROAD_KINDS
  if full_expected > MAX_PREVIEW_TILES:
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    half = int(math.sqrt(MAX_PREVIEW_TILES)) // 2
    x0, x1 = max(0, cx - half), min(n - 1, cx + half - 1)
    y0, y1 = max(0, cy - half), min(n - 1, cy + half - 1)

  def to_screen(px, py):
    return ((px - center_x) * scale + width / 2,
            (py - center_y) * scale + height / 2)

  buf = bytearray(b'\x1a\x21\x2b' * (width * height))
  tiles_loaded = roads = 0
  for tx in range(x0, x1 + 1):
    for ty in range(y0, y1 + 1):
      tile = archive.get(zoom, tx, ty)
      if not tile:
        continue
      tiles_loaded += 1
      try:
        for line, thickness in _mvt_road_lines(tile, cap, kinds):
          roads += 1
          # 一个瓦片在预览图里只有几十像素，很多 MVT 点会落在同一个像素上；
          # 先按整数像素去重，再丢掉整条在画布外的线，能省掉大部分 _line 调用。
          screen, last = [], None
          for px, py in line:
            point = to_screen((tx + px) * tile_px, (ty + py) * tile_px)
            ip = (int(point[0]), int(point[1]))
            if ip != last:
              screen.append(point)
              last = ip
          if len(screen) < 2:
            continue
          xs = [p[0] for p in screen]
          ys = [p[1] for p in screen]
          if max(xs) < 0 or min(xs) > width or max(ys) < 0 or min(ys) > height:
            continue
          for a, b in zip(screen, screen[1:]):
            _line(buf, width, height, a, b, (95, 105, 117), thickness)
      except (ValueError, IndexError, KeyError, struct.error, zlib.error):
        continue
  route = [to_screen(px, py) for px, py in zip(gx, gy)]
  for a, b in zip(route, route[1:]):
    _line(buf, width, height, a, b, (255, 140, 32), 5)
  if route:
    for point, color in ((route[0], (60, 200, 90)), (route[-1], (230, 70, 70))):
      for dx in range(-5, 6):
        for dy in range(-5, 6):
          if dx * dx + dy * dy <= 25:
            px, py = int(point[0] + dx), int(point[1] + dy)
            if 0 <= px < width and 0 <= py < height:
              buf[(py * width + px) * 3:(py * width + px) * 3 + 3] = bytes(color)
  if not tiles_loaded or not roads:
    return 0., None
  return min(1., tiles_loaded / max(1, full_expected)), _png(width, height, buf)


def _render_archive(path: str, points, width: int, height: int):
  """单个归档：优先最高 zoom，缺瓦片时自动降级（全国归档只有 z12）。"""
  archive = _pmtiles_class()(LocalTiles(path))
  try:
    xy = [mercator(lon, lat) for lon, lat in points]
    top = min(CITY_ZOOM, int(archive.max_zoom))
    bottom = max(int(archive.min_zoom), top - 4)
    best = (0., None)
    for zoom in range(top, bottom - 1, -1):
      if not _zoom_has_tiles(archive, zoom, xy):
        continue
      coverage, png = _render_zoom(archive, zoom, xy, width, height)
      if png is not None and coverage >= MIN_COVERAGE:
        return coverage, png
      if png is not None and coverage > best[0]:
        best = (coverage, png)
    return best
  finally:
    archive.close()


def render_preview(points, width: int = PREVIEW_SIZE, height: int = PREVIEW_SIZE,
                   state_path: str = STATE_PATH, archive_dir: str = ARCHIVE_DIR) -> bytes:
  """按预览容器比例出图，自动 fit 整条路线；城市归档不覆盖时回退全国归档。"""
  width = max(200, min(1200, int(width)))
  height = max(200, min(1200, int(height)))
  xy = [(float(point[0]), float(point[1])) for point in points]
  if len(xy) < 2:
    raise OfflineMapError('缺少路线点')
  paths = _candidate_archives(state_path, archive_dir)
  if not paths:
    raise OfflineMapError('还没有离线底图归档，请先在参数页下载')
  best = (0., None)
  for path in paths:
    try:
      coverage, png = _render_archive(path, xy, width, height)
    except (OSError, ValueError, KeyError, IndexError, struct.error, zlib.error):
      continue  # 单个归档损坏/不兼容，继续试下一个
    if png is not None and coverage >= MIN_COVERAGE:
      return png
    if png is not None and coverage > best[0]:
      best = (coverage, png)
  if best[1] is None:
    raise OfflineMapError('离线归档没有覆盖这条路线：请在参数页下载对应城市，或把「使用归档」切到全国')
  return best[1]


# ─────────────────────────────────────────────
# Mapbox 静态底图（预览界面第二种在线来源）
# ─────────────────────────────────────────────
def encode_polyline(points) -> str:
  """Google encoded polyline（Mapbox Static API 的 path 参数）。"""
  def encode_value(value: int) -> str:
    value <<= 1
    if value < 0:
      value = ~value
    chars = []
    while value >= 0x20:
      chars.append(chr((0x20 | (value & 0x1f)) + 63))
      value >>= 5
    chars.append(chr(value + 63))
    return ''.join(chars)

  out, last_lat, last_lon = [], 0, 0
  for lon, lat in points:
    lat_i, lon_i = int(round(lat * 1e5)), int(round(lon * 1e5))
    out.append(encode_value(lat_i - last_lat))
    out.append(encode_value(lon_i - last_lon))
    last_lat, last_lon = lat_i, lon_i
  return ''.join(out)


def mapbox_static_png(points, key: str, cache_dir: str = STATIC_CACHE_DIR,
                      timeout: float = 15.) -> bytes:
  if not key:
    raise OfflineMapError('未配置 MapboxPublicKey')
  sampled = points[::max(1, -(-len(points) // 45))]
  path = urllib.parse.quote(encode_polyline(sampled), safe='')
  url = ('https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/'
         f'path-5+f97316-0.9({path})/auto/{PREVIEW_SIZE}x{PREVIEW_SIZE}?padding=40'
         f'&access_token={urllib.parse.quote(key)}')
  os.makedirs(cache_dir, exist_ok=True)
  cached = os.path.join(cache_dir, 'mapbox_' + hashlib.sha256(url.encode()).hexdigest() + '.png')
  try:
    with open(cached, 'rb') as f:
      return f.read()
  except OSError:
    pass
  with urllib.request.urlopen(url, timeout=timeout) as response:
    body = response.read(STATIC_MAX_BYTES + 1)
  if not body.startswith(b'\x89PNG\r\n\x1a\n') or len(body) > STATIC_MAX_BYTES:
    raise OfflineMapError('Mapbox 静态图返回异常')
  fd, temporary = tempfile.mkstemp(prefix='mapbox_', dir=cache_dir)
  try:
    with os.fdopen(fd, 'wb') as f:
      f.write(body)
    os.replace(temporary, cached)
  finally:
    if os.path.exists(temporary):
      os.remove(temporary)
  return body
