#!/usr/bin/env bash
# 克隆即自愈: TRT 栈一键部署 (幂等, 可重复执行无副作用)
#
# 场景: 重刷镜像后克隆本仓库, carrot_supervisor.sh 启动时自动调用本脚本,
#       也可手动执行: bash scripts/usbgpu/deploy_stack.sh [--dry-run]
# 做什么:
#   1) TRT python 绑定+trtexec 工具链 deb: 已装则跳过; 缺失时优先 apt 在线装
#      (镜像自带 repo.download.nvidia.com/jetson 源, libnvinfer11 ~2.36GB 在线
#      拉取); apt 不可达再用 assets/debs 小包兜底 dpkg -i (小包不含 libnvinfer11,
#      纯离线装不齐时只告警不阻塞, 栈自动退回 tinygrad 旧路径)
#   2) plan 就位: yolo/tl 引擎从 assets/plans 重组/复制到 /data/trt_build
#      (目标缺失或 sha256 不符才写入); supercombo 引擎直接用仓内
#      modeld/models/big_driving_supercombo_trt.plan, 无需复制
#   3) 门控参数置 "1" (SmalldetEnabled/TlDetEnabled/AvoidanceEnabled/DevTargetsOverlay)
#   4) 兜底: 目标 plan 仍缺失且 trtexec 可用时, 用仓内 onnx 按编译日志原命令重建
# 免责: 所有缺失都只告警, 不阻塞栈启动。
#
# 铁律(血泪教训): 装完 TRT deb 后必须重启 carrot-supervisor.service —— manager
# 启动早于 dist-packages 目录创建会导致其 sys.path 永久缺失新包路径。本脚本被
# supervisor 启动流程调用时 manager 尚未起, 天然满足; 手动执行时见末尾提示。
set -u
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
say() { echo "[deploy_stack] $*"; }
run() { if [ "$DRY" = 1 ]; then say "DRY: $*"; else "$@"; fi }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ASSETS="$ROOT/scripts/usbgpu/assets"
PARAMS_D="${PARAMS_D:-/data/params/d}"
TRT_BUILD="${TRT_BUILD:-/data/trt_build}"
MODEL_DIR="$ROOT/openpilot/selfdrive/modeld/models"
YOLO_ONNX="$ROOT/openpilot/selfdrive/carrot/radar_motion/models"
TL_ONNX="$ROOT/openpilot/selfdrive/carrot/radar_motion/models"
GATES=(SmalldetEnabled TlDetEnabled AvoidanceEnabled DevTargetsOverlay)
TRT_JUST_INSTALLED=0

# ---------- 1) TRT deb ----------
# 必须校验"已配置"状态而非仅存在: 失败兜底的 dpkg -i 会留下 unpacked 未配置态,
# dpkg -s 对其返回成功, 若不区分会导致失败后永不重试 apt
deb_ok() { [ "$(dpkg-query -W -f='${Status}' "$1" 2>/dev/null)" = "install ok installed" ]; }
need_trt=0
for p in python3-libnvinfer libnvinfer-bin; do
  deb_ok "$p" || need_trt=1
done
if [ "$need_trt" = 0 ]; then
  say "TRT deb 已装, 跳过"
