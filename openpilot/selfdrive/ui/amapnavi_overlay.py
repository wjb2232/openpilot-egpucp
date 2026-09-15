#!/usr/bin/env python3
"""amapnavi（外挂激光雷达 / 摄像头 BSD 模块）的 UI 显示。

由 cpv9-dev ``openpilot/selfdrive/ui/carrot.cc`` 中 AmapNavi 相关绘制移植而来
（源端约 500 行 C++ / nanovg，含 ui.cc 中订阅 amapNavi 的 1 行）。

**设计目标：不侵入现有 UI 代码**。解析、配色、布局、绘制全部集中在本模块，
现有 UI 文件各自只需加 1 行调用：

* ``ui_state.py``              - SubMaster 增加 ``"amapNavi"``
* ``onroad/model_renderer.py`` - ``_draw_carrot_overlays()`` 末尾调用 :func:`draw_barriers_c3`
* ``onroad/hud_renderer.py``   - ``_render()`` 调用 :func:`draw_bsd_panel`，
                                 状态徽标处调用 :func:`draw_ext_state_badge`
* ``mici/onroad/model_renderer.py`` - ``_draw_blindspots()`` 末尾调用 :func:`draw_barriers_mici`

盲区位定义（``amapNavi.leftBlind`` / ``rightBlind``，与源端一致）::

  bit0 (1)  激光雷达盲区
  bit1 (2)  摄像头盲区
  bit2 (4)  原车侧向盲区
  bit3 (8)  实线
  bit4 (16) 目标在侧前方（向上箭头）
  bit5 (32) 目标在侧后方（向下箭头）

设备位定义（``leftDevice`` / ``rightDevice``）::

  bit0 (1) 激光雷达在线
  bit1 (2) 摄像头在线

距离字段（``lfDrel`` / ``lbDrel`` / ``rfDrel`` / ``rbDrel``，四角 = 左前/左后/右前/右后）::

  原始单位 mm，amap_navi 发布时 /100 → dm，本模块显示时再 /10 → 米（与源端一致）

**已知差异**：源端第一行圆圈用的是 ``modelV2.meta.leftFrontBlind``（原车前盲区），
本分支的 MetaData 没有该字段，因此用 ``getattr`` 兜底为 False，
即第一行在本分支不会出现（不影响雷达/摄像头/距离的显示）。
"""

import time
from dataclasses import dataclass, field

import pyray as rl

from openpilot.system.ui.lib.shader_polygon import draw_polygon
from openpilot.system.ui.lib.text_draw import draw_text_ui_style
from openpilot.selfdrive.ui.road_markings import blindspot_barrier_quads, project_blindspot_barrier

# ------------------------------------------------------------------ 位定义
BLIND_LIDAR = 1
BLIND_CAMERA = 2
BLIND_STOCK_SIDE = 4
BLIND_SOLID_LINE = 8
BLIND_FRONT = 16
BLIND_REAR = 32

DEVICE_LIDAR = 1
DEVICE_CAMERA = 2

SIDES = ("left", "right")

# ------------------------------------------------------------------ 配色
def _c(r: int, g: int, b: int, a: int) -> rl.Color:
  return rl.Color(r, g, b, a)


# 变道护栏（半透明，源端 alpha=60）
BARRIER_YELLOW = _c(255, 215, 0, 60)
BARRIER_BLUE = _c(0, 0, 255, 60)
BARRIER_PURPLE = _c(138, 43, 226, 60)
BARRIER_CYAN = _c(0, 255, 255, 60)
BARRIER_PINK = _c(233, 37, 227, 60)

# 圆形图标（源端 alpha=150）
ICON_RED = _c(255, 0, 0, 150)
ICON_YELLOW = _c(255, 215, 0, 150)
ICON_BLUE = _c(0, 0, 255, 150)
ICON_PURPLE = _c(138, 43, 226, 150)
ICON_PINK = _c(233, 37, 227, 150)

