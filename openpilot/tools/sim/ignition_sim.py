#!/usr/bin/env python3
"""c3 shadow-test ignition/CAN simulator - Honda Civic 2022 (matches tn tree FINGERPRINT=HONDA_CIVIC_2022).

Publishes pandaStates (ignition=True) + Honda CAN frames at ~100Hz by driving
the fork's own SimulatedCar with a static SimulatorState.
Used with NOBOARD=1 so real pandad is skipped; card fingerprints via
FINGERPRINT=HONDA_CIVIC_2022 + SKIP_FW_QUERY=1.

2026-10-17 enhancement: auto cruise-button sequence (otherwise
cruiseState.enabled stays False forever, UI locks in disabled state and
does not draw the trajectory path):
  t=2s   : CRUISE_BUTTONS=MAIN(1)      -> open cruise main switch (cruiseState.available)
  t=4s   : CRUISE_BUTTONS=RES_ACCEL(4) -> accelCruise request -> controlsd preEnabled
  then 0 (released). Restart this script to re-enable.
"""
import os
import sys
import time

sys.path.insert(0, "/data/openpilot_tn")

from openpilot.tools.sim.lib.common import SimulatorState, vec3
from openpilot.tools.sim.lib.simulated_car import SimulatedCar


def main():
  state = SimulatorState()
  state.valid = True
  state.ignition = True
  # gentle movement so the model sees motion cues (speed = |velocity|)
  state.velocity = vec3(5.0, 0.0, 0.0)
  state.steering_angle = 0.05

  sim = SimulatedCar()
  t0 = time.monotonic()
  print("ignition_sim started: pandaStates(ignition=True) + Honda CAN @ ~100Hz", flush=True)

  while True:
    now = time.monotonic() - t0
    # cruise button sequence: MAIN at 2s (1s hold), RES_ACCEL at 4s (0.5s pulse),
    # then keep is_engaged=True so the PCM replies ACC_STATUS=1 (Honda is
    # pcmCruise: enabled comes from ACC_STATUS, not from the button itself).
    if 2.0 <= now < 3.0:
      state.cruise_button = 1   # MAIN
    elif 4.0 <= now < 4.5:
      state.cruise_button = 4   # RES_ACCEL
    else:
      state.cruise_button = 0   # none
    if now >= 4.5:
      # selfdrived engages on the RISING EDGE of cruiseState.enabled (pcmEnable).
      # The stack starts after ignition_sim has been on for a while, so a
      # constant True is never seen as an edge. Toggle: 2s off, 28s on,
      # repeating — every cycle produces a fresh enable edge.
      state.is_engaged = (int(now - 4.5) % 300) >= 2
    try:
      sim.update(state)
    except Exception as e:
      print(f"ignition_sim error: {e}", flush=True)
    time.sleep(0.01)


if __name__ == "__main__":
  main()