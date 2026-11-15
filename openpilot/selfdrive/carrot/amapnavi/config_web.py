#!/usr/bin/env python3
"""Web 界面模块 - amapnavi 参数设置页面。

由 cpv9-dev 的 ``openpilot/selfdrive/carrot/web_interface.py`` 移植而来（文件名改为 config_web.py）。
用于在 Web 页面查看/修改由 ``UnifiedParams``(nav_params.json) 管理的 amapnavi 参数。

注意：本 fork 的 ``openpilot.common.params.Params`` 是带类型校验的新版 API，
``get()`` 返回已解码的 Python 值，``put()`` 要求传入与 key 类型匹配的值。
因此源码里基于 bytes 的 get/put 不能直接使用，下面按类型分别做了转换。

本服务只管理 ``config.py``(nav_params.json) 这一套参数：
网页上的「导出配置 / 恢复配置」备份与恢复的也只是这套参数，
**不涉及 openpilot 系统参数**（原 cp 系统的参数不走这个渠道）。

接口列表：
  GET  /                       -> 重定向到 /nav_params
  GET  /nav_params             -> 参数设置页面 (nav_params.html)
  GET  /nav_params_data        -> 当前配置 (JSON)，供页面接口使用
  GET  /nav_params_download    -> 当前配置以 JSON 文件下载（备份，兼容 iOS Safari）
  GET  /get_default_nav_params -> 默认配置 (JSON)
  POST /nav_params             -> 保存配置；{"reset": "true"} 时恢复默认值
"""

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from openpilot.selfdrive.carrot.amapnavi import osm_cache
from openpilot.selfdrive.navigation import carrot_offline_tiles as offline_maps
from openpilot.selfdrive.carrot.amapnavi.config import UnifiedParams
from openpilot.selfdrive.carrot.amapnavi.nav_plan import PlanError, STATIC_MAP_MAX_POINTS, live_position, parse_point
from openpilot.selfdrive.carrot.amapnavi.nav_plan import plan as plan_route
from openpilot.selfdrive.carrot.amapnavi.nav_plan import static_map_png

DEFAULT_HTTP_PORT = 8088
_MEMORY_PARAMS = None


def memory_params():
    """Params('/dev/shm/params')，用来读 LastGPSPosition；不可用时返回 None。"""
    global _MEMORY_PARAMS
    if _MEMORY_PARAMS is None:
        try:
            from openpilot.common.params import Params

            _MEMORY_PARAMS = Params('/dev/shm/params')
        except Exception:  # 参数服务缺失时页面仍然可用，只是没有「我的位置」
            _MEMORY_PARAMS = False
    return _MEMORY_PARAMS or None


def preview_keys(unified_params):
    """路线预览用的 (高德 Web 服务 Key, Mapbox key)。"""
    def read(name):
        value = None
        try:
            value = (unified_params.nav_data or {}).get(name)
        except Exception:
            value = None
        if value in (None, ''):
            try:
                value = unified_params.system_params.get(name)
            except Exception:
                value = None
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'ignore')
        return str(value or '').strip()

    return {'amap_key': read('AmapWebKey'), 'mapbox_key': read('MapboxPublicKey')}