# 线条 / 箭头
LINE_YELLOW = _c(255, 255, 0, 255)
LINE_BLUE = _c(0, 0, 255, 255)
ARROW_RED = _c(255, 0, 0, 200)
ARROW_YELLOW = _c(255, 215, 0, 200)
DIST_TEXT_YELLOW = _c(255, 255, 0, 255)

# ------------------------------------------------------------------ 布局
CIRCLE_RADIUS = 46
VERTICAL_SPACING = 100
HORIZONTAL_OFFSET = 150
TOP_Y = 10
ARROW_HEAD_WIDTH = 46
ARROW_HEAD_LENGTH = 30
ARROW_GAP = 5

DIST_FONT_SIZE = 50
DIST_TEXT_OFFSET_X = 30
DIST_TEXT_OFFSET_Y = 35

SOLID_BAR_WIDTH = 20

# E 徽标（外挂客户端数量），相对 APN/APM 徽标中心的偏移
EXT_BADGE_OFFSET_X = 60
EXT_BADGE_WIDTH = 55
EXT_BADGE_HEIGHT = 48
EXT_BADGE_OK = _c(0, 228, 48, 255)
EXT_BADGE_IDLE = _c(230, 60, 60, 255)

# ------------------------------------------------------------------ 数据
@dataclass
class AmapNaviView:
  """一帧 amapNavi 消息的解包结果（纯数据，便于单测）。"""

  left_blind: int = 0
  right_blind: int = 0
  left_device: int = 0
  right_device: int = 0
  left_line: int = 0
  right_line: int = 0
  line_valid: bool = False
  ext_state: int = 0
  # corner -> (valid, 米)
  distances: dict = field(default_factory=dict)

  def blind(self, side: str) -> int:
    return self.left_blind if side == "left" else self.right_blind

  def device(self, side: str) -> int:
    return self.left_device if side == "left" else self.right_device

  @property
  def has_distance(self) -> bool:
    return any(valid for valid, _ in self.distances.values())


def read_amapnavi(sm):
  """从 SubMaster 读一帧 amapNavi；不可用或未在线时返回 None。"""
  try:
    if not (sm.valid['amapNavi'] and sm.alive['amapNavi']):
      return None
    msg = sm['amapNavi']
  except Exception:
    return None

  view = AmapNaviView(
    left_blind=int(msg.leftBlind),
    right_blind=int(msg.rightBlind),
    left_device=int(msg.leftDevice),
    right_device=int(msg.rightDevice),
    left_line=int(msg.leftLine),
    right_line=int(msg.rightLine),
    line_valid=bool(msg.lineValid),
    ext_state=int(getattr(msg, "extState", 0) or 0),
  )
  for corner in ("lf", "lb", "rf", "rb"):
    valid = int(getattr(msg, f"{corner}DrelValid", 0) or 0)
    raw = float(getattr(msg, f"{corner}Drel", 0) or 0)
    view.distances[corner] = (valid, raw / 10.0)  # dm -> m
  return view


def _stock_blindspots(sm) -> dict:
  """原车后盲区（carState.leftBlindspot / rightBlindspot）。"""
  out = {"left": False, "right": False}
  try:
    if sm.valid['carState']:
      car_state = sm['carState']
      out["left"] = bool(car_state.leftBlindspot)
      out["right"] = bool(car_state.rightBlindspot)
  except Exception:
    pass
  return out


def _front_blind(sm) -> dict:
  """原车前盲区（源端取 modelV2.meta.leftFrontBlind，本分支无此字段时兜底 False）。"""
  out = {"left": False, "right": False}
  try:
    if sm.valid['modelV2']:
      meta = sm['modelV2'].meta
      out["left"] = bool(getattr(meta, "leftFrontBlind", False))
      out["right"] = bool(getattr(meta, "rightFrontBlind", False))
  except Exception:
    pass
  return out


