#!/usr/bin/env bash
# 恢复上车模式（真实相机）
set -e
TREE=/data/openpilot_egpucp
echo "停止当前栈..."
pids=$(pgrep -f "^python3 ./manager.py" || true)
[ -n "$pids" ] && kill $pids || true
sleep 10
rem=$(ps -eo pid,cmd | grep -E "openpilot|launch_chffrplus" \
  | grep -vE "grep|carrot_server|carrot_web_watchdog|sim.py" | awk '{print $1}' || true)
[ -n "$rem" ] && kill -9 $rem 2>/dev/null || true
sleep 5
# 清掉视频测试留下的状态
cd "$TREE"
.venv/bin/python3 -c "
from openpilot.common.params import Params
p = Params()
p.put_bool('IsDriverViewEnabled', False)
print('IsDriverViewEnabled -> False')
" || true
rm -f /tmp/carrot_inject_vru.txt /tmp/carrot_inject_sig.txt
echo "启动真实相机模式..."
DISPLAY=:0 setsid nohup ./launch_openpilot.sh > /tmp/op.log 2>&1 < /dev/null &
disown
sleep 8
echo "已启动上车模式，日志: /tmp/op.log"
echo "确认 camerad 是 C++ 版: ps -eo args | grep -E '^./camerad'"
