#!/usr/bin/env bash
# 自动构建 FP16 TRT plan(选模/换模后一键构建)
# 用法: auto_build_fp16.sh <model_dir> <onnx_name> <plan_name>
#   例: auto_build_fp16.sh /data/openpilot_c3/openpilot/selfdrive/modeld/models big_driving_supercombo.onnx big_driving_supercombo_trt.plan
#
# 逻辑: 输入 UINT8→FP16(TRT 10.16 importer 拒收 UINT8)→ trtexec --fp16 构建。
# 权重 FP32/FP16 都适用: --fp16 交给 TensorRT 自动转。

set -e
MODEL_DIR="$1"
ONNX_NAME="$2"
PLAN_NAME="$3"
[ -d "$MODEL_DIR" ] || { echo "目录不存在: $MODEL_DIR"; exit 1; }
[ -n "$ONNX_NAME" ] && [ -n "$PLAN_NAME" ] || { echo "用法: $0 <dir> <onnx> <plan>"; exit 1; }

cd "$MODEL_DIR"
ONNX_PATH="$MODEL_DIR/$ONNX_NAME"
PLAN_PATH="$MODEL_DIR/$PLAN_NAME"
FP16IN_PATH="$MODEL_DIR/${ONNX_NAME%.onnx}_fp16in.onnx"
BUILD_SCRIPT="$(dirname "$(readlink -f "$0")")/fp16in_onnx.py"

[ -f "$ONNX_PATH" ] || { echo "ONNX 不存在: $ONNX_PATH"; exit 1; }

# plan 已存在且比 onnx 新 → 跳过
if [ -f "$PLAN_PATH" ] && [ "$PLAN_PATH" -nt "$ONNX_PATH" ]; then
  echo "plan 已是最新, 跳过: $PLAN_PATH"
  exit 0
fi

echo "=== [1/3] 检查/转换输入类型 (UINT8→FP16) ==="
if /usr/bin/python3.12 "$BUILD_SCRIPT" "$ONNX_PATH" "$FP16IN_PATH"; then
  ONNX_INPUT="$FP16IN_PATH"
else
  echo "输入无 UINT8(或转换失败), 直接用原 ONNX"
  ONNX_INPUT="$ONNX_PATH"
fi

echo "=== [2/3] trtexec 构建 FP16 plan ($(date +%H:%M)) ==="
/usr/bin/trtexec --onnx="$ONNX_INPUT" --fp16 --saveEngine="$PLAN_PATH" \
  --builderOptimizationLevel=4 --memPoolSize=workspace:2048

echo "=== [3/3] 完成 ==="
ls -lh "$PLAN_PATH"