# ------------------------------------------------------------------ 配色决策
def barrier_color(blind: int, front_blind: bool = False):
  """amapnavi 变道护栏的配色（对应源端 ``ui_draw_bsd`` 的颜色分支）。

  原车后盲区（红色）由渲染器自己绘制，这里不覆盖，因此只在 amapnavi 有盲区时返回颜色。

  :return: :class:`rl.Color`，None 表示不需要绘制
  """
  if blind <= 0:
    return None

  lidar = blind & BLIND_LIDAR
  camera = blind & BLIND_CAMERA
  if front_blind and lidar and camera:  # 前盲区 + 雷达 + 摄像头
    return BARRIER_PINK
  if front_blind and lidar:  # 前盲区 + 雷达
    return BARRIER_CYAN
  if camera:  # 摄像头
    return BARRIER_PURPLE
  if lidar:  # 雷达
    return BARRIER_BLUE
  return BARRIER_YELLOW if front_blind else None


def icon_color(blind: int):
  """雷达 / 摄像头盲区圆圈的填充色。"""
  lidar = blind & BLIND_LIDAR
  camera = blind & BLIND_CAMERA
  if lidar and camera:
    return ICON_PINK
  if camera:
    return ICON_PURPLE
  return ICON_BLUE


# ------------------------------------------------------------------ 绘制原语
def _tri(x1, y1, x2, y2, x3, y3, color: rl.Color) -> None:
  rl.draw_triangle(
    rl.Vector2(float(x1), float(y1)),
    rl.Vector2(float(x2), float(y2)),
    rl.Vector2(float(x3), float(y3)),
    color,
  )


def _arrow_up(cx, cy, color: rl.Color, gap: float = 0.0) -> None:
  half_w = ARROW_HEAD_WIDTH / 2
  length = ARROW_HEAD_LENGTH
  _tri(cx, cy - length - gap, cx - half_w, cy - gap, cx + half_w, cy - gap, color)


def _arrow_down(cx, cy, color: rl.Color, gap: float = 0.0) -> None:
  half_w = ARROW_HEAD_WIDTH / 2
  length = ARROW_HEAD_LENGTH
  _tri(cx, cy + length + gap, cx - half_w, cy + gap, cx + half_w, cy + gap, color)


def _arrow_center_up(cx, cy, color: rl.Color) -> None:
  """居中向上的小三角（源端第一行「原车前盲区」）。"""
  half_w = ARROW_HEAD_WIDTH / 2
  half_l = ARROW_HEAD_LENGTH / 2
  _tri(cx, cy - half_l, cx - half_w, cy + half_l, cx + half_w, cy + half_l, color)


def _arrow_center_down(cx, cy, color: rl.Color) -> None:
  """居中小向下的三角（源端第三行「原车后盲区」）。"""
  half_w = ARROW_HEAD_WIDTH / 2
  half_l = ARROW_HEAD_LENGTH / 2
  _tri(cx, cy + half_l, cx - half_w, cy - half_l, cx + half_w, cy - half_l, color)


def _arrow_side(cx, cy, to_left: bool, color: rl.Color) -> None:
  half_w = ARROW_HEAD_WIDTH / 2
  half_l = ARROW_HEAD_LENGTH / 2
  if to_left:
    _tri(cx - half_l, cy, cx + half_l, cy - half_w, cx + half_l, cy + half_w, color)
  else:
    _tri(cx + half_l, cy, cx - half_l, cy - half_w, cx - half_l, cy + half_w, color)


# ------------------------------------------------------------------ 参数缓存
_param_cache: dict = {}


def _cached_int_param(key: str, default: int, ttl: float = 1.0) -> int:
  """带 TTL 的参数读取，避免每帧访问 Params。"""
  now = time.monotonic()
  hit = _param_cache.get(key)
  if hit is not None and now - hit[0] < ttl:
    return hit[1]
  try:
    from openpilot.selfdrive.ui.ui_state import ui_state

    value = int(ui_state.params.get_int(key))
  except Exception:
    value = default
  _param_cache[key] = (now, value)
  return value