class ConfigWeb:
    """amapnavi 参数配置 Web 服务处理器。

    :param controller: 拥有 ``.params``(UnifiedParams) 属性的对象，如 ``AmapNaviServ`` / ``CarrotMan``；
                       不传时直接使用 ``UnifiedParams()`` 单例。
    :param port: HTTP 端口（默认 8088）
    :param params: 也可以直接传入 UnifiedParams 实例。
    """

    def __init__(self, controller=None, port=DEFAULT_HTTP_PORT, params=None):
        self.controller = controller
        self.web_server = None
        self.port = port
        self.params = params
        if self.params is None:
          self.params = getattr(controller, "params", None)
        if self.params is None:
          self.params = UnifiedParams()

    def create_web_handler(self):
        """创建Web处理器"""
        unified_params = self.params
        controller = self.controller

        class ConfigWebRequestHandler(BaseHTTPRequestHandler):
            def safe_write(self, data):
                """安全写入数据，处理连接中断"""
                try:
                    if isinstance(data, str):
                        data = data.encode('utf-8')
                    self.wfile.write(data)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                except Exception as e:
                    print(f"写入数据时发生错误: {e}")

            def log_message(self, format, *args):
                """自定义日志格式，避免每次请求都打印到控制台"""
                pass

            def do_OPTIONS(self):
                """处理CORS预检请求"""
                try:
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                    self.send_header('Access-Control-Max-Age', '86400')
                    self.end_headers()
                except Exception as e:
                    print(f"OPTIONS请求处理错误: {e}")

            def do_GET(self):
                """处理GET请求"""
                try:
                    if self.path == '/':
                        self.send_response(301)
                        self.send_header('Location', '/nav_params')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                    elif self.path == '/radar':
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        self.send_radar_page()
                    elif self.path == '/radar_data':
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        self.send_radar_data()
                    elif self.path == '/nav_params':
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-store')
                        self.end_headers()
                        self.send_nav_params_page()
                    elif self.path == '/nav_params_data':
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.send_nav_params_data()
                    elif self.path == '/get_default_nav_params':
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.send_default_nav_params()
                    elif self.path == '/nav_params_download':
                        self.send_nav_params_file()
                    elif self.path == '/nav_search':
                        self.send_response(200)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-store')
                        self.end_headers()
                        self.send_nav_search_page()
                    elif self.path.startswith('/nav_search/api/position'):
                        self.send_nav_position()
                    elif self.path.startswith('/nav_search/api/route'):
                        self.send_nav_route()
                    elif self.path.startswith('/nav_search/api/staticmap'):
                        self.send_nav_static_map()
                    elif self.path.startswith('/nav_search/api/osm/status'):
                        self.send_json_response(osm_cache.status())
                    elif self.path.startswith('/nav_search/api/osm/regions'):
                        self.send_json_response({'regions': osm_cache.regions()})
                    elif self.path.startswith('/nav_search/api/basemap'):
                        self.send_preview_base_map()
                    elif self.path.startswith('/nav_search/api/offline/status'):
                        self.send_json_response(offline_maps.status())
                    elif self.path.startswith('/nav_search/api/offline/regions'):
                        self.send_offline_regions()
                    elif self.path.startswith('/nav_search/api'):
                        self.proxy_nav_api('GET')
                    elif self.path == '/nav_search/map.png':
                        self.proxy_nav_map()
                    else:
                        self.send_error(404, f"{self.path} Page not found")

                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端连接中断: {e}")
                except IOError as e:
                    print(f"IO错误: {e}")
                    self.send_error(500, "Internal server erro")
                except Exception as e:
                    print(f"未预期的错误: {e}")
                    self.send_error(500, f"Internal server erro: {str(e)}")

            def do_POST(self):
                """处理POST请求"""
                try:
                    if self.path.startswith('/nav_search/api/offline/'):
                        self.handle_offline_post()
                        return
                    if self.path.startswith('/nav_search/api/osm/'):
                        self.handle_osm_post()
                        return
                    if self.path.startswith('/nav_search/api'):
                        self.proxy_nav_api('POST')
                        return
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    data = json.loads(post_data) if post_data else {}

                    if self.path == '/nav_params':
                        self.handle_nav_params(data)
                    else:
                        self.send_error(404, "API not found")
                except json.JSONDecodeError:
                    self.send_error(400, "JSON format error")
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端连接中断: {e}")
                except Exception as e:
                    print(f"请求处理错误: {e}")
                    self.send_error(500, f"Internal server erro: {str(e)}")

            def do_DELETE(self):
                """处理DELETE请求（导航搜索页清除目的地）"""
                try:
                    if self.path.startswith('/nav_search/api'):
                        self.proxy_nav_api('DELETE')
                    else:
                        self.send_error(404, "API not found")
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端连接中断: {e}")
                except Exception as e:
                    print(f"请求处理错误: {e}")

            def send_nav_search_page(self):
                """发送导航搜索页面（8088 独立页面）"""
                try:
                    self.safe_write(self.get_html_content('nav_search.html'))
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端连接中断: {e}")
                except Exception as e:
                    print(f"发送导航搜索页面错误: {e}")

            def proxy_nav_api(self, method):
                """把 /nav_search/api/* 转发给 carrot_server (127.0.0.1:7000)。

                carrot_server 的接口不带 CORS 头，页面放在 8088 同源代理最省事，
                也不用为浏览器额外开放端口。
                """
                suffix = self.path[len('/nav_search/api'):] or '/'
                url = 'http://127.0.0.1:7000/api/navigation' + suffix
                body = None
                if method in ('POST', 'PUT'):
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length) if length > 0 else b''
                request = urllib.request.Request(url, data=body, method=method,
                                                 headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        status, payload = response.status, response.read()
                except urllib.error.HTTPError as error:
                    status, payload = error.code, error.read()
                except Exception as error:
                    status = 502
                    payload = json.dumps({'error': f'carrot_server 不可达: {error}'},
                                         ensure_ascii=False).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.safe_write(payload)

            def proxy_nav_map(self):
                """转发 carrot_server 的路线预览图（204 表示暂时没有图）。"""
                request = urllib.request.Request('http://127.0.0.1:7000/api/navigation/map.png', method='GET')
                map_status = ''
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        status, payload = response.status, response.read()
                        map_status = response.headers.get('X-Nav-Map-Status', '')
                except urllib.error.HTTPError as error:
                    status, payload = error.code, error.read()
                except Exception:
                    status, payload, map_status = 503, b'', 'unreachable'
                self.send_response(status)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Nav-Map-Status', map_status)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                if payload:
                    self.safe_write(payload)

            def send_nav_params_file(self):
                """下载当前配置为 JSON 文件（带 Content-Disposition，兼容 iOS Safari）"""
                try:
                    unified_params._match_system_param()
                    payload = json.dumps(unified_params.nav_data, ensure_ascii=False, indent=2)
                    body = payload.encode('utf-8')
                    filename = time.strftime("amapnavi_params_%Y%m%d_%H%M%S.json")
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.safe_write(body)
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送配置文件错误: {e}")

            def send_nav_params_page(self):
                """发送 amapnavi 参数设置页面"""
                try:
                    html = self.get_html_content('nav_params.html')
                    self.safe_write(html)
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送参数页面错误: {e}")

            def send_default_nav_params(self):
                """发送默认的 amapnavi 参数数据"""
                try:
                    default_data = unified_params._get_default_nav_data()
                    self.safe_write(json.dumps(default_data, ensure_ascii=False))
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送默认参数错误: {e}")

            def send_nav_params_data(self):
                """发送 amapnavi 参数数据"""
                try:
                    unified_params._match_system_param()
                    nav_data = unified_params.nav_data
                    self.safe_write(json.dumps(nav_data, ensure_ascii=False))
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送参数数据错误: {e}")

            def handle_nav_params(self, data):
                """处理 amapnavi 参数更新 - 复用 UnifiedParams 逻辑"""
                try:
                    if not data:
                        self.send_json_response({'status': 'error', 'message': '无效的数据'})
                        return

                    if 'reset' in data and data['reset'] == 'true':
                        default_data = unified_params._get_default_nav_data()
                        unified_params.nav_data = default_data
                        unified_params._save_nav_data()
                        unified_params._save_system_param()
                        self.send_json_response({'status': 'success', 'message': '参数已恢复默认'})
                    else:
                        unified_params.nav_data = data
                        unified_params._save_nav_data()
                        unified_params._save_system_param()
                        self.send_json_response({'status': 'success', 'message': '参数已保存'})
                except Exception as e:
                    self.send_json_response({'status': 'error', 'message': f'保存失败: {str(e)}'})

            def send_json_response(self, data, status=200):
                """发送JSON响应"""
                try:
                    self.send_response(status)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.safe_write(json.dumps(data, ensure_ascii=False))
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送JSON响应错误: {e}")

            def send_offline_regions(self):
                """离线底图区域：城市/省份默认 z15，国家/全国 z12，并预估体积。"""
                regions = []
                for region in osm_cache.regions():
                    zoom = (offline_maps.NATIONAL_ZOOM if region['kind'] == 'country'
                            else offline_maps.CITY_ZOOM)
                    item = dict(region, zoom=zoom)
                    item['est_bytes'] = offline_maps.estimate_bytes(region['bbox'], zoom)
                    regions.append(item)
                nationwide = {'key': 'nationwide', 'name': '全国（z12 低精度，约 1 GB）',
                              'bbox': list(osm_cache.COUNTRY_REGIONS['CN'][1]),
                              'tiles': 1, 'kind': 'national', 'zoom': offline_maps.NATIONAL_ZOOM}
                nationwide['est_bytes'] = offline_maps.estimate_bytes(nationwide['bbox'],
                                                                      offline_maps.NATIONAL_ZOOM)
                regions.append(nationwide)
                self.send_json_response({'regions': regions})

            def handle_offline_post(self):
                """离线底图：切换来源、按城市/全国下载、删除或选中归档。"""
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    data = json.loads(self.rfile.read(length) or b'{}') if length else {}
                except (ValueError, TypeError):
                    self.send_json_response({'error': '请求体不是合法 JSON'}, status=400)
                    return
                try:
                    if self.path.startswith('/nav_search/api/offline/provider'):
                        self.send_json_response({'provider': offline_maps.set_provider(str(data.get('provider')))})
                    elif self.path.startswith('/nav_search/api/offline/install'):
                        # 设备不自带 go-pmtiles，按需从 release 下载（分块 + 断点续传）
                        self.send_json_response(offline_maps.start_cli_install())
                    elif self.path.startswith('/nav_search/api/offline/download'):
                        region_key = data.get('region')
                        requested_zoom = data.get('zoom')
                        if requested_zoom not in (None, '', 'auto'):
                            try:
                                requested_zoom = int(requested_zoom)
                            except (ValueError, TypeError):
                                raise offline_maps.OfflineMapError('精度等级无效')
                            if requested_zoom not in range(0, 16):
                                raise offline_maps.OfflineMapError('精度等级超出范围')
                        else:
                            requested_zoom = None
                        zoom = None
                        if region_key == 'nationwide':
                            name = '全国'
                            bbox = list(osm_cache.COUNTRY_REGIONS['CN'][1])
                            # 全国固定 z12：z15 有上千万瓦片，误选会撑爆设备
                            zoom = offline_maps.NATIONAL_ZOOM
                        elif region_key:
                            region = osm_cache.find_region(str(region_key))
                            if region is None:
                                raise offline_maps.OfflineMapError('未知区域')
                            name, bbox = region['name'], region['bbox']
                            default_zoom = (offline_maps.NATIONAL_ZOOM if region['kind'] == 'country'
                                           else offline_maps.CITY_ZOOM)
                            zoom = requested_zoom if requested_zoom is not None else default_zoom
                        else:
                            name = str(data.get('name') or '自定义区域')
                            bbox = data.get('bbox')
                            zoom = requested_zoom
                            if not bbox:
                                raise offline_maps.OfflineMapError('缺少 region 或 bbox')
                        self.send_json_response(offline_maps.start_download(name, bbox, zoom))
                    elif self.path.startswith('/nav_search/api/offline/active'):
                        self.send_json_response({'active': offline_maps.set_active(str(data.get('name')))})
                    elif self.path.startswith('/nav_search/api/offline/delete'):
                        offline_maps.delete_archive(str(data.get('name')))
                        self.send_json_response(offline_maps.status())
                    else:
                        self.send_json_response({'error': '未知的离线底图接口'}, status=404)
                except offline_maps.OfflineMapError as e:
                    self.send_json_response({'error': str(e)}, status=400)
                except Exception as e:
                    self.send_json_response({'error': f'操作失败: {e}'}, status=500)

            def send_preview_base_map(self):
                """预览界面三选一：高德静态图 / Mapbox 静态图 / OSM 离线瓦片。"""
                fields = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                raw = (fields.get('points') or [''])[0]
                points = []
                for part in raw.split(';')[:STATIC_MAP_MAX_POINTS]:
                    if ',' not in part:
                        continue
                    try:
                        lon, lat = (float(value) for value in part.split(',')[:2])
                    except ValueError:
                        continue
                    if math.isfinite(lon) and math.isfinite(lat) and abs(lon) <= 180 and abs(lat) <= 85.05:
                        points.append((lon, lat))
                try:
                    if len(points) < 2:
                        raise PlanError('缺少路线点')
                    keys = preview_keys(unified_params)
                    provider = offline_maps.get_provider()
                    if provider == 'osm':
                        body = offline_maps.render_preview(points)
                    elif provider == 'mapbox':
                        if not keys['mapbox_key']:
                            raise PlanError('未配置 MapboxPublicKey')
                        body = offline_maps.mapbox_static_png(points, keys['mapbox_key'])
                    else:
                        if not keys['amap_key']:
                            raise PlanError('未配置高德 Web 服务 Key')
                        body = static_map_png(points, keys['amap_key'])
                except (PlanError, offline_maps.OfflineMapError) as e:
                    self.send_json_response({'error': str(e)}, status=400)
                    return
                except Exception as e:
                    self.send_json_response({'error': f'底图生成失败: {e}'}, status=500)
                    return
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'public, max-age=86400')
                    self.end_headers()
                    self.safe_write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def handle_osm_post(self):
                """OSM 离线地图：启动下载或清空缓存（都在本进程内完成）。"""
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    data = json.loads(self.rfile.read(length) or b'{}') if length else {}
                except (ValueError, TypeError):
                    self.send_json_response({'error': '请求体不是合法 JSON'}, status=400)
                    return
                try:
                    if self.path.startswith('/nav_search/api/osm/download'):
                        region_key = data.get('region')
                        if region_key:
                            region = osm_cache.find_region(str(region_key))
                            if region is None:
                                raise osm_cache.OsmError('未知区域')
                            bbox, name = region['bbox'], region['name']
                        else:
                            bbox = data.get('bbox')
                            name = str(data.get('name') or '自定义区域')
                            if not bbox:
                                raise osm_cache.OsmError('缺少 region 或 bbox')
                        self.send_json_response(osm_cache.start_download(name, bbox))
                    elif self.path.startswith('/nav_search/api/osm/delete'):
                        self.send_json_response(osm_cache.clear_cache())
                    else:
                        self.send_json_response({'error': '未知的 OSM 接口'}, status=404)
                except osm_cache.OsmError as e:
                    self.send_json_response({'error': str(e)}, status=400)
                except Exception as e:
                    self.send_json_response({'error': f'操作失败: {e}'}, status=500)

            def send_nav_position(self):
                """页面把「我的位置」填进出发地输入框；没有定位时返回 null。"""
                position = live_position(memory_params())
                if position is None:
                    self.send_json_response({'position': None})
                    return
                longitude, latitude = position
                self.send_json_response({'position': {'latitude': latitude, 'longitude': longitude}})

            def send_nav_route(self):
                """页面侧路线预览：出发地可手填，留空则用当前定位。"""
                fields = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                destination = parse_point((fields.get('destination') or [''])[0])
                origin = parse_point((fields.get('origin') or [''])[0])
                try:
                    if destination is None:
                        raise PlanError('先搜索并选择一个目的地')
                    if origin is None:
                        origin = live_position(memory_params())
                        if origin is None:
                            raise PlanError('车辆没有定位，请先搜索出发地')
                    self.send_json_response(plan_route(origin, destination, **preview_keys(unified_params)))
                except PlanError as e:
                    self.send_json_response({'error': str(e)}, status=400)
                except Exception as e:
                    self.send_json_response({'error': f'预览失败: {e}'}, status=500)

            def send_nav_static_map(self):
                """路线预览的底图：高德静态图（道路 + 路线 + 起终点，自动适配）。"""
                fields = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                raw = (fields.get('points') or [''])[0]
                points = []
                for part in raw.split(';')[:STATIC_MAP_MAX_POINTS]:
                    if ',' not in part:
                        continue
                    try:
                        lon, lat = (float(value) for value in part.split(',')[:2])
                    except ValueError:
                        continue
                    if math.isfinite(lon) and math.isfinite(lat) and abs(lon) <= 180 and abs(lat) <= 85.05:
                        points.append((lon, lat))
                try:
                    if len(points) < 2:
                        raise PlanError('缺少路线点')
                    key = preview_keys(unified_params)['amap_key']
                    if not key:
                        raise PlanError('未配置高德 Web 服务 Key')
                    body = static_map_png(points, key)
                except PlanError as e:
                    self.send_json_response({'error': str(e)}, status=400)
                    return
                except Exception as e:
                    self.send_json_response({'error': f'底图生成失败: {e}'}, status=500)
                    return
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'public, max-age=86400')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.safe_write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def send_radar_page(self):
                """发送雷达数据显示页面（没有 radar.html 时返回提示信息）"""
                try:
                    html = self.get_html_content('radar.html')
                    self.safe_write(html)
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送雷达页面错误: {e}")

            def send_radar_data(self):
                """发送雷达数据JSON（仅当存在 controller.get_radar_data() 时）"""
                try:
                    if controller is None or not hasattr(controller, 'get_radar_data'):
                        radar_data = {'points': [], 'tracks': [], 'leads': [], 'timestamp': 0.0, 'error': 'no radar source'}
                    else:
                        radar_data = controller.get_radar_data()
                    self.safe_write(json.dumps(radar_data, ensure_ascii=False))
                except (BrokenPipeError, ConnectionResetError) as e:
                    print(f"客户端断开连接: {e}")
                except Exception as e:
                    print(f"发送雷达数据错误: {e}")

            def get_html_content(self, filename):
                """HTML文件读取加载（与本模块同目录）"""
                try:
                    base_dir = os.path.abspath(os.path.dirname(__file__))
                    html_file_path = os.path.join(base_dir, filename)

                    if not os.path.exists(html_file_path):
                        return f"<html><body><h1>错误：文件 {filename} 不存在于路径 {html_file_path}</h1></body></html>"

                    with open(html_file_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except FileNotFoundError:
                    return f"<html><body><h1>错误：未找到 {filename} 文件</h1></body></html>"
                except Exception as e:
                    return f"<html><body><h1>错误：读取文件失败 - {str(e)}</h1></body></html>"

        return ConfigWebRequestHandler

    def start_web_server(self):
        """启动Web服务器"""
        try:
            handler = self.create_web_handler()
            self.web_server = HTTPServer(('0.0.0.0', self.port), handler)
            self.web_server.timeout = 30
            print(f"🌐 amapnavi Web服务器启动在端口 {self.port}")
            self.web_server.serve_forever()
        except Exception as e:
            print(f"启动Web服务器失败: {e}")
            raise

    def start(self, daemon=True):
        """以后台线程方式启动 Web 服务器"""
        import threading

        thread = threading.Thread(target=self.start_web_server, daemon=daemon)
        thread.start()
        return thread

    def stop_web_server(self):
        """停止Web服务器"""
        if self.web_server:
            self.web_server.shutdown()
            self.web_server.server_close()
            print("🌐 amapnavi Web服务器已停止")
