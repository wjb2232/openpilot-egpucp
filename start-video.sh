#!/usr/bin/env bash
# 用视频作为相机输入启动 132 的 openpilot
# 素材自标定: 视频源焦距假设(1928宽基准), 源中心40°窗放大到训练视角; 0=关闭
export ROAD_WARP_F="${ROAD_WARP_F:-1100}"
# ROAD_WARP_PY = warp 采样窗垂直偏移(px): pysweep 扫参选定 +30(score 1.822, 与+60 差0.042<0.1 并列取小|PY|;
# -60 异常档(带宽3.37m/ok0.85)被 conf 0.80 保底门拦下)。0=画面几何中心。
export ROAD_WARP_PY="${ROAD_WARP_PY:-30}"
# ROAD_VP_LOCK=1: 消失点锚定动态 warp(P1-2): 采样窗水平中心跟随弯道消失点, 远端路面保持居中;
# VP 估计(480宽 Canny+Hough)+EMA+限幅±30px+死区全在输入侧闭环, 摊薄开销<2ms/帧。0=A/B 基线。
export ROAD_VP_LOCK="${ROAD_VP_LOCK:-1}"
# ROAD_CLAHE=1: 亮度门控暗场景增强(P2): warp后Y均值<55(滞回70)才启用 gamma LUT 提亮(0.70ms, CLAHE 6.8ms超预算弃用);
# gamma 0.42~0.62 随暗度自适应, 白天零改动零开销。0=A/B 基线。
export ROAD_CLAHE="${ROAD_CLAHE:-1}"
# ROAD_LANE_RAW=1: UI 车道白线直出模型原始几何, 跳过渲染侧四道整形(右线远端重构/远端外推+EMA/拓扑锚定/对称重构),
# 白线实时跟随真实车道线; 代价: 右弯远端内缩、带宽窄~5% 等模型固有偏差重新可见。0=整形默认。
export ROAD_LANE_RAW="${ROAD_LANE_RAW:-0}"
# 用法: ./start-video.sh /tmp/cam.mp4 [焦距]
#
# 三个关键开关(真机都不要设):
#   ROAD_CAM_F=<f>    视频相机焦距(1920 宽基准)。默认 448 ≈ 130° 水平 FOV。
#                     这个值决定两件事:
#                       1) 模型 warp 取多大视野 —— f 太大(2637=40°)只看到画面
#                          中心一小块, 弯道被裁掉, 模型输出的 plan 就是直线,
#                          看起来"轨迹不随车道弯"
#                       2) UI 投影尺度 —— f 太大时轨迹带(米制 1.81m)在画面上
#                          被放大, 显得"轨迹比车道宽"
#                     换视频且 FOV 明显不同就调这个参数:
#                       广角记录仪 130° → 448
#                       标准记录仪 119° → 558
#                       不确定就先跑, 看 /tmp/ui_proj_probe.txt
#   VIS_PITCH_ONLY=1  视频模式 pitch 只取视觉自校准(intrinsic_calibd), 不用
#                     calibrationd 的姿态。原因: 视频模式无真 IMU, calibrationd
#                     会把 pitch 漂到 -3.34°, 而画面是平装的 -> 地面线被压低 26px
#                     ("有点飞天")。开了它 UI 的地平线回到 540(光学中心)。
Y_SHIFT="${Y_SHIFT:-170}"     # 轨迹垂直偏移(px); 换视频需重扫
VIS_PITCH="${VIS_PITCH:--7.24}"  # 视频模式 pitch(度), 由实测消失点反解
#   PATH_Y_SHIFT_PX   轨迹垂直像素偏移(实测对齐地平线)。原版 video_transform 把
#                     "沿光轴无穷远点"钉在内容中心, 调 pitch/f 都动不了收口位置;
#                     该偏移量直接平移轨迹层。本视频实测值 170(地平线336/轨迹顶338)。
#   PATH_FLATTEN_Z=1  把模型输出 z 压到已知路面高度(远端发散 1.32°)
#   自校准: intrinsic_calibd 会在本视频上重新收敛 pitch_offset
#           (视频相机平装时它会回退到 0; 不必手动设 CALIB_ZERO)
set -e
VIDEO="${1:?用法: $0 <视频路径> [焦距]}"
FOCAL="${2:-448}"
TREE=/data/openpilot_egpucp
echo "停 supervisor(自动重启守护, 否则主树 manager 被秒拉, 台架 flock 起不来)..."
sudo -n systemctl stop carrot-supervisor.service 2>/dev/null || true   # 必须sudo, 否则静默失败
sleep 3
echo "停止当前栈..."
pids=$(pgrep -f "^python3 ./manager.py" || true)
[ -n "$pids" ] && kill $pids || true
sleep 10
rem=$(ps -eo pid,cmd | grep -E "openpilot|launch_chffrplus" \
  | grep -vE "grep|carrot_server|carrot_web_watchdog|sim\.py|start-video\.sh|stop-stack\.sh" | awk '{print $1}' || true)
[ -n "$rem" ] && kill -9 $rem 2>/dev/null || true
# C++ 孤儿补刀: ./camerad 等 cmdline 不含 openpilot, grep 漏杀且成孤儿后仍发布真相机流
for n in camerad ui loggerd encoderd modeld dmonitoringmodeld; do
  pkill -9 -x "$n" 2>/dev/null || true
done
sleep 2
# 换相机素材/焦距参数自动清标定: 视频路径或 ROAD_CAM_F/ROAD_WARP_F 变了说明机位/FOV 可能变,
# 旧 CalibrationParams 不再适用; calibrationd 与视觉自校准会从零自动重新收敛。同素材同参数重放不清, 保留已收敛值。
CAM_MARK=/data/params/last_video_cam
FP="$VIDEO|F=${ROAD_WARP_F}|CF=${FOCAL}"
if [ "$(cat "$CAM_MARK" 2>/dev/null)" != "$FP" ]; then
  rm -f /data/params/d/CalibrationParams
  echo "素材/参数变更($(basename "$VIDEO") $(basename "$FP"|cut -d'|' -f2)), 已清除旧标定, 将自动重新收敛"
fi
mkdir -p /data/params
printf '%s' "$FP" > "$CAM_MARK"
echo "启动视频输入模式: $VIDEO  (ROAD_CAM_F=$FOCAL)"
cd "$TREE"
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority \
  USE_WEBCAM=1 ROAD_CAM="$VIDEO" ROAD_CAM_F="$FOCAL" PATH_FLATTEN_Z=1 \
  VIS_PITCH_DEG="$VIS_PITCH" PATH_Y_SHIFT_PX="$Y_SHIFT" \
  setsid nohup ./launch_openpilot.sh > /tmp/op_video.log 2>&1 < /dev/null &
disown
sleep 8
echo "已启动，约 40 秒后 UI 出现"
echo "日志: /tmp/op_video.log"
echo "验证: tail /tmp/trend_probe.txt    (hz 应为 540 = 光学中心)"
echo "      车道宽约 3.0m / 轨迹带约 1.8m 才合理; 差异过大就调焦距参数"
