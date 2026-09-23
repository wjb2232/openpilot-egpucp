#!/usr/bin/env bash

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1

# models get lower priority than ui
# - ui is ~5ms
# - modeld is 20ms
# - DM is 10ms
# in order to run ui at 60fps (16.67ms), we need to allow
# it to preempt the model workloads. we have enough
# headroom for this until ui is moved to the CPU.
export QCOM_PRIORITY=12

if [ -z "$AGNOS_VERSION" ]; then
  export AGNOS_VERSION="19.6.3-carrot"
fi

export STAGING_ROOT="/data/safe_staging"

# Ensure the repo venv is used no matter how this shell was started
# (build.py / params_check.py / recovery all call bare "python3").
if [ -f "$(dirname "${BASH_SOURCE[0]}")/.venv/bin/activate" ]; then
  source "$(dirname "${BASH_SOURCE[0]}")/.venv/bin/activate"
fi

# UI: 1920x1200 monitor -> big-UI canvas (2160x1080) scaled to fit (0.889)
export BIG="1"
export SCALE="0.889"
export DISPLAY=":0"
#!/usr/bin/env bash
# Jetson dev/sim mode: the Qualcomm-only camerad (spectra.cc) asserts on this
# platform, so block it and use the Python webcamerad instead; fake panda
# provides ignition + CAN. Real panda hardware (TICI/AGNOS or USB panda) is
# NOT affected: these vars only apply on non-TICI aarch64 (Jetson).
if [ "$(uname -m)" = "aarch64" ] && [ ! -e /TICI ]; then
  export SKIP_FW_QUERY="1"
  export FINGERPRINT="TOYOTA_COROLLA_TSS2"
  export PASSIVE="0"
  export BLOCK="${BLOCK:+${BLOCK},}camerad,loggerd,encoderd,dmonitoringmodeld,dmonitoringd,micd,logmessaged,manage_athenad"
  export USE_WEBCAM="1"
  export ROAD_CAM="0"
  export WIDE_CAM="1"
  export CAM_WIDTH="1344"
  export CAM_HEIGHT="760"
  export CAM_BRIGHTNESS="1.0"
fi