else
  say "TRT deb 缺失, 尝试 apt 在线安装 (libnvinfer11 ~2.36GB, 走镜像自带 NVIDIA jetson 源)"
  if [ "$DRY" = 1 ]; then
    say "DRY: sudo apt-get install -y --no-install-recommends python3-libnvinfer libnvinfer-bin"
  else
    if ! sudo apt-get install -y --no-install-recommends python3-libnvinfer libnvinfer-bin; then
      say "apt 失败(可能缺包列表), apt-get update 后重试一次"
      sudo apt-get update && sudo apt-get install -y --no-install-recommends python3-libnvinfer libnvinfer-bin
    fi
    deb_ok python3-libnvinfer && TRT_JUST_INSTALLED=1
  fi
  if ! deb_ok python3-libnvinfer; then
    say "apt 不可用, 用 assets/debs 小包兜底 (不含 libnvinfer11, 装不齐属预期)"
    run sudo dpkg -i "$ASSETS"/debs/*.deb || true
  fi
  deb_ok python3-libnvinfer && deb_ok libnvinfer-bin \
    || say "警告: TRT 仍未装齐, 栈将退回 tinygrad 路径; 联网后重跑本脚本即可补齐"
fi

# ---------- 2) plan 就位 ----------
ensure_plan() {  # $1 = /data/trt_build 内目标文件名
  local name="$1" want have="" src="$ASSETS/plans/$1"
  want="$(awk -v n="$name" '$2==n{print $1}' "$ASSETS/plans/plans.sha256" 2>/dev/null)"
  if [ -f "$TRT_BUILD/$name" ]; then
    have="$(sha256sum "$TRT_BUILD/$name" | cut -d' ' -f1)"
  fi
  if [ -n "$want" ] && [ "$have" = "$want" ]; then
    say "$name 已就位, 跳过"
    return 0
  fi
  say "写入 $TRT_BUILD/$name (现状: ${have:-缺失})"
  [ "$DRY" = 1 ] && { say "DRY: 重组/复制 $name"; return 0; }
  mkdir -p "$TRT_BUILD"
  if ls "$src".part* >/dev/null 2>&1; then
    cat "$src".part* > "$TRT_BUILD/$name.tmp$$" && mv -f "$TRT_BUILD/$name.tmp$$" "$TRT_BUILD/$name"
  elif [ -f "$src" ]; then
    cp -f "$src" "$TRT_BUILD/$name.tmp$$" && mv -f "$TRT_BUILD/$name.tmp$$" "$TRT_BUILD/$name"
  else
    say "警告: 仓库内缺 $name 资产"
    return 1
  fi
  have="$(sha256sum "$TRT_BUILD/$name" | cut -d' ' -f1)"
  if [ -n "$want" ] && [ "$have" != "$want" ]; then
    say "警告: $name 写入后 sha256 不符, 重建兜底见步骤4"
    return 1
  fi
  return 0
}

ensure_plan yolo11n_gpu_fp16.plan
ensure_plan tl_own_best_fp16.plan

# supercombo 引擎直接用仓内路径, 只做存在性检查
if [ -f "$MODEL_DIR/big_driving_supercombo_trt.plan" ]; then
  say "supercombo plan 在仓内就位, 跳过"
else
  say "警告: 缺 $MODEL_DIR/big_driving_supercombo_trt.plan (clone 不完整?)"
fi

# ---------- 2.5) N16Nav plan: local_models.json 登记的绝对路径, 仓内分块重组 ----------
# 777MB 超 GitHub 单文件限制, 仓库存 45MB 分块(45*1024*1024, file_chunker.py 切割),
# 此处按序重组到登记路径; sha 校验防分块缺失/损坏
N16_DIR="${N16_DIR:-/home/nvidia/.comma/media/0/models}"
N16_PLAN="$N16_DIR/big_driving_n16_trt.plan"
N16_SHA="$(awk '$2=="big_driving_n16_trt.plan"{print $1}' "$ASSETS/plans/plans.sha256" 2>/dev/null)"
ensure_n16() {
  if [ ! -f "$N16_DIR/big_driving_n16_trt_meta.json" ] && [ -f "$ASSETS/plans/big_driving_n16_trt_meta.json" ]; then
    say "写入 $N16_DIR/big_driving_n16_trt_meta.json"
    run mkdir -p "$N16_DIR"
    run cp -f "$ASSETS/plans/big_driving_n16_trt_meta.json" "$N16_DIR/"
  fi
  if [ -f "$N16_PLAN" ]; then
    have="$(sha256sum "$N16_PLAN" | cut -d' ' -f1)"
    if [ "$have" = "$N16_SHA" ]; then
      say "n16 plan 已就位, 跳过"
      return 0
    fi
    say "n16 plan sha 不符 (现: ${have:-无}), 重组覆盖"
  else
    say "写入 $N16_PLAN (仓内分块重组)"
  fi
  [ "$DRY" = 1 ] && { say "DRY: 重组 $N16_PLAN"; return 0; }
  mkdir -p "$N16_DIR"
  cat "$ASSETS/plans/big_driving_n16_trt.plan".chunk[0-9]*of[0-9]* > "$N16_PLAN.tmp$$" \
    && mv -f "$N16_PLAN.tmp$$" "$N16_PLAN" \
    || { say "警告: 仓内缺 n16 分块资产"; return 1; }
  have="$(sha256sum "$N16_PLAN" | cut -d' ' -f1)"
  [ "$have" = "$N16_SHA" ] || say "警告: n16 plan 重组后 sha256 不符"
}
ensure_n16

# ---------- 3) 门控参数 ----------
for k in "${GATES[@]}"; do
  val="$(cat "$PARAMS_D/$k" 2>/dev/null || true)"
  if [ "$val" != "1" ]; then
    say "参数 $k := 1 (原值: ${val:-无})"
    if [ "$DRY" = 1 ]; then
      say "DRY: echo 1 > $PARAMS_D/$k"
    else
      mkdir -p "$PARAMS_D"
      printf '1' > "$PARAMS_D/$k.tmp$$" && mv -f "$PARAMS_D/$k.tmp$$" "$PARAMS_D/$k"
    fi
  fi
done

# ---------- 4) 重建兜底 (仅当目标 plan 缺失且 trtexec 可用) ----------
rebuild_if_missing() {  # $1=plan绝对路径 $2=onnx绝对路径
  local plan="$1" onnx="$2"
  [ -f "$plan" ] && return 0
  command -v trtexec >/dev/null 2>&1 || { say "警告: $plan 缺失且无 trtexec, 跳过重建"; return 1; }
  [ -f "$onnx" ] || { say "警告: $plan 缺失且无源 onnx, 跳过重建"; return 1; }
  say "重建 $plan (trtexec, 约5-15分钟)"
  [ "$DRY" = 1 ] && { say "DRY: trtexec --onnx=$onnx --saveEngine=$plan"; return 0; }
  trtexec --onnx="$onnx" --saveEngine="$plan" && say "重建完成" || say "警告: 重建失败"
}
rebuild_if_missing "$TRT_BUILD/yolo11n_gpu_fp16.plan" "$YOLO_ONNX/yolo11m_640_fp16w.onnx"
rebuild_if_missing "$TRT_BUILD/tl_own_best_fp16.plan" "$TL_ONNX/tl_traffic_light_fp16w.onnx"
rebuild_if_missing "$MODEL_DIR/big_driving_supercombo_trt.plan" "$MODEL_DIR/driving_supercombo_fp16in.onnx"

# ---------- 收尾 ----------
if [ "$TRT_JUST_INSTALLED" = 1 ] && pgrep -f '[m]anager\.py' >/dev/null 2>&1; then
  say "TRT 新装且栈在跑: 请执行 sudo systemctl restart carrot-supervisor.service 使新库生效"
fi
say "完成"
