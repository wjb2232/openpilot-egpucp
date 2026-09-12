import numpy as np
from openpilot.common.constants import ACCELERATION_DUE_TO_GRAVITY
from openpilot.common.realtime import DT_CTRL, DT_MDL

MIN_SPEED = 1.0
CONTROL_N = 17
CAR_ROTATION_RADIUS = 0.0
# This is a turn radius smaller than most cars can achieve
MAX_CURVATURE = 0.2
MIN_STABLE_DELAY = 0.3

# EU guidelines
MAX_LATERAL_JERK = 5.0  # m/s^3
MAX_LATERAL_ACCEL_NO_ROLL = 3.0  # m/s^2


# --- 停车判据 -----------------------------------------------------------------
# 上游判据 v_ego < 0.3 在蠕行工况下会死锁: 低速时变速箱蠕行扭矩是正向的, 会把 MPC
# 那个很弱的负 a_target 抵消掉, v_ego 于是卡在 0.3 以上永不下降, should_stop 永远
# 为假, 而那唯一能压过蠕行的 stopping 状态也就永远不使能 -> 车一直蹭着往前走。
#
# 但补判据必须极其小心, 因为 should_stop 不只是 "该不该停" 的提示, 它同时还是:
#   - LongControl 里 stopping -> pid 的放行条件 (starting_condition 要求 not should_stop)
#   - controlsd 里 CC.cruiseControl.resume 的放行条件 (要求 not shouldStop)
# 也就是说 should_stop 一旦 "多真了一点", 代价不是停早了, 而是车起不来步。
#
# 所以下面两条补判据都收在同一件事上: 规划既没在减速、也没在加速。
#   - 正常跟停时 a_target 很负 (规划正在减速)  -> 补判据不参与, 行为与上游完全一致
#   - 正常起步时 a_target 为正 (规划要加速)    -> 补判据不参与, 绝不挡起步
#   - 只有 "车已经慢到 1 m/s 还停不下来、规划又不减速" 这个死锁窗口才补判据
#
# 但上游那条 v_ego < 0.3 的条款只看瞬时 a_target, 温和起步时 a_target 同样在 0.1 以下,
# 于是它会把上面两条的判别力用 or 短路掉。所以 should_start_from_plan() 是一个否决:
# 只要规划在明确加速, 无论哪条判据为真都一律不报停车。

# 规划的减速请求弱于此值, 才算 "它不打算继续减速了"。必须与 longcontrol.py 里
# stopping 接管控制权的阈值共用同一个数, 否则会出现 "判据放行但控制律不接管"
# (或者反过来) 的真空区。
STOPPING_MIN_BRAKE = 0.3  # m/s^2

# should_stop 允许的 a_target 上限: 规划在要求加速时绝不判停, 否则会压住起步
CREEP_STOP_MAX_A_TARGET = 0.1  # m/s^2

# 1) 蠕行规则: 正前方很近的地方有基本静止的车, 自己也很慢, 且规划处于
#    "既不减速也不加速" 的窄窗口内
CREEP_STOP_MAX_V_EGO = 1.0   # m/s
CREEP_STOP_MAX_D_REL = 2.5   # m
CREEP_STOP_MAX_V_LEAD = 1.0  # m/s

# 2) 规划规则: MPC 自己规划的速度轨迹在作动器时域和其后 1 s 都已接近 0, 说明这次
#    规划就是在执行一次停车, 与 v_ego 现在是多少无关。不依赖雷达, 因此也覆盖
#    停车线、红灯、e2e 停车。
CREEP_STOP_V_PLANNED = 0.5          # m/s
CREEP_STOP_PLANNED_LOOKAHEAD = 1.0  # s
# 只看速度不够: 从静止蠕行起步时, 规划在 t+1.5 s 的速度同样可能低于 0.5 m/s,
# 但那时规划是在加速, 不是停车。用该时刻的规划加速度把两者分开。
CREEP_STOP_MAX_PLANNED_ACCEL = 0.1  # m/s^2


def should_stop(v_ego: float, a_target: float, d_rel=None, v_lead=None) -> bool:
  if v_ego < 0.3 and a_target < CREEP_STOP_MAX_A_TARGET:
    return True
  # 兼容只传两个参数的旧调用点 (modeld / joystickd / maneuversd 等)
  if d_rel is None or v_lead is None:
    return False
  return bool(-STOPPING_MIN_BRAKE < a_target < CREEP_STOP_MAX_A_TARGET
              and v_ego < CREEP_STOP_MAX_V_EGO and d_rel < CREEP_STOP_MAX_D_REL
              and v_lead < CREEP_STOP_MAX_V_LEAD)


