#!/usr/bin/env bash
# Carrot openpilot 栈守护: manager 崩溃后自动重拉。
# 可能被多个来源拉起 (systemd carrot-supervisor.service / 开机遗留钩子 /
# 手动执行), flock 保证全局只有一份真正干活, 其余副本静默退出。
#
# 注意不能写裸 "while true; do ./launch_chffrplus.sh; sleep 2; done":
# launch_chffrplus.sh 起 manager 后卡在尾部 "while true; do sleep 1; done"
# 永不退出, 裸循环会永远阻塞在第一轮 (旧版守护的自动重拉从未生效过)。
# 所以后台拉 launch, 监控 manager.py 存活: 消失超过 8s 判死, 杀掉本轮
# launch 重拉。manager 死后其 spawn 子进程会自杀, 残留由 launch 内部
# cleanup_previous_instance 兜底。
exec 9>/tmp/carrot_supervisor.lock   # /run 是 root 目录, 服务以 nvidia 运行写不了
flock -n 9 || exit 0

while true; do
  cd /data/openpilot || exit 1
  ./launch_chffrplus.sh &
  LAUNCH_PID=$!
  # 阶段1: 等 manager 首次出现 (最多 300s, 覆盖慢启动/增量重编译)
  for i in $(seq 1 150); do
    pgrep -f '[m]anager\.py' >/dev/null 2>&1 && break
    kill -0 $LAUNCH_PID 2>/dev/null || break  # launch 意外退出, 立即重拉
    sleep 2
  done
  # 阶段2: 存活监控, manager 消失超过 8s 判死
  MISS_AT=0
  while kill -0 $LAUNCH_PID 2>/dev/null; do
    if pgrep -f '[m]anager\.py' >/dev/null 2>&1; then
      MISS_AT=0
    else
      [ "$MISS_AT" -eq 0 ] && MISS_AT=$(date +%s)
      if [ $(( $(date +%s) - MISS_AT )) -ge 8 ]; then
        break
      fi
    fi
    sleep 2
  done
  # manager 已死: 本轮 launch 卡在尾部死循环, 杀掉后重拉
  kill -9 $LAUNCH_PID 2>/dev/null
  sleep 2
done
