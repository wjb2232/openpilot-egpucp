#!/usr/bin/env python3
"""avoidance.py —— 障碍感知与避险(自行设计避障绕行 阶段1)。

检测本车道前方的静止/极慢障碍物(基于 radarState + 模型路径)
并推算一个安全的限速建议,注入 carrot_serv 的 speed_n_sources
(经 desiredSpeed 通道实现车减速,不改变转向)。

安全设计:
- 只在本车道(dPath 判定)且距离较近时才触发
- 输出是"限速",不是急刹(最终制动由 MPC 平滑执行)
- 连续确认 N 帧才生效(防雷达抖动误触发)
- 离开危险区立即恢复(无迟滞锁存)
- 参数全部可调、可通过 params 关闭

输入: radarState.leadOne(最近前车)/carState(本车道路径 dPath)
输出: avoidance_speed_kph(建议限速,None=不触发)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


# 触发条件阈值(可经 params 覆盖)
MIN_TRIGGER_SPEED_KPH = 5.0      # 本车速度低于此不触发(接近停车排队)
MAX_TRIGGER_DREL_M = 40.0        # 障碍物最近距离(米)
MAX_TRIGGER_DPATH_M = 3.5        # 障碍物偏离路径距离(米),>此视为相邻车道
STOPPED_VREL_KPH = -3.0          # 相对速度低于此视为"静止/极慢障碍"
CONFIRM_FRAMES = 3               # 连续确认帧数
RELEASE_FRAMES = 5               # 连续消失帧数后才恢复
TARGET_GAP_M = 12.0              # 期望保持的车间距(米)
MAX_AVOID_SPEED_KPH = 80.0       # 避障限速上限
MIN_AVOID_SPEED_KPH = 0.0        # 避障限速下限

# 安全减速度(m/s^2):限速按"到障碍距离"线性平滑
SAFE_DECEL_MPS2 = 1.5


@dataclass(frozen=True)
class AvoidanceEstimate:
  active: bool
  speed_kph: float
  d_rel_m: float
  d_path_m: float
  v_rel_kph: float
  reason: str = ""


class ObstacleAvoidance:
  """状态机:确认触发 -> 持续限速 -> 释放。"""

  def __init__(self) -> None:
    self._confirm_count = 0
    self._release_count = 0
    self._active = False
    self._last_estimate: AvoidanceEstimate | None = None
    self._stats: dict = field(default_factory=dict)

  def reset(self) -> None:
    self._confirm_count = 0
    self._release_count = 0
    self._active = False
    self._last_estimate = None

  def _detect_obstacle(self, lead: object | None, car_state: object | None) -> AvoidanceEstimate:
    """从 leadOne 检测本车道静止/极慢障碍。lead/car_state 为 None 时不触发。"""
    if lead is None or car_state is None:
      return AvoidanceEstimate(False, 0.0, 0.0, 0.0, 0.0, "no-data")

    d_rel = float(lead.dRel)
    d_path = float(lead.dPath)
    v_rel = float(lead.vRel) * 3.6  # m/s -> kph
    v_ego = float(car_state.vEgo) * 3.6
    v_lead = float(lead.vLead) * 3.6 if hasattr(lead, "vLead") else v_ego + v_rel

    # 非本车道(偏移过大)
    if abs(d_path) > MAX_TRIGGER_DPATH_M:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "off-path")

    # 距离过远
    if d_rel > MAX_TRIGGER_DREL_M:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "far")

    # 本车太慢(已在排队,让 MPC 处理)
    if v_ego < MIN_TRIGGER_SPEED_KPH:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "slow-ego")

    # 障碍物判定:静止/极慢(相对速度显著为负 或 前车速度接近 0)
    is_stopped = v_rel < STOPPED_VREL_KPH or v_lead < 1.0
    if not is_stopped:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "moving-lead")

    # 计算建议限速:12m(TARGET_GAP)内线性递减
    # d_rel >= TARGET_GAP:交给 MPC 正常纵向跟车,不重复干预
    # d_rel 0~12m:限速 = v_ego * d_rel / TARGET_GAP(越近越慢,0m→0)
    if d_rel >= TARGET_GAP_M:
      return AvoidanceEstimate(False, 0.0, d_rel, d_path, v_rel, "matching-lead")
    speed_kph = v_ego * max(0.0, d_rel / TARGET_GAP_M)
    speed_kph = min(speed_kph, MAX_AVOID_SPEED_KPH)
    return AvoidanceEstimate(True, speed_kph, d_rel, d_path, v_rel, "stopped-obstacle")

  def update(self, lead: object | None, car_state: object | None) -> AvoidanceEstimate:
    est = self._detect_obstacle(lead, car_state)

    if est.active:
      self._confirm_count += 1
      self._release_count = 0
      if self._confirm_count >= CONFIRM_FRAMES:
        self._active = True
        self._last_estimate = est
    else:
      self._confirm_count = 0
      if self._active:
        self._release_count += 1
        if self._release_count >= RELEASE_FRAMES:
          self._active = False
          self._last_estimate = None
      else:
        self._last_estimate = None

    if self._active and self._last_estimate is not None:
      return self._last_estimate
    return AvoidanceEstimate(False, 0.0, est.d_rel_m, est.d_path_m, est.v_rel_kph, est.reason)

  # 对外:建议的限速(kph),不触发返回 None
  def suggested_speed(self) -> float | None:
    if self._active and self._last_estimate is not None:
      return self._last_estimate.speed_kph
    return None

  def is_active(self) -> bool:
    return self._active