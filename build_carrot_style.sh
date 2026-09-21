#!/usr/bin/env bash
# Compile the Cinque V2 big model "carrot-style": warp on the internal QCOM GPU,
# supercombo body on the eGPU (AMD), so only the small warped tensor crosses the
# USB link instead of full camera frames every frame.
#
# Requires: ignition ON (eGPU has 12V), car parked, tens of minutes.
# The eGPU is exclusive, so the chestnut bundle is disabled while compiling and
# modeld falls back to the internal model meanwhile.
#
# NOTE: openpilot wipes untracked files inside /data/openpilot at startup, so the
# helper scripts live in /data/carrot_build.
set -u
cd /data/openpilot || exit 1

BUILD_DIR=/data/carrot_build
PY=/usr/local/venv/bin/python3
export PYTHONPATH=/data/openpilot
export PYTHONUNBUFFERED=1
ONNX=/data/media/0/models/big_driving_supercombo-09d080f36965bb2a.onnx
OUT=/data/media/0/models/cinque_v2_carrot_style.pkl

if [ ! -f "$ONNX" ]; then echo "missing ONNX: $ONNX"; exit 1; fi
if [ ! -f "$BUILD_DIR/compile_carrot_style.py" ]; then echo "missing $BUILD_DIR/compile_carrot_style.py"; exit 1; fi

# 1) free the eGPU: hide the chestnut bundle so modeld uses the internal model
if [ -f /data/params/d/ModelManager_ActiveBundleChestnut ]; then
  cp -f /data/params/d/ModelManager_ActiveBundleChestnut /data/params/d/ModelManager_ActiveBundleChestnut.carrotbak
  mv -f /data/params/d/ModelManager_ActiveBundleChestnut /tmp/ModelManager_ActiveBundleChestnut.disabled
  echo "chestnut bundle disabled"
fi
pkill -f modeld_tinygrad
sleep 15

# 2) wait for the eGPU to become available
# NOTE: must import modeld_v2.compile_modeld first — it patches tinygrad's firmware
# loader to use /lib/firmware/*.zst instead of downloading (network is blocked).
for i in $(seq 1 12); do
  if DEV=AMD "$PY" -c "import openpilot.sunnypilot.modeld_v2.compile_modeld; from tinygrad import Device; Device['AMD']; print('amd ok')" 2>/dev/null | grep -q "amd ok"; then
    echo "eGPU ready after ${i} attempt(s)"
    break
  fi
  echo "waiting for eGPU ($i)..."
  sleep 10
done

# 3) compile
DEV=AMD WARP_DEV=QCOM FLOAT16=1 JIT_BATCH_SIZE=0 GMMU=0 TC_OPT=2 \
  "$PY" "$BUILD_DIR/compile_carrot_style.py" \
  --onnx "$ONNX" --output "$OUT" \
  --model-size 512x256 --camera-resolutions 1928x1208 1344x760 --frame-skip 4 \
  2>&1 | tee /data/compile_carrot.log
COMPILE_RC=$?

# 4) install + restore
if [ -s "$OUT" ]; then
  "$PY" "$BUILD_DIR/install_carrot_pkl.py" 2>&1 | tee /data/install_carrot.log
else
  echo "compile failed or produced no output (rc=$COMPILE_RC)"
fi

if [ -f /tmp/ModelManager_ActiveBundleChestnut.disabled ]; then
  mv -f /tmp/ModelManager_ActiveBundleChestnut.disabled /data/params/d/ModelManager_ActiveBundleChestnut
  echo "chestnut bundle restored"
fi
pkill -f modeld_tinygrad
echo "done; modeld restarts and loads the new pkl"
