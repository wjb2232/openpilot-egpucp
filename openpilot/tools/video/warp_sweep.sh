#!/bin/bash
# ROAD_WARP_F 扫参自选工具 — 几何优先选点规则
# 用法: warp_sweep.sh /data/videos/xxx.mp4 [700 900 1100 1300 1500]
# 评分: lane1/2 置信度均值; 选点: 分数差 <=0.05 视为并列, 并列取最小 F。
# 原因: F 越大中心放大越强, 置信度越高但弯道几何可能被拉糊(720p 素材实测
# F=1300 置信度 0.98 但轨迹带横向穿出路面; F=1100 置信度 0.93 且几何正确)。
VIDEO="${1:?usage: warp_sweep.sh <video> [F...]}"; shift
FS=("${@:-700 900 1100 1300 1500}")
RES=/tmp/warp_sweep_results.txt; : > "$RES"
for V in "${FS[@]}"; do
  cd /data/openpilot_egpucp
  ROAD_WARP_F=$V DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority \
    ./start-video.sh "$VIDEO" > "/tmp/start_sweep_$V.log" 2>&1
  sleep 40
  SCORE=$(PYTHONPATH=/data/openpilot_egpucp/pydeps:/data/openpilot_egpucp:/data/openpilot_egpucp/openpilot \
    timeout 30 /usr/bin/python3.12 - <<'PY' 2>/dev/null
import cereal.messaging as messaging, numpy as np, time
sm = messaging.SubMaster(["modelV2"])
t0 = time.monotonic()
while time.monotonic()-t0 < 6: sm.update(0)
p = np.array(sm["modelV2"].laneLineProbs)
print("%.3f %.2f %.2f" % ((float(p[1])+float(p[2]))/2, p[1], p[2]))
PY
)
  echo "F=$V score/lane1/lane2: $SCORE" | tee -a "$RES"
done
/usr/bin/python3.12 - "$RES" <<'PY'
import sys, re
rows = []
for line in open(sys.argv[1]):
  m = re.match(r"F=(\d+) score/lane1/lane2: ([\d.]+) ([\d.]+) ([\d.]+)", line)
  if m: rows.append((int(m.group(1)), float(m.group(2))))
best = max(s for _, s in rows)
pick = min(f for f, s in rows if s >= best - 0.05)   # 并列窗口 0.05, 取最小 F
print("选定 ROAD_WARP_F=%d (最高分 %.3f, 并列窗口内取最小 F)" % (pick, best))
open("/tmp/warp_sweep_pick.txt", "w").write(str(pick))
PY
