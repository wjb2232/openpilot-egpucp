#!/usr/bin/env python3
"""c3 avoidance —— 主动避障(曲线避让)。

阶段1: 检测本车道静止/极慢障碍 -> 限速(纵向避险)。
阶段2: 从障碍物位置生成平滑避让曲线(偏出->保持->回中), 逐点输出曲率,
       注入 controlsd 的 desiredCurvature(横向绕过, 不跨线)。
阶段3: 相邻车道空旷且本车道障碍近时, 自动换道请求(LANECHANGE)。

与 egpucp 的差异: c3 无 lane_planner_2 路径偏移层, 横向直接由模型
curvature 驱动, 因此阶段2 改为"曲线避让": 以障碍相对位置为基准生成
y(s) 横向位移曲线(三段余弦拼接, 边界处 y=y'=0, 无限可导),
每周期按里程 s 查曲率 kappa = y''(s) 叠加到 desired_curvature。

安全:
- 40m 内对静止/极慢障碍线性限速(消除 12~40m 盲区)
- 避让偏移 <= 0.35m 不跨线; 两侧都不可绕则不横向避让(只减速)
- 横向加速度限制 <= 0.5 m/s^2; 曲率按速度夹取
- 换道仅 25m 内触发, 8s 冷却, 且模型判定可绕时才发
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass


MIN_TRIGGER_SPEED_KPH = 5.0
MAX_TRIGGER_DREL_M = 40.0
MAX_TRIGGER_DPATH_M = 3.5
# 前车绝对速度低于此值视为静止/极慢障碍(触发避障)。
# 注意不能用相对速度 v_rel 判据: 高速巡航时前车慢几 km/h 是常态,
# v_rel < -3 会把正常慢车误判为静止障碍(egpucp 原版即如此)。
STOPPED_VLEAD_KPH = 10.0
TARGET_GAP_M = 40.0
MAX_AVOID_SPEED_KPH = 80.0

# 时间基准防抖(与调用频率无关): 0.3s 确认 / 0.5s 释放
CONFIRM_SEC = 0.30
RELEASE_SEC = 0.50

# ---- 阶段2 曲线避让参数 ------------------------------------------------ #
MAX_OFFSET_M = 0.35          # 最大横向偏移(车道内, 不跨线)
NEAR_AVOID_M = 25.0          # 近距触发阈值(<=25m 才启动曲线)
HOLD_SEC = 1.2               # 保持段时长(绕过障碍身位)
SIDE_SEC = 1.5               # 偏出/回中段时间基数(随速度: L = v*SIDE_SEC)
MIN_SIDE_M = 12.0            # 偏出/回中段最小长度
MAX_LAT_ACCEL_MPS2 = 0.5     # 避让横向加速度上限
# 曲线完成冷却: 走完一条曲线(偏出->保持->回中)后, 即使障碍仍在触发区
# 也至少等这么久再重触发, 防止同一障碍导致左右往复绕行(往复摆动)。
CURVE_COOLDOWN_S = 4.0

# ---- 阶段3 换道参数 ---------------------------------------------------- #
LC_COOLDOWN_S = 8.0
LC_MIN_SPEED_KPH = 40.0
LC_NEAR_M = 25.0
LC_SIDE_CLEAR_M = 45.0
LC_SIDE_CLEAR_Y_M = 5.0

# ---- 自动超车(OVERTAKE)参数 -------------------------------------------- #
# 三档设置移植自 AmapNavi.apk OvertakeParams(反编译 MainActivityLaneDecisionKt
# <clinit>, 与手机端 evaluateOvertakeTrigger/Side 同参)。档位由
# OverTakeMode param 选择: 1=激进/2=常规/3=保守。
# 构造器参数顺序 (I String F F I F F I I J F I I F F F Z Z J J):
#   mode, name, triggerMaxDist, triggerMinDist, vrelThreshold, timeGapMax,
#   cruiseRatio, leadMinSpeedRoad, leadMinSpeedHighWay, cooldownFailedMs,
#   _?, rearMinDist, sideFrontMinDist, sideMinScore, sideSafetyMargin(bool侧?),
#   extra, allowRightOvertake, preferLeftFirst, cooldownSuccessMs, _?
OT_PARAMS = {
  # 激进: 距离区间8~72m, 前车慢1km/h即超, 高速限15/普通25, 冷成功6s失败400ms, 允许右侧
  1: {
    "trigger_min_m": 8.0, "trigger_max_m": 72.0,
    "vrel_threshold_kph": -1.0,
    "lead_min_road_kph": 25.0, "lead_min_highway_kph": 15.0,
    "rear_min_dist_m": 45.0, "side_front_min_dist_m": 5.0,
    "time_gap_max_s": 4.0, "cruise_ratio": 0.95,
    "cooldown_success_s": 6.0, "cooldown_failed_s": 0.4,
    "allow_right_overtake": True, "prefer_left_first": False,
  },
  # 常规: 12~80m, 慢3km/h, 高速20/普通35, 冷成功10s失败800ms, 优先左侧
  2: {
    "trigger_min_m": 12.0, "trigger_max_m": 80.0,
    "vrel_threshold_kph": -3.0,
    "lead_min_road_kph": 35.0, "lead_min_highway_kph": 20.0,
    "rear_min_dist_m": 60.0, "side_front_min_dist_m": 10.0,
    "time_gap_max_s": 3.0, "cruise_ratio": 0.90,
    "cooldown_success_s": 10.0, "cooldown_failed_s": 0.8,
    "allow_right_overtake": True, "prefer_left_first": True,
  },
  # 保守: 20~60m, 慢8km/h, 高速30/普通45, 冷成功15s失败1.2s
  3: {
    "trigger_min_m": 20.0, "trigger_max_m": 60.0,
    "vrel_threshold_kph": -8.0,
    "lead_min_road_kph": 45.0, "lead_min_highway_kph": 30.0,
    "rear_min_dist_m": 75.0, "side_front_min_dist_m": 15.0,
    "time_gap_max_s": 2.0, "cruise_ratio": 0.80,
    "cooldown_success_s": 15.0, "cooldown_failed_s": 1.2,
    "allow_right_overtake": True, "prefer_left_first": False,
  },
}
OT_DEFAULT_MODE = 2  # 常规
OT_MIN_SPEED_KPH = 40.0  # 低于该车速不主动超车(低速排队)


@dataclass(frozen=True)
class AvoidanceEstimate:
  active: bool
  speed_kph: float
  d_rel_m: float
  d_path_m: float
  v_rel_kph: float
  reason: str = ""


class ObstacleAvoidance:
  """阶目1+3 状态机: 时间防抖, 确认触发 -> 持续限速 -> 释放。"""

  def __init__(self) -> None:
    self._confirm_since = 0.0
    self._release_since = 0.0
    self._active = False
    self._last_estimate: AvoidanceEstimate | None = None
    self._last_y_rel: float = 0.0  # 障碍横向位置(右正), 阶段3 选边用

  def reset(self) -> None:
    self._confirm_since = 0.0
    self._release_since = 0.0
    self._active = False
    self._last_estimate = None
    self._last_y_rel = 0.0

  def _detect_obstacle(self, lead, car_state) -> AvoidanceEstimate:
    if lead is None or car_state is None:
      return AvoidanceEstimate(False, 0.0, 0.0, 0.0, 0.0, "no-data")
    try:
      d_rel = float(lead.dRel)
      d_path = float(lead.dPath)
      v_rel = float(lead.vRel) * 3.6
      v_ego = float(car_state.vEgo) * 3.6
    except Exception:
      return AvoidanceEstimate(False, 0.0, 0.0, 0.0, 0.0, "bad-data")

    if abs(d_path) > MAX_TRIGGER_DPATH_M:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "off-path")
    if d_rel > MAX_TRIGGER_DREL_M:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "far")
    if v_ego < MIN_TRIGGER_SPEED_KPH:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "slow-ego")

    # 静止/极慢判定: 必须看前车绝对速度(vLead), 不能只看相对速度。
    # v_rel < -3 只说明"前车比我慢"——高速巡航时前车慢 3~5km/h 是常态,
    # 若误判为静止障碍会触发无谓限速+换道(复查发现, egpucp 原判据)。
    # 绝对速度 < STOPPED_VLEAD_KPH 才视为极慢/静止障碍。
    try:
      v_lead = float(lead.vLead) * 3.6
    except Exception:
      v_lead = v_ego + v_rel  # 无 vLead 字段时用自车速度+相对速度合成
    is_stopped = v_lead < STOPPED_VLEAD_KPH
    if not is_stopped:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "moving-lead")
    if d_rel >= TARGET_GAP_M:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "matching-lead")
    speed_kph = v_ego * max(0.0, d_rel / TARGET_GAP_M)
    speed_kph = min(speed_kph, MAX_AVOID_SPEED_KPH)
    # desiredSpeed=0 会被 controlsd 过滤, 最低 1.0 kph 保证通道有效
    speed_kph = max(speed_kph, 1.0)
    return AvoidanceEstimate(True, speed_kph, d_rel, d_path, v_rel, "stopped-obstacle")

  def update(self, lead, car_state, now: float | None = None) -> AvoidanceEstimate:
    now = time.monotonic() if now is None else now
    est = self._detect_obstacle(lead, car_state)
    if lead is not None:
      try:
        self._last_y_rel = float(lead.yRel)
      except Exception:
        self._last_y_rel = 0.0

    if est.active:
      self._release_since = 0.0
      if self._confirm_since == 0.0:
        self._confirm_since = now
      elif now - self._confirm_since >= CONFIRM_SEC:
        self._active = True
        self._last_estimate = est
    else:
      self._confirm_since = 0.0
      if self._active:
        if self._release_since == 0.0:
          self._release_since = now
        elif now - self._release_since >= RELEASE_SEC:
          self._active = False
          self._last_estimate = None
      else:
        self._last_estimate = None

    if self._active and self._last_estimate is not None:
      return self._last_estimate
    return AvoidanceEstimate(False, 0.0, est.d_rel_m, est.d_path_m, est.v_rel_kph, est.reason)

  def suggested_speed(self) -> float | None:
    if self._active and self._last_estimate is not None:
      return self._last_estimate.speed_kph
    return None

  def is_active(self) -> bool:
    return self._active

  def estimate(self) -> AvoidanceEstimate | None:
    return self._last_estimate if self._active else None

  # ---- 阶段3: 自动换道请求 --------------------------------------------- #
  def lane_change_request(self, v_ego_kph: float,
                          left_blocked: bool | None = None,
                          right_blocked: bool | None = None,
                          lane_change_active: bool = False,
                          now: float | None = None) -> str | None:
    """评估是否应自动换道绕行。返回 "LEFT"/"RIGHT"/None。

    left_blocked/right_blocked 由调用方合成(carrot_man: lidar 盲区 +
    radarTracks 点云 + 模型 laneChangeAvailable + 视觉行人/车辆):
      None  = 无该侧信息(视为可绕, 保守性由调用方保证)
      True  = 该侧有风险(后方来车/盲区/行人/相邻车道占用) -> 不可绕
      False = 该侧安全
    """
    now = time.monotonic() if now is None else now
    if now - getattr(self, "_lc_last_request", 0.0) < LC_COOLDOWN_S:
      return None
    if lane_change_active or not self._active:
      return None
    est = self._last_estimate
    if est is None or est.d_rel_m > LC_NEAR_M:
      return None
    if v_ego_kph < LC_MIN_SPEED_KPH:
      return None

    left_clear = left_blocked is not True
    right_clear = right_blocked is not True
    # 障碍反侧优先: yRel 左正(log.capnp), y_rel>0=障碍在左 -> 右绕
    # (离开障碍); 偏左/居中 -> 默认左绕(国内左超车, 靠右行驶)。
    prefer_left = self._last_y_rel <= 0.0
    if prefer_left and left_clear:
      direction = "LEFT"
    elif (not prefer_left) and right_clear:
      direction = "RIGHT"
    elif left_clear:
      direction = "LEFT"
    elif right_clear:
      direction = "RIGHT"
    else:
      return None

    self._lc_last_request = now
    return direction

  # ---- 自动超车(OVERTAKE) ---- #
  def set_overtake_mode(self, mode: int) -> None:
    """设置超车档位(见 OT_PARAMS): 1=激进/2=常规/3=保守。"""
    if mode in OT_PARAMS:
      self.overtake_mode = mode

  def overtake_request(self, v_ego_kph: float, v_lead_kph: float | None,
                       left_blocked: bool | None = None,
                       right_blocked: bool | None = None,
                       lane_change_active: bool = False,
                       highway: bool = False,
                       now: float | None = None) -> str | None:
    """评估是否应自动超车, 返回 "LEFT"/"RIGHT"/None。

    与 AmapNavi.apk evaluateOvertakeTrigger 同参(按档位):
      前车低于档位最低速度(高速/普通路分开) -> 疑似排队, 不超;
      前车相对自车过慢(巡航比例 cruise_ratio) -> 值得超;
      距离区间(trigger_min~trigger_max)内 -> 可超;
      目标侧安全(left_blocked/right_blocked 由调用方合成) -> 发起。
    冷却按档位 cooldown_success_s(成功后)/cooldown_failed_s(失败后, 短),
    失败冷却由 overtake_result(False) 切换。
    """
    now = time.monotonic() if now is None else now
    p = OT_PARAMS.get(getattr(self, "overtake_mode", OT_DEFAULT_MODE), OT_PARAMS[OT_DEFAULT_MODE])

    if v_lead_kph is None:
      return None
    # 档位最低前车速度(排队/拥堵判定), 高速与普通路分开
    lead_min = p["lead_min_highway_kph"] if highway else p["lead_min_road_kph"]
    if v_lead_kph < lead_min:
      return None
    # 前车相对自车(巡航代理)过慢才值得超
    if v_lead_kph > v_ego_kph * p["cruise_ratio"]:
      return None
    if v_ego_kph < OT_MIN_SPEED_KPH:
      return None

    # 冷却: 成功/失败分开(APK cooldownSuccess/Failed)
    cooldown = p["cooldown_success_s"] if not getattr(self, "_ot_failed", False) else p["cooldown_failed_s"]
    if now - getattr(self, "_ot_last_request", 0.0) < cooldown:
      return None
    if lane_change_active:
      return None

    left_clear = left_blocked is not True
    right_clear = right_blocked is not True
    # 档位偏好: prefer_left_first 优先左侧; 障碍反侧优先次之(yRel 左正,
    # y_rel>0=障碍在左 -> 右绕; 偏左/居中 -> 左绕)。
    prefer_left = p["prefer_left_first"] or self._last_y_rel <= 0.0
    if prefer_left and left_clear:
      direction = "LEFT"
    elif (not prefer_left) and right_clear and p["allow_right_overtake"]:
      direction = "RIGHT"
    elif left_clear:
      direction = "LEFT"
    elif right_clear and p["allow_right_overtake"]:
      direction = "RIGHT"
    else:
      return None

    self._ot_last_request = now
    return direction

  def overtake_result(self, success: bool) -> None:
    """超车结果回馈: 失败 -> 短冷却(快速重试); 成功 -> 长冷却(避免骚扰)。"""
    self._ot_failed = not success


class AvoidanceCurve:
  """阶段2: 从障碍物位置生成平滑避让曲线(偏出->保持->回中)。

  曲线以纵向里程 s 为参数, 三段 quintic 多项式拼接(y, y', y'' 全程连续):
    段1  s in [0, L1)     y = O * Q(r),  r=s/L1,  Q=10r^3-15r^4+6r^5
    段2  s in [L1, L1+L2) y = O
    段3  s in [L1+L2, L)  y = O * (1-Q(r)),  r=(s-L1-L2)/L3
  Q(r) 在 r=0 与 r=1 处 y=y'=y''=0, 故段2(保持)与段1/段3 边界处
  y''=0 连续, kappa 无阶跃(驾驶平顺, 无 jerk 冲击)。
  kappa = y''(s): 段1 = O*(60r-180r^2+120r^3)/L1^2, 段3 = -O*.../L3^2
  横向加速度限制 <= MAX_LAT_ACCEL_MPS2, 曲率按速度夹取。

  触发: 障碍 active 且 d_rel <= NEAR_AVOID_M, 且存在可绕方向。
  方向: 优先模型 laneChangeAvailable 判据; 否则倾向障碍所在侧的对面,
        两侧都不可绕则只限速不横向避让。
  """

  def __init__(self, detector: ObstacleAvoidance | None = None) -> None:
    self.detector = detector or ObstacleAvoidance()
    self._active = False
    self._s = 0.0
    self._L1 = MIN_SIDE_M
    self._L2 = 8.0
    self._L3 = MIN_SIDE_M
    self._O = 0.0          # 带符号最终偏移(右正左负)
    self._direction = 1
    self._reason = ""
    self._last_kappa = 0.0
    self._done_at = 0.0    # 最近一次曲线完成(或取消)时刻, 防往复重触发

  def reset(self, now: float | None = None) -> None:
    if self._active:
      self._done_at = now if now is not None else time.monotonic()
    self._active = False
    self._s = 0.0
    self._last_kappa = 0.0

  def is_active(self) -> bool:
    return self._active

  def _pick_direction(self, lead, sm, left_blocked: bool | None = None,
                      right_blocked: bool | None = None) -> int:
    """返回避让方向: +1 右绕, -1 左绕; 0 不避让(只限速)。

    侧后安全(左/右)由调用方合成: lidar 盲区 + radarTracks 点云 +
    模型 laneChangeAvailable + 视觉行人。None 表示无信息。

    yRel 为 car frame, 左正(log.capnp): y_rel>0 = 障碍在左 -> 右绕
    (离开障碍); y_rel<0 = 障碍在右 -> 左绕; 居中 -> 默认左绕(左超车
    习惯, 靠右行驶)。
    """
    md = None
    lav_l = lav_r = None
    try:
      if sm is not None and sm.alive.get('modelV2', False):
        md = sm['modelV2']
        lav_l = bool(md.meta.laneChangeAvailableLeft)
        lav_r = bool(md.meta.laneChangeAvailableRight)
    except Exception:
      pass

    # 障碍侧: y_rel>0 障碍在左 -> 倾向右绕
    try:
      y_rel = float(lead.yRel) if lead is not None else 0.0
    except Exception:
      y_rel = 0.0
    prefer_left = y_rel <= 0.0

    # 合成"该侧可绕": 无明确 blocked, 且模型未明确禁止
    left_ok = left_blocked is not True
    right_ok = right_blocked is not True
    if lav_l is not None and left_ok:
      left_ok = left_ok and lav_l
    if lav_r is not None and right_ok:
      right_ok = right_ok and lav_r

    if left_ok and prefer_left:
      return -1
    if right_ok and not prefer_left:
      return 1
    if left_ok:
      return -1
    if right_ok:
      return 1
    return 0

  def _setup_curve(self, v_ego: float, d_rel: float, direction: int) -> None:
    """按当前速度与障碍距离初始化曲线段长。"""
    side = max(MIN_SIDE_M, min(v_ego * SIDE_SEC, max(d_rel - 4.0, MIN_SIDE_M)))
    self._L1 = side
    self._L3 = side
    self._L2 = max(6.0, v_ego * HOLD_SEC)
    self._O = MAX_OFFSET_M * direction
    self._direction = direction
    self._s = 0.0

  def _kappa_at(self, s: float) -> float:
    if not self._active:
      return 0.0
    O, L1, L2, L3 = self._O, self._L1, self._L2, self._L3
    if s < L1:
      r = s / L1
      return O * (60.0 * r - 180.0 * r * r + 120.0 * r ** 3) / (L1 * L1)
    if s < L1 + L2:
      return 0.0
    r = (s - L1 - L2) / L3
    return -O * (60.0 * r - 180.0 * r * r + 120.0 * r ** 3) / (L3 * L3)

  def _total_len(self) -> float:
    return self._L1 + self._L2 + self._L3

  def update(self, v_ego: float, dt: float, sm=None, lead=None, now: float | None = None,
             left_blocked: bool | None = None, right_blocked: bool | None = None,
             lane_change_active: bool = False) -> float:
    """每控制周期调用, 返回应叠加的曲率(rad/m)。v_ego: m/s, dt: s。

    lane_change_active: 模型换道中 -> 抑制曲线(换道轨迹与曲线叠加打架,
    且换道本身就是在绕行)。detector 仍正常推进(限速持续有效)。
    """
    # 1. 障碍检测(时间防抖, 与 carrot_man 的频率无关)
    lead_cur = lead
    cs = None
    rs = None
    if sm is not None:
      try:
        rs = sm['radarState'] if sm.alive.get('radarState', False) else None
        if rs is not None:
          lead_cur = rs.leadOne if (rs.leadOne.present and rs.leadOne.status) else None
        cs = sm['carState'] if sm.valid.get('carState', False) else None
      except Exception:
        pass
    if lead_cur is None and lead is not None:
      lead_cur = lead
    # 状态机推进(结果由 detector.is_active()/estimate() 读取)
    self.detector.update(lead_cur, cs, now=now)

    # 1b. 换道中: 抑制曲线(但 detector 已推进, 限速继续)
    if lane_change_active:
      if self._active:
        self.reset(now)
      return 0.0

    # 1c. 激活中但目标侧突然 blocked: 立即取消曲线(侧后有车时不能继续
    # 贴边绕行), 只保留限速。方向检查只在触发时做过, 这里每帧复查。
    if self._active:
      dir_now = self._direction
      if dir_now < 0 and left_blocked is True:
        self.reset(now)
        return 0.0
      if dir_now > 0 and right_blocked is True:
        self.reset(now)
        return 0.0

    # 2. 曲线状态推进
    if self._active:
      self._s += max(v_ego, 1.0) * dt
      # 障碍消失且已过保持段 -> 走完回中段后归零
      if not self.detector.is_active() and self._s >= self._L1 + self._L2:
        pass  # 继续回中段
      if self._s >= self._total_len():
        self.reset(now)
        return 0.0

    # 3. 未激活: 评估是否触发
    if not self._active:
      if self.detector.is_active():
        # 曲线完成/取消后冷却期内不重触发(防同一障碍往复绕行)
        if now is not None and now - self._done_at < CURVE_COOLDOWN_S:
          return 0.0
        est_d = self.detector.estimate()
        d_rel = est_d.d_rel_m if est_d is not None else 40.0
        v_ego_kph = v_ego * 3.6
        if (d_rel <= NEAR_AVOID_M and v_ego_kph >= MIN_TRIGGER_SPEED_KPH):
          direction = self._pick_direction(lead_cur, sm, left_blocked, right_blocked)
          if direction != 0:
            self._setup_curve(v_ego, d_rel, direction)
            self._active = True
            self._reason = f"avoid-curve d={d_rel:.0f}m dir={'L' if direction < 0 else 'R'}"
            return self._kappa_at(0.0)
      return 0.0

    # 4. 激活中: 查曲线曲率, 限幅
    kappa = self._kappa_at(self._s)
    # 横向加速度限制: a = kappa * v^2 <= MAX_LAT_ACCEL
    max_k = MAX_LAT_ACCEL_MPS2 / max(v_ego * v_ego, 0.25)
    if abs(kappa) > max_k:
      kappa = math.copysign(max_k, kappa)
    self._last_kappa = kappa
    return kappa

  @property
  def offset_now(self) -> float:
    """当前横向偏移(m, 右正左负), 用于调试/UI。"""
    if not self._active:
      return 0.0
    O, L1, L2, L3 = self._O, self._L1, self._L2, self._L3
    s = self._s

    def _q(r: float) -> float:
      return 10.0 * r ** 3 - 15.0 * r ** 4 + 6.0 * r ** 5

    if s < L1:
      return O * _q(s / L1)
    if s < L1 + L2:
      return O
    return O * (1.0 - _q((s - L1 - L2) / L3))
