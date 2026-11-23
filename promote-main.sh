#!/bin/bash
# promote-main.sh — 把台架已验证的修订晋级进车机主树（上车模式生效）
# 流程: 语法预检 → 备份主树原文件 → 断链复制台架版 → (由调用方重启 supervisor)
# 用法: bash promote-main.sh [主树路径, 默认 /data/openpilot]
# 范围: 只晋级"上车相关且已台架验证"的修订文件;
#       webcam camerad/process_config/camera 焦距等台架专用基建一律不晋级。
set -euo pipefail

MAIN="${1:-/data/openpilot}"
BENCH="/data/openpilot_egpucp"
STAMP=$(date +%Y%m%d_%H%M%S)
PY=/usr/bin/python3.12

FILES=(
  openpilot/selfdrive/carrot/sensing/smalldetd.py        # 修订22/24/26 检测净化
  openpilot/selfdrive/ui/onroad/targets_overlay.py       # 修订21/22/24 目标框
  openpilot/selfdrive/ui/onroad/model_renderer.py        # 修订23/25 轨迹渲染
  openpilot/selfdrive/controls/plannerd.py               # 修订27 S型绕行接轨迹
  openpilot/selfdrive/controls/lib/lateral_planner.py    # 修订27 S型绕行接轨迹
  openpilot/selfdrive/controls/controlsd.py              # 修订28b laneless 差分曲率叠加
)

echo "== 语法预检（台架版, python3.12）=="
for f in "${FILES[@]}"; do
  $PY -m py_compile "$BENCH/$f"
done
echo "预检通过: ${#FILES[@]} 个文件"

echo "== 备份并同步到主树 $MAIN =="
BAK="$MAIN/.bak_promote_$STAMP"
mkdir -p "$BAK"
for f in "${FILES[@]}"; do
  if [ ! -f "$MAIN/$f" ]; then echo "!! 主树缺文件: $f, 跳过"; continue; fi
  mkdir -p "$BAK/$(dirname "$f")"
  cp --preserve=mode,timestamps "$MAIN/$f" "$BAK/$f"
  rm -f "$MAIN/$f"          # 断开任何残留硬链接, 绝不原地写
  cp "$BENCH/$f" "$MAIN/$f"
  chmod --reference="$BENCH/$f" "$MAIN/$f"
  chown --reference="$BAK/$f" "$MAIN/$f" 2>/dev/null || true
  echo "  晋级 $f  (原文件备份: $BAK/$f)"
done

echo "== 晋级后校验 =="
fail=0
for f in "${FILES[@]}"; do
  a=$(md5sum "$BENCH/$f" | cut -d' ' -f1)
  b=$(md5sum "$MAIN/$f" | cut -d' ' -f1)
  if [ "$a" = "$b" ]; then echo "  OK $f"; else echo "  !! md5 不一致 $f"; fail=1; fi
done
[ "$fail" = 0 ] || { echo "校验失败, 回滚: cp -a $BAK/. $MAIN/"; exit 1; }
echo "全部一致。备份目录: $BAK"
echo "重启生效: sudo -n systemctl restart carrot-supervisor.service"
