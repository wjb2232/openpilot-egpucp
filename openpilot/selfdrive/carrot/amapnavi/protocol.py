#!/usr/bin/env python3
"""外挂雷达 / 摄像头模块的 UDP 报文解析（协议层）。

只负责「一包 JSON 怎么变成客户端状态」，不涉及 socket，便于单独测试。
速度估计与风险评估复用 :mod:`blindspot`。
"""

import time

from openpilot.selfdrive.carrot.amapnavi.blindspot import (
  TrackedTarget,
  TrackerConfig,
  assess_side_risk,
  resolve_safe_distance,
)
from openpilot.selfdrive.carrot.amapnavi.shared_state import BLINKER_LEFT, BLINKER_NONE, BLINKER_RIGHT

# 四个角的标识
CORNERS = ("lf", "lb", "rf", "rb")

DISTANCE_FIELDS = ("lf_drel", "lb_drel", "rf_drel", "rb_drel",
                   "lf_xrel", "lb_xrel", "rf_xrel", "rb_xrel")


class PacketHandler:
  """解析客户端报文，维护每个客户端的在线状态与盲区数据。"""

  def __init__(self, shared_data, params, tracker_config: TrackerConfig | None = None):
    self.shared_data = shared_data
    self.params = params
    self.blinker_alive = False
    self.blinker_time = time.time()
    self.blinker_ctrl_alive = False
    self.blinker_ctrl_time = time.time()

    cfg = tracker_config or TrackerConfig()
    self.trackers = {corner: TrackedTarget(cfg) for corner in CORNERS}
    # 每个角的原始危险标志（未经去抖）
    self.object_detected = {corner: False for corner in CORNERS}

    # 由外部（AmapNaviServ）按参数刷新
    self.min_front_drel_vego_time = 3.0
    self.min_front_vrel_vego_time = 3.0
    self.min_behind_drel_vego_time = 3.0
    self.min_behind_vrel_vego_time = 3.0
    self.risk_horizon_s = 3.0
    self.ttc_threshold_s = 2.5
    self.min_clearance_m = 4.0
    # 是否处于导航变道（由 AmapNaviServ 每帧刷新）
    self.atc_flag = False

  # ------------------------------------------------------------------ 入口
  def handle(self, json_obj, ip, old_info, now):
    """处理一包 JSON，返回该客户端的新状态字典。"""
    self.update_blinker(json_obj, now)
    self.update_command(json_obj)
    self.update_control(json_obj, now)
    return self.update_sensors(json_obj, ip, old_info, now)

  # ------------------------------------------------------------------ 转向灯
  def update_control(self, json_obj, now):
    if "ctrl" in json_obj:
      try:
        ctrl = json_obj.get("ctrl")
        if ctrl == "blinker":
          if "state" in json_obj:
            state = json_obj.get("state")
            if state == "left":
              self.shared_data.blinker_ctrl = BLINKER_LEFT
              self.blinker_ctrl_alive = True
              self.blinker_ctrl_time = now
            elif state == "right":
              self.shared_data.blinker_ctrl = BLINKER_RIGHT
              self.blinker_ctrl_alive = True
              self.blinker_ctrl_time = now
            else:
              self.shared_data.blinker_ctrl = BLINKER_NONE
              self.blinker_ctrl_alive = False
              self.blinker_ctrl_time = now
      except Exception as e:
        print(f"Process json 'ctrl' error: {e}")
        print(json_obj)

    # 转向灯控制超时检测
    if self.blinker_ctrl_alive and (now - self.blinker_ctrl_time) > 2.:
      self.shared_data.blinker_ctrl = BLINKER_NONE
      self.blinker_ctrl_alive = False
      self.blinker_ctrl_time = now

  def update_blinker(self, json_obj, now):
    if "blinker" not in json_obj:
      return
    val = json_obj.get("blinker")
    if val in ("left", "stockleft"):
      self.shared_data.ext_blinker = BLINKER_LEFT
    elif val in ("right", "stockright"):
      self.shared_data.ext_blinker = BLINKER_RIGHT
    else:
      self.shared_data.ext_blinker = BLINKER_NONE
    self.blinker_alive = True
    self.blinker_time = now

  def update_command(self, json_obj):
    if "index" in json_obj:
      self.shared_data.cmd_index = int(json_obj.get("index"))
    if "cmd" in json_obj:
      self.shared_data.remote_cmd = json_obj.get("cmd")
      self.shared_data.remote_arg = json_obj.get("arg")

  def blinker_ctrl_value(self, default="none"):
    """外挂转向灯控制命令 → 协议字符串。"""
    stock = int(self.params.get_int("StockBlinkerCtrl"))
    if self.shared_data.blinker_ctrl == BLINKER_LEFT:
      return "left" if stock == 0 else "stockleft"
    if self.shared_data.blinker_ctrl == BLINKER_RIGHT:
      return "right" if stock == 0 else "stockright"
    return default

  # ------------------------------------------------------------------ 传感器
  def update_sensors(self, json_obj, ip, old_info, now):
    device = json_obj.get("device", old_info.get("device", ""))

    shared = self.shared_data
    left_blind = right_blind = None
    lidar_blind = {c: None for c in ("lblind", "rblind", "lfblind", "rfblind", "lbblind", "rbblind")}
    values = {f: None for f in DISTANCE_FIELDS}
    alive = {f: False for f in DISTANCE_FIELDS}

    camera_data = lidar_data = False
    dist_timems = None
    detect_side = json_obj.get("detect_side", 0)

    try:
      if "resp" in json_obj:
        resp = json_obj.get("resp")

        if resp == "cam_blind":
          camera_data = True
          if "left_blind" in json_obj:
            left_blind = json_obj.get("left_blind")
          if "right_blind" in json_obj:
            right_blind = json_obj.get("right_blind")

        if resp == "blindspot":
          lidar_data = True
          lidar_id = int(json_obj.get("lidar_id", 0))
          dist_timems = json_obj.get("dist_time", None)
          for key in lidar_blind:
            lidar_blind[key] = json_obj.get(f"lidar_{key}")

          # 非动态盲区时立即上报盲区标志（保持原有实时性）
          if self._instant_blind():
            if lidar_blind["lblind"]:  shared.lidar_lblind = True
            if lidar_blind["lfblind"]: shared.lidar_lfblind = True
            if lidar_blind["lbblind"]: shared.lidar_lbblind = True
            if lidar_blind["rblind"]:  shared.lidar_rblind = True
            if lidar_blind["rfblind"]: shared.lidar_rfblind = True
            if lidar_blind["rbblind"]: shared.lidar_rbblind = True

          for f in DISTANCE_FIELDS:
            if f in json_obj:
              values[f] = int(json_obj[f])
              alive[f] = True

          self._update_main_targets(lidar_id, detect_side, values, old_info)
          self._update_side_risk(lidar_id, detect_side, values, old_info, dist_timems)
    except Exception as e:
      print(f"Process json 'resp' error: {e}")
      print(json_obj)

    if device == "lidar":
      return self._build_lidar_info(json_obj, old_info, now, device, detect_side, dist_timems,
                                    lidar_blind, values, alive, lidar_data)
    if device == "camera":
      return self._build_camera_info(json_obj, old_info, now, device, detect_side,
                                     left_blind, right_blind, camera_data)
    return {
      "port": int(json_obj.get("port", 4210)),
      "last_seen": now,
      "device": device,
    }

  # ------------------------------------------------------------------ 内部
  def _instant_blind(self):
    """是否使用「立即上报」的盲区（与原有 DynamicBlindRange 语义一致）。"""
    dynamic_range = int(self.params.get_int("DynamicBlindRange"))
    dynamic_dist = int(self.params.get_int("DynamicBlindDistance"))
    if dynamic_range == 0 and dynamic_dist == 0:
      return True
    return dynamic_range == 1 and not getattr(self, "atc_flag", False)

  def _update_main_targets(self, lidar_id, detect_side, values, old_info):
    """保存主雷达（编号 0/1/2）的距离，缺失时用上一次的值消抖。"""
    shared = self.shared_data
    if detect_side & 1:
      if lidar_id in (0, 1):
        if values["lf_drel"] is None: values["lf_drel"] = old_info.get("lf_drel", None)
        if values["lf_xrel"] is None: values["lf_xrel"] = old_info.get("lf_xrel", None)
        shared.main_lf_drel = values["lf_drel"]
        shared.main_lf_xrel = values["lf_xrel"]
      if lidar_id in (0, 2):
        if values["lb_drel"] is None: values["lb_drel"] = old_info.get("lb_drel", None)
        if values["lb_xrel"] is None: values["lb_xrel"] = old_info.get("lb_xrel", None)
        shared.main_lb_drel = values["lb_drel"]
        shared.main_lb_xrel = values["lb_xrel"]
    if detect_side & 2:
      if lidar_id in (0, 1):
        if values["rf_drel"] is None: values["rf_drel"] = old_info.get("rf_drel", None)
        if values["rf_xrel"] is None: values["rf_xrel"] = old_info.get("rf_xrel", None)
        shared.main_rf_drel = values["rf_drel"]
        shared.main_rf_xrel = values["rf_xrel"]
      if lidar_id in (0, 2):
        if values["rb_drel"] is None: values["rb_drel"] = old_info.get("rb_drel", None)
        if values["rb_xrel"] is None: values["rb_xrel"] = old_info.get("rb_xrel", None)
        shared.main_rb_drel = values["rb_drel"]
        shared.main_rb_xrel = values["rb_xrel"]

  def _update_side_risk(self, lidar_id, detect_side, values, old_info, dist_timems):
    """用卡尔曼跟踪 + 风险评估更新四个角的危险标志。"""
    shared = self.shared_data
    v_ego = shared.v_ego_m

    def risky(corner, drel, behind):
      tracker = self.trackers[corner]
      result = tracker.update(drel, dist_timems)
      if result is None:
        return
      d_mm, v_mps = result
      setattr(shared, f"{corner}_vrel", v_mps)

      time_param = (self.min_behind_drel_vego_time if behind
                    else self.min_front_drel_vego_time)
      safe_distance = resolve_safe_distance(time_param, v_ego or 0.0, self.min_clearance_m)
      self.object_detected[corner] = assess_side_risk(
        d_mm, v_mps, v_ego, safe_distance,
        horizon_s=self.risk_horizon_s, ttc_threshold_s=self.ttc_threshold_s,
      ).risky

    if detect_side & 1:
      if lidar_id in (0, 1):
        risky("lf", self._debounce_pair(values["lf_drel"], old_info.get("lf_drel", None)), False)
      if lidar_id in (0, 2):
        risky("lb", self._debounce_pair(values["lb_drel"], old_info.get("lb_drel", None)), True)
    if detect_side & 2:
      if lidar_id in (0, 1):
        risky("rf", self._debounce_pair(values["rf_drel"], old_info.get("rf_drel", None)), False)
      if lidar_id in (0, 2):
        risky("rb", self._debounce_pair(values["rb_drel"], old_info.get("rb_drel", None)), True)

  @staticmethod
  def _debounce_pair(value, old_value):
    """没有新测量时沿用上一次的距离（与原实现的消抖一致）。"""
    return value if value is not None else old_value

  def _build_lidar_info(self, json_obj, old_info, now, device, detect_side, dist_timems,
                        lidar_blind, values, alive, lidar_data):
    if not lidar_data:
      for f in DISTANCE_FIELDS:
        if values[f] is None:
          values[f] = old_info.get(f, None)

    times = {}
    for f in DISTANCE_FIELDS:
      times[f] = now if alive[f] else old_info.get(f"{f}_time", now)
      # 1 秒内没有距离数据更新则清空
      if (now - times[f]) > 1.0 and values[f] is not None:
        values[f] = None

    # 2 秒内没有盲区数据更新则清空
    for key in lidar_blind:
      t = old_info.get(f"lidar_{key}_time", now)
      if (now - t) > 2.0 and lidar_blind[key] is not None:
        lidar_blind[key] = False

    info = {
      "port": int(json_obj.get("port", 4210)),
      "last_seen": now,
      "device": device,
      "detect_side": json_obj.get("detect_side", old_info.get("detect_side", 0)),
      "dist_time": dist_timems,
    }
    for f in DISTANCE_FIELDS:
      info[f] = values[f]
      info[f"{f}_time"] = times[f]
    for key in lidar_blind:
      info[f"lidar_{key}"] = lidar_blind[key] if lidar_blind[key] is not None else old_info.get(f"lidar_{key}", False)
      info[f"lidar_{key}_time"] = now if lidar_blind[key] is not None else old_info.get(f"lidar_{key}_time", now)
    return info

  def _build_camera_info(self, json_obj, old_info, now, device, detect_side,
                         left_blind, right_blind, camera_data):
    l_time = old_info.get("l_blindspot_time", now)
    r_time = old_info.get("r_blindspot_time", now)
    if (now - l_time) > 2.0 and left_blind is not None:
      left_blind = False
    if (now - r_time) > 2.0 and right_blind is not None:
      right_blind = False
    return {
      "port": int(json_obj.get("port", 4210)),
      "last_seen": now,
      "device": device,
      "detect_side": json_obj.get("detect_side", old_info.get("detect_side", 0)),
      "left_blind": left_blind if left_blind is not None else old_info.get("left_blind", False),
      "right_blind": right_blind if right_blind is not None else old_info.get("right_blind", False),
      "l_blindspot_time": now if left_blind is not None else old_info.get("l_blindspot_time", now),
      "r_blindspot_time": now if right_blind is not None else old_info.get("r_blindspot_time", now),
    }


