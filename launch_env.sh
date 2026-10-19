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
  export AGNOS_VERSION="19.8-carrot-bt2"
fi

export STAGING_ROOT="/data/safe_staging"

source /data/openpilot_c3/.venv/bin/activate

# Jetson/Orin Python runtime tuning (doc 14.6, field-verified)
export PYTHONHASHSEED=42
export PYTHONMALLOC=malloc
export MALLOC_ARENA_MAX=2
export PYTHONOPTIMIZE=1
export PYTHONNOUSERSITE=1

# --- webcamerad (GMSL via v4l2 direct, field-verified) ---
export USE_WEBCAM=1
export ROAD_CAM=0
export WIDE_CAM=1
export CAM_WIDTH=1344
export CAM_HEIGHT=760

# --- c3 UI scaling for 132 touch panel (1024x600) ---
# canvas 2160x1080 x 0.474 = 1024x512; fonts hardcoded for 2160
export BIG=1
export SCALE=0.474
export UI_WIDTH=2160
export UI_HEIGHT=1080
# X display for the UI process (gnome session on :0); tmux/ssh-launched stacks
# inherit neither DISPLAY nor XAUTHORITY, leaving UI windowless & spin-locked
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority
export UNDECORATED=1