# ------------------------------------------------------------------ 顶部图标面板
def draw_bsd_panel(sm, rect: rl.Rectangle, font=None, show_lane_info: int | None = None) -> None:
  """在屏幕顶部中央绘制盲区图标与四角距离（对应源端 ``draw()`` 的圆形部分）。

  三行布局（与源端一致，行数固定以保证图标位置稳定）：

  * 第一行  原车前盲区（黄圆 + 向上红箭头）
  * 第二行  雷达/摄像头盲区圆 + 箭头 + 在线双环 + 实线黄条，两侧为四角距离
  * 第三行  原车后盲区（红圆 + 向下黄箭头）
  """
  view = read_amapnavi(sm)
  if view is None:
    return

  if show_lane_info is None:
    show_lane_info = _cached_int_param("ShowLaneInfo", 1)

  stock = _stock_blindspots(sm)
  front = _front_blind(sm)

  nothing_to_show = not (
    view.left_blind or view.right_blind or view.left_device or view.right_device
    or view.has_distance or stock["left"] or stock["right"] or front["left"] or front["right"]
  )
  if nothing_to_show:
    return

  center_x = int(rect.x + rect.width / 2)
  r = CIRCLE_RADIUS
  top_y = TOP_Y

  # ---------------- 第一行：原车前盲区 ----------------
  for side in SIDES:
    if not front[side]:
      continue
    cx = center_x - HORIZONTAL_OFFSET if side == "left" else center_x + HORIZONTAL_OFFSET
    cy = top_y + r
    rl.draw_circle(int(cx), int(cy), r, ICON_YELLOW)
    if show_lane_info >= 1:
      _arrow_center_up(cx, cy, ARROW_RED)
  top_y += VERTICAL_SPACING

  # ---------------- 第二行：距离 + 雷达/摄像头图标 ----------------
  for side in SIDES:
    is_left = side == "left"
    sign = -1 if is_left else 1
    cx = center_x + sign * HORIZONTAL_OFFSET
    cy = top_y + r

    # 四角距离文字（左前/左后 或 右前/右后）
    front_corner, rear_corner = ("lf", "lb") if is_left else ("rf", "rb")
    f_valid, f_dist = view.distances.get(front_corner, (0, 0.0))
    r_valid, r_dist = view.distances.get(rear_corner, (0, 0.0))
    if f_valid or r_valid:
      text_x = cx + sign * (r + DIST_TEXT_OFFSET_X)
      align = "right_center" if is_left else "left_center"
      if f_valid:
        draw_text_ui_style(
          f"{f_dist:.1f}", text_x, cy - DIST_TEXT_OFFSET_Y, DIST_FONT_SIZE, DIST_TEXT_YELLOW,
          font=font, border_width=2.0, shadow_offset=4.0, align=align,
        )
      if r_valid:
        draw_text_ui_style(
          f"{r_dist:.1f}", text_x, cy + DIST_TEXT_OFFSET_Y, DIST_FONT_SIZE, DIST_TEXT_YELLOW,
          font=font, border_width=2.0, shadow_offset=4.0, align=align,
        )

    # 雷达 / 摄像头盲区圆圈
    blind = view.blind(side)
    if blind & ~BLIND_SOLID_LINE:
      rl.draw_circle(int(cx), int(cy), r, icon_color(blind))
      if blind & BLIND_FRONT:
        _arrow_up(cx, cy, ARROW_RED, ARROW_GAP)
      if blind & BLIND_REAR:
        _arrow_down(cx, cy, ARROW_RED, ARROW_GAP)
      if not (blind & (BLIND_FRONT | BLIND_REAR)):
        _arrow_side(cx, cy, is_left, ARROW_RED)
    elif view.device(side) & DEVICE_LIDAR:
      # 设备在线但无盲区：外蓝内黄双环（源端为 10px 描边的两个同心圆）
      center = rl.Vector2(float(cx), float(cy))
      rl.draw_ring(center, r - 10, r, 0, 360, 32, LINE_BLUE)
      rl.draw_ring(center, max(0.0, r - 20), max(1.0, r - 10), 0, 360, 32, LINE_YELLOW)

    # 实线：靠近车辆一侧的黄色竖条
    if blind & BLIND_SOLID_LINE:
      bar_x = cx + r + DIST_TEXT_OFFSET_X if is_left else cx - r - DIST_TEXT_OFFSET_X - SOLID_BAR_WIDTH
      rl.draw_rectangle(int(bar_x), int(cy - r), SOLID_BAR_WIDTH, int(r * 2), LINE_YELLOW)
  top_y += VERTICAL_SPACING

  # ---------------- 第三行：原车后盲区 ----------------
  for side in SIDES:
    if not stock[side]:
      continue
    cx = center_x - HORIZONTAL_OFFSET if side == "left" else center_x + HORIZONTAL_OFFSET
    cy = top_y + r
    rl.draw_circle(int(cx), int(cy), r, ICON_RED)
    if show_lane_info >= 1:
      _arrow_center_down(cx, cy, ARROW_YELLOW)


