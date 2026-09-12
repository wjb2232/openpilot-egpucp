import numpy as np
from opendbc.car.structs import car
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.controls.lib.drive_helpers import CONTROL_N, CREEP_STOP_MAX_A_TARGET
from openpilot.common.pid import PIDController
from openpilot.selfdrive.modeld.constants import ModelConstants

CONTROL_N_T_IDX = ModelConstants.T_IDXS[:CONTROL_N]

LongCtrlState = car.CarControl.Actuators.LongControlState

# --- stopping 状态的职责 ------------------------------------------------------
#
# stopping 只需要做两件事: 压过蠕行扭矩、静止后保持。
# 减速曲线本身始终交给规划(MPC), 因为它的 a_target 会随 v->0 收敛到 0, 那个收敛
# 才是不点头的来源。
#
# 历史实现做的是 `output_accel = self.last_output_accel` 然后无条件
# `-= 1.0 * DT_CTRL` 一路加到 CP.stopAccel(-2.0):
#   - 它把规划丢开了, 于是规划精心做的 "末段收敛" 被换成 "单调加深";
#   - 它把上一次的输出"冻住"了, 所以规划想松刹车时它反而继续踩深;
#   - 目标 -2.0 是"车已经停住用来保持"的值, 不是"还在滚的时候该追"的值。
# 结果就是减速峰值必然落在停车那一刻 -> 点头。
#
# 下面改成三段式: 规划为纲 + 低速保底 + 静止硬保持, 并且双向限速率。
#
# 判据必须做在 a_ego(车实际减速度) 上, 不能做在 a_target(规划请求) 上。
# 日志 (route 19808ba994, 蠕行带 v=0.3~1.0, engaged 37.9s) 实测:
#     a_target med -0.46   <- 规划看着一直在认真减速
#     aEgo     med -0.02   <- 蠕行扭矩把它抵消了, 车根本没在减速
# 也就是说死锁的形状不是 "规划软下来了", 而是 "规划顶着、车不动"。
# 上一版把入口写成 a_target > -STOPPING_MIN_BRAKE, 于是这 37.9s 里门只开了
# 6.6s(17%), 与 should_stop 同时成立只有 1.9s: stopping 全程 3.8s, 4 次里只有
# 1 次真把车停住, 保底减速形同虚设。
# 改成看 a_ego 后, 同一段 "规划要刹车但车没在减速" 的时间是 23.1s(61%), 门才真的开。
STOPPING_HOLD_V = 0.1        # m/s    低于此速度直接按 CP.stopAccel 保持
CREEP_FLOOR_ACCEL = -1.0     # m/s^2  压过蠕行扭矩的保底减速(主旋钮, 需明显大于约 0.6~0.9 的蠕行加速度)
CREEP_DECEL_MARGIN = -0.3    # m/s^2  a_ego 低于此值说明车确实在减速, 规划在起作用
STOPPING_ACCEL_RATE = 1.0    # m/s^2/s 指令变化率上限(与车辆侧 stopping 态 1.0 m/s^3 的 jerk 上限一致)


def long_control_state_trans(CP_SP, active, long_control_state,
                             should_stop, brake_pressed, cruise_standstill,
                             a_ego: float = 0.0):
  # Gas Interceptor
  cruise_standstill = cruise_standstill and not CP_SP.enableGasInterceptor

  starting_condition = (not should_stop and
                        not cruise_standstill and
                        not brake_pressed)

  if not active:
    long_control_state = LongCtrlState.off

  else:
    if long_control_state == LongCtrlState.off:
      if not starting_condition:
        long_control_state = LongCtrlState.stopping
      else:
        long_control_state = LongCtrlState.pid

    elif long_control_state == LongCtrlState.stopping:
      if starting_condition:
        long_control_state = LongCtrlState.pid

    elif long_control_state == LongCtrlState.pid:
      # 入口判据是 "车没在真的减速", 不是 "规划软了"。
      #   - 正常跟停: 规划要减速且车真的在减速 -> a_ego 明显为负 -> 不接管,
      #     全程走 pid(还带 a_ego 反馈), 曲线连续收敛, 行为与上游一致。
      #   - 蠕行死锁: 规划要 -0.46 但 a_ego ≈ 0(被蠕行扭矩抵消) -> 接管。
      #     这一条正是上一版漏掉的形状: 它只认 a_target 软下来, 而规划在死锁中
      #     从来没软过, 于是门一直关着。
      if should_stop and a_ego > CREEP_DECEL_MARGIN:
        long_control_state = LongCtrlState.stopping

  return long_control_state

class LongControl:
  def __init__(self, CP, CP_SP):
    self.CP = CP
    self.CP_SP = CP_SP
    self.long_control_state = LongCtrlState.off
    self.pid = PIDController(0.0, (CP.longitudinalTuning.kiBP, CP.longitudinalTuning.kiV),
                             rate=1 / DT_CTRL)
    self.last_output_accel = 0.0

  def reset(self):
    self.pid.reset()

  def update(self, active, CS, a_target, should_stop, accel_limits):
    """Update longitudinal control. This updates the state machine and runs a PID loop"""
    self.pid.neg_limit = accel_limits[0]
    self.pid.pos_limit = accel_limits[1]

    self.long_control_state = long_control_state_trans(self.CP_SP, active, self.long_control_state,
                                                      should_stop, CS.brakePressed,
                                                      CS.cruiseState.standstill, CS.aEgo)
    if self.long_control_state == LongCtrlState.off:
      self.reset()
      output_accel = 0.

    elif self.long_control_state == LongCtrlState.stopping:
      if CS.vEgo < STOPPING_HOLD_V:
        # 已经停住: 硬保持, 否则蠕行扭矩会把车顶走
        target_accel = self.CP.stopAccel
      elif a_target < CREEP_STOP_MAX_A_TARGET:
        # 保底减速: 至少压到 CREEP_FLOOR_ACCEL; 规划要求更强的减速时听规划的。
        # 这里刻意不再用 "车一减速就松手" 的判据 -- 松手就回到规划那个被蠕行扭矩抵消的
        # -0.46, 车马上又不减速, 于是指令会在 -1.0 与 -0.46 之间来回抖, 平均值压不住蠕行,
        # 表现出来就是 "一直在蹭、就是停不下来"。
        # 保底一直保持到 v < STOPPING_HOLD_V 转硬保持, 减速曲线是平的 -> 不点头。
        target_accel = min(a_target, CREEP_FLOOR_ACCEL)
      else:
        # 规划在要求加速 -> 绝不能被保底压住 (那是起不来步的来源)
        target_accel = a_target

      # 双向限速率: 加深和松开都不许一步到位。原实现是"只加深、不松开",
      # 所以规划要松刹车时它反而越踩越深, 而且是单调加深到 -2.0。
      max_step = STOPPING_ACCEL_RATE * DT_CTRL
      if target_accel < self.last_output_accel:
        output_accel = max(target_accel, self.last_output_accel - max_step)
      else:
        output_accel = min(target_accel, self.last_output_accel + max_step)
      self.reset()

    else:  # LongCtrlState.pid
      error = a_target - CS.aEgo
      output_accel = self.pid.update(error, speed=CS.vEgo,
                                     feedforward=a_target)

    self.last_output_accel = np.clip(output_accel, accel_limits[0], accel_limits[1])
    return self.last_output_accel
