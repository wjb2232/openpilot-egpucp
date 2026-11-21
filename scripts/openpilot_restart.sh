#!/usr/bin/env bash
# 一键重启 openpilot: 停 systemd 守护 → 清残留 → systemd 重新拉起 → 跟日志。
# 用法: /home/nvidia/openpilot_restart.sh   (Ctrl-C 退出日志跟踪, 栈继续运行)
#
# 栈由 /etc/systemd/system/carrot-supervisor.service 常驻守护:
# - 开机自动拉起; manager 崩溃 2s 内自动重拉 (Restart=always)
# - /data/carrot_supervisor.sh 用 flock 幂等, 多来源拉起只有一份干活
# - 日志随时可看: journalctl -u carrot-supervisor -f
#
# 清理名单与 launch_chffrplus.sh 里的 cleanup_previous_instance 保持一致:
# 遗留的 launcher 处在 show_startup_failure 的 while 循环里会每 30s 重弹
# "Startup recovery" 窗口; 遗留的服务进程占着 msgq 服务名和 TCP 端口会让新实例
# 报 MultiplePublishersError / OSError 98 并反复崩溃。
set -u

UNIT=carrot-supervisor.service
PATS='openpilot\.(selfdrive|system)\.|[m]anager\.py|[/ ](camerad|encoderd|stream_encoderd|carrot_vision_encoderd|loggerd|pandad|bridge)( |$)|launch_chffrplus|launch_openpilot|startup_recovery|carrot_web_watchdog'

echo "== 停止 systemd 守护 =="
sudo -n systemctl stop "$UNIT" 2>/dev/null || true
# 兜底: 非 systemd 来源拉起的 supervisor (含开机遗留钩子), 杀掉干活副本
for p in $(pgrep -f '[c]arrot_supervisor\.sh' 2>/dev/null); do
  [ "$p" = "$$" ] && continue
  sudo -n kill -9 "$p" 2>/dev/null || kill -9 "$p" 2>/dev/null
done

echo "== 停止所有遗留 openpilot 进程 =="
# launcher 先杀: 否则杀掉 manager 会让它走进恢复循环, 每 30s 弹一次恢复窗口
for p in $(pgrep -f 'launch_(chffrplus|openpilot)' 2>/dev/null); do
  [ "$p" = "$$" ] && continue
  sudo -n kill -9 "$p" 2>/dev/null || kill -9 "$p" 2>/dev/null
done
sleep 1
for p in $(pgrep -f "$PATS" 2>/dev/null); do
  [ "$p" = "$$" ] && continue
  sudo -n kill -9 "$p" 2>/dev/null || kill -9 "$p" 2>/dev/null
done
# 名单之外的残留 (改名/孙进程) 用端口兜底
fuser -k 6999/tcp 7000/tcp 7712/tcp 7713/tcp 7714/tcp 7714/udp 7705/udp 8088/tcp 8888/tcp >/dev/null 2>&1 || true

for i in $(seq 1 15); do
  pgrep -f "[m]anager\.py" >/dev/null 2>&1 || break
  sleep 1
done

LEFT=$(pgrep -af "$PATS" 2>/dev/null | grep -v "$$" | grep -v pgrep || true)
if [ -n "$LEFT" ]; then
  echo "!! 仍有进程未停止:"; echo "$LEFT"
fi

echo "== 启动 (systemd 守护) =="
sudo -n systemctl start "$UNIT"
sleep 1
echo "--- 日志跟踪中, Ctrl-C 退出 (栈继续由 systemd 守护运行) ---"
journalctl -n 100 -f -u "$UNIT"