# ------------------------------------------------------------------ E 徽标
def draw_ext_state_badge(count: int, dx: float, dy: float, font=None) -> None:
  """外挂客户端数量徽标（源端在 N/M 徽标右侧的 "E" 方框）。

  有客户端时绿色，无客户端时红色，中间显示数量。
  """
  x = dx + EXT_BADGE_OFFSET_X
  y = dy - 38
  rect = rl.Rectangle(float(x), float(y), float(EXT_BADGE_WIDTH), float(EXT_BADGE_HEIGHT))
  fill = EXT_BADGE_OK if count > 0 else EXT_BADGE_IDLE

  rl.draw_rectangle_rounded(rect, 0.25, 8, fill)
  rl.draw_rectangle_rounded_lines_ex(rect, 0.25, 8, 2, rl.WHITE)
  draw_text_ui_style(
    str(int(count)), x + EXT_BADGE_WIDTH / 2, dy, 40, rl.WHITE,
    font=font, border_width=2.0, shadow_offset=4.0, align="center_bottom",
  )


def ext_state_from(sm) -> int:
  """取当前外挂客户端数量（amapNavi 不可用时返回 0）。"""
  view = read_amapnavi(sm)
  return view.ext_state if view is not None else 0


# ------------------------------------------------------------------ 变道护栏
def draw_barriers_c3(renderer, sm) -> None:
  """c3（大屏）渲染器：补充 amapnavi 的变道护栏着色。

  复用渲染器自身的护栏构建与绘制方法，因此这里只做配色决策。
  """
  view = read_amapnavi(sm)
  if view is None:
    return
  try:
    if not sm.valid['modelV2']:
      return
    front = _front_blind(sm)
    for idx, side in enumerate(SIDES):
      color = barrier_color(view.blind(side), front[side])
      if color is None:
        continue
      renderer._update_blind_spot_barriers_carrot(sm, update_left=(idx == 0), update_right=(idx == 1))
      renderer._draw_blind_spot_segments_carrot(renderer._carrot_lane_barrier_vertices[idx], color)
  except Exception:
    # UI 绘制不应因为数据缺失而中断
    return


def draw_barriers_mici(renderer, sm) -> None:
  """mici（小屏）渲染器：补充 amapnavi 的变道护栏着色。"""
  view = read_amapnavi(sm)
  if view is None:
    return
  try:
    if not sm.valid['modelV2']:
      return
    points = renderer._path.raw_points
    if points.shape[0] < 2:
      return
    front = _front_blind(sm)
    max_idx = renderer._get_path_length_idx(points[:, 0], 40.0)
    for side, shift in (("left", -1.7), ("right", 1.7)):
      color = barrier_color(view.blind(side), front[side])
      if color is None:
        continue
      polygon = project_blindspot_barrier(
        points[:max_idx + 1], shift, renderer._car_space_transform, renderer._clip_region,
      )
      for quad in blindspot_barrier_quads(polygon):
        draw_polygon(renderer._rect, quad, color)
  except Exception:
    return
