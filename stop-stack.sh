#!/usr/bin/env bash
# 停止 132 上的 openpilot 栈（彻底清干净）
# 2026-11-23 修订: ① 先停 carrot-supervisor(否则它会秒拉主树 manager, 台架 flock 起不来)
#                  ② C++ 进程 cmdline 不含 openpilot(./camerad 等)且 manager 死后成孤儿 —— 按名补刀
sudo -n systemctl stop carrot-supervisor.service 2>/dev/null || true   # 必须sudo, 否则静默失败
sleep 3
pids=$(pgrep -f "^python3 ./manager.py" || true)
[ -n "$pids" ] && kill $pids || true
sleep 10
rem=$(ps -eo pid,cmd | grep -E "openpilot|launch_chffrplus" \
  | grep -vE "grep|carrot_server|carrot_web_watchdog|sim\.py|start-video\.sh|stop-stack\.sh" | awk '{print $1}' || true)
[ -n "$rem" ] && kill -9 $rem 2>/dev/null || true
# C++ 孤儿补刀(-x 精确按进程名, python 进程名是 python3 不会误杀)
for n in camerad ui loggerd encoderd modeld dmonitoringmodeld; do
  pkill -9 -x "$n" 2>/dev/null || true
done
sleep 4
echo "已停止"
left=$(ps -eo pid,args | grep -E "openpilot|manager.py|camerad" \
  | grep -vE "grep|carrot_server|carrot_web_watchdog|sim.py" | head -5)
if [ -n "$left" ]; then echo "$left"; else echo "  无残留进程"; fi