def apply_timeouts_lidar(info, now):
  """就地清理超时的雷达数据（供采集线程调用）。"""
  for f in DISTANCE_FIELDS:
    if (now - info.get(f"{f}_time", now)) > 1.0:
      info[f] = None
  for key in ("lblind", "rblind", "lfblind", "rfblind", "lbblind", "rbblind"):
    if (now - info.get(f"lidar_{key}_time", now)) > 2.0:
      info[f"lidar_{key}"] = False
  return info


def apply_timeouts_camera(info, now):
  """就地清理超时的摄像头盲区数据。"""
  if (now - info.get("l_blindspot_time", now)) > 2.0:
    info["left_blind"] = False
  if (now - info.get("r_blindspot_time", now)) > 2.0:
    info["right_blind"] = False
  return info


def body_blind(drel_front, xrel_front, drel_behind, xrel_behind):
  """车身范围内的障碍判断（车头 3m / 车尾 2m 内，且横向距离 < 1.2m）。"""
  limit = max(3000 + (drel_behind if drel_behind is not None else -2000), 1000)
  if ((drel_front is not None and drel_front < limit and xrel_front is not None and xrel_front < 1200) or
      (drel_behind is not None and drel_behind > -2000 and xrel_behind is not None and xrel_behind < 1200)):
    return True
  return False
