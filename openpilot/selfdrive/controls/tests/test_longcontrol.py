from openpilot.common.test import OpenpilotTestCase
from openpilot.cereal import custom
from openpilot.selfdrive.controls.lib.longcontrol import LongCtrlState, long_control_state_trans


class TestLongControlStateTransition(OpenpilotTestCase):

  def test_stay_stopped(self):
    CP_SP = custom.CarParamsSP.new_message()
    active = True
    current_state = LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=True, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=True, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=False, cruise_standstill=True,
                             a_ego=0.0)
    assert next_state == LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.pid
    active = False
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.off

  def test_engage(self):
    CP_SP = custom.CarParamsSP.new_message()
    active = True
    current_state = LongCtrlState.off
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=True, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=True, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=False, cruise_standstill=True,
                             a_ego=0.0)
    assert next_state == LongCtrlState.stopping
    next_state = long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.0)
    assert next_state == LongCtrlState.pid

  def test_pid_entry_hysteresis(self):
    CP_SP = custom.CarParamsSP.new_message()
    active = True
    current_state = LongCtrlState.pid

    # 正常跟停: 规划要减速, 车也真的在减速 -> 不许接管, 留在 pid 让它自己把车管到停
    assert long_control_state_trans(CP_SP, active, current_state,
                             should_stop=True, brake_pressed=False, cruise_standstill=False,
                             a_ego=-0.8) == LongCtrlState.pid
    # 蠕行死锁: 规划顶着 -0.46 要减速, 但 a_ego ≈ 0 (被蠕行扭矩抵消) -> 这才是接管的形状。
    # 注意判据看的是 a_ego 而不是 a_target: 只看 a_target 会以为规划还在认真减速而漏接。
    assert long_control_state_trans(CP_SP, active, current_state,
                             should_stop=True, brake_pressed=False, cruise_standstill=False,
                             a_ego=-0.02) == LongCtrlState.stopping
    # 规划没在要减速但车也没减速 (规划软、车匀速蹭): 同样接管
    assert long_control_state_trans(CP_SP, active, current_state,
                             should_stop=True, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.0) == LongCtrlState.stopping
    # 不该停就不进
    assert long_control_state_trans(CP_SP, active, current_state,
                             should_stop=False, brake_pressed=False, cruise_standstill=False,
                             a_ego=0.5) == LongCtrlState.pid
    # 入口判据是单向的: 已进 stopping 后只由 starting_condition 决定退出
    assert long_control_state_trans(CP_SP, active, LongCtrlState.stopping,
                             should_stop=True, brake_pressed=False, cruise_standstill=False,
                             a_ego=-0.8) == LongCtrlState.stopping
    # 起步放行与 a_ego 无关
    assert long_control_state_trans(CP_SP, active, LongCtrlState.stopping,
                             should_stop=False, brake_pressed=False, cruise_standstill=False,
                             a_ego=-0.8) == LongCtrlState.pid