def should_stop_from_plan(v_plan, a_plan, t_idxs, action_t: float = DT_MDL,
                          v_planned: float = CREEP_STOP_V_PLANNED) -> bool:
  if v_plan is None or len(v_plan) == 0 or a_plan is None or len(a_plan) == 0:
    return False
  t_look = action_t + CREEP_STOP_PLANNED_LOOKAHEAD
  v_t = float(np.interp(action_t, t_idxs, v_plan))
  v_t1 = float(np.interp(t_look, t_idxs, v_plan))
  a_t1 = float(np.interp(t_look, t_idxs, a_plan))
  return bool(v_t < v_planned and v_t1 < v_planned
              and a_t1 < CREEP_STOP_MAX_PLANNED_ACCEL)

def should_start_from_plan(v_plan, a_plan, t_idxs, action_t: float = DT_MDL) -> bool:
  """规划在作动器时域之后已经在明确加速、且速度在上升 -> 这是一次起步, 不是停车。

  用于否决 should_stop: 上游那条 v_ego < 0.3 的条款只看瞬时 a_target, 温和起步时
  a_target 同样在 0.1 以下, 会把规划规则的判别力短路掉。这里看的是 t+1.5 s 的规划
  轨迹, 那个时刻能明确区分 "正在起步" 和 "正在停车"。

  判据必须是 "规划在加速" 这个正面信号, 不能写成 "规划 1.5 s 内没停下"
  (v_t1 > 某值) -- 后者只是 "规划停车" 的否命题, 太松: 0.9 m/s 跟在停住的前车后面
  时规划可能就是不减速, 那并不是起步, 拿它去否决蠕行判据会变成漏停。
  """
  if v_plan is None or len(v_plan) == 0 or a_plan is None or len(a_plan) == 0:
    return False
  t_look = action_t + CREEP_STOP_PLANNED_LOOKAHEAD
  v_t = float(np.interp(action_t, t_idxs, v_plan))
  v_t1 = float(np.interp(t_look, t_idxs, v_plan))
  a_t1 = float(np.interp(t_look, t_idxs, a_plan))
  return bool(a_t1 > CREEP_STOP_MAX_PLANNED_ACCEL and v_t1 > v_t)

def clamp(val, min_val, max_val):
  clamped_val = float(np.clip(val, min_val, max_val))
  return clamped_val, clamped_val != val

def smooth_value(val, prev_val, tau, dt=DT_MDL):
  alpha = 1 - np.exp(-dt/tau) if tau > 0 else 1
  return alpha * val + (1 - alpha) * prev_val

def clip_curvature(v_ego, prev_curvature, new_curvature, roll) -> tuple[float, bool]:
  # This function respects ISO lateral jerk and acceleration limits + a max curvature
  v_ego = max(v_ego, MIN_SPEED)
  max_curvature_rate = MAX_LATERAL_JERK / (v_ego ** 2)  # inexact calculation, check https://github.com/commaai/openpilot/pull/24755
  new_curvature = np.clip(new_curvature,
                          prev_curvature - max_curvature_rate * DT_CTRL,
                          prev_curvature + max_curvature_rate * DT_CTRL)

  roll_compensation = roll * ACCELERATION_DUE_TO_GRAVITY
  max_lat_accel = MAX_LATERAL_ACCEL_NO_ROLL + roll_compensation
  min_lat_accel = -MAX_LATERAL_ACCEL_NO_ROLL + roll_compensation
  new_curvature, limited_accel = clamp(new_curvature, min_lat_accel / v_ego ** 2, max_lat_accel / v_ego ** 2)

  new_curvature, limited_max_curv = clamp(new_curvature, -MAX_CURVATURE, MAX_CURVATURE)
  return float(new_curvature), limited_accel or limited_max_curv


def get_accel_from_plan(speeds, accels, t_idxs, action_t=DT_MDL):
  if len(speeds) == len(t_idxs):
    v_now = speeds[0]
    a_now = accels[0]
    if action_t < MIN_STABLE_DELAY:
      v_target = v_now + (action_t / MIN_STABLE_DELAY) * (np.interp(MIN_STABLE_DELAY, t_idxs, speeds) - v_now)
    else:
      v_target = np.interp(action_t, t_idxs, speeds)
    a_target = 2 * (v_target - v_now) / (action_t) - a_now
  else:
    a_target = 0.0
  return a_target

def curv_from_psis(psi_target, psi_rate, vego, action_t):
  vego = np.clip(vego, MIN_SPEED, np.inf)
  curv_from_psi = psi_target / (vego * action_t)
  return 2*curv_from_psi - psi_rate / vego

def get_curvature_from_plan(yaws, yaw_rates, t_idxs, vego, action_t):
  if action_t < MIN_STABLE_DELAY:
    psi_target = (action_t / MIN_STABLE_DELAY) * np.interp(MIN_STABLE_DELAY, t_idxs, yaws)
  else:
    psi_target = np.interp(action_t, t_idxs, yaws)
  psi_rate = yaw_rates[0]
  return curv_from_psis(psi_target, psi_rate, vego, action_t)
