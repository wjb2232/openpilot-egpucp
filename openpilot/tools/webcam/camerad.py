#!/usr/bin/env python3
"""webcamerad v4 —— 角色/候选源模型,真正三路互备。

物理源(摄像头)与发布角色(road/wide)解耦:
- 每个物理源一个线程:独立打开/读帧/断流重连;只要能读帧就标记 alive,
  保存最新帧供角色取用。
- 每个角色(road/wide)一个线程:按优先级从候选源中挑"当前活着的最优源",
  把它的帧发布到对应 stream。源挂了自动切下一个候选;源恢复自动切回。

因此:
- 三路全活:road 吃 30°(看得远),wide 吃 196°(看得广),90° USB 作两端备胎。
- 任一源挂:角色自动用备胎顶上,模型始终能看到 road+wide 两个流。
- 只剩一个源:两个角色共享它,模型仍双流输入。

环境变量语义(与 launch_env.sh / resolve_cams.sh 配合):
  ROAD_CAM   主路默认源(30°),road 候选优先级: ROAD_CAM > DRIVER_CAM > WIDE_CAM
  WIDE_CAM   增强路默认源(196°),wide 候选优先级: WIDE_CAM > DRIVER_CAM > ROAD_CAM
  DRIVER_CAM 中距离备胎(USB 90°),参与两端顶替。
"""
import threading
import os
import platform
import time
import json

from msgq.visionipc import VisionIpcServer, VisionStreamType
from openpilot.cereal import messaging

from openpilot.tools.webcam.camera import Camera, CAM_WIDTH, CAM_HEIGHT
from openpilot.common.realtime import Ratekeeper

ROAD_CAM = os.getenv("ROAD_CAM", "0")
WIDE_CAM = os.getenv("WIDE_CAM")
DRIVER_CAM = os.getenv("DRIVER_CAM")

RECONNECT_DELAY = 2.0
OPEN_TIMEOUT = 6.0
FRAME_HZ = 20
STICKY_SECONDS = 5.0  # 角色切源防抖:高优先级源恢复后至少等这么久才切回
ROLE_STATUS_FILE = "/tmp/role_sources.json"  # 当前源状态(供 intrinsic_calibd 防标定污染)
ROLE_STATUS_LOCK = threading.Lock()  # 状态文件写锁(多角色线程)


class Source:
  """一个物理摄像头。独立线程负责打开/读帧/重连,并保存最新帧。"""

  def __init__(self, name: str, cam_device: str):
    self.name = name
    self.cam_device = cam_device
    self.lock = threading.Lock()
    self.latest = None          # (frame_id, nv12, eof_ns)
    self.alive = False
    self._prev_alive = False
    self.cam = None

  # ---- 有超时的打开 ----
  def _open_once(self):
    result = {}

    def worker():
      try:
        result["cam"] = Camera(self.name, None, self.cam_device)
      except Exception as e:  # noqa: BLE001
        result["err"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(OPEN_TIMEOUT)
    if t.is_alive():
      return None
    cam = result.get("cam")
    if cam is None or cam.src_w <= 0 or cam.src_h <= 0:
      return None
    return cam

  def _set_alive(self, alive: bool):
    with self.lock:
      changed = (self.alive != alive)
      self.alive = alive
    if changed:
      print(f"[webcamerad] {self.name}: {'ALIVE' if alive else 'DEAD'} ({self.cam_device})", flush=True)

  # ---- 主循环:打开->读帧->断流重连 ----
  def run(self):
    cam = None
    while True:
      if cam is None:
        cam = self._open_once()
        if cam is None:
          self._set_alive(False)
          time.sleep(RECONNECT_DELAY)
          continue
        print(f"[webcamerad] {self.name}: opened {self.cam_device} (uvc={cam.is_uvc})", flush=True)
        self.cam = cam
      try:
        for yuv in cam.read_frames():
          self._set_alive(True)
          eof = time.monotonic_ns()
          with self.lock:
            self.latest = (cam.cur_frame_id, yuv, eof)
          cam.cur_frame_id += 1
      except Exception as e:  # noqa: BLE001
        print(f"[webcamerad] {self.name}: read error ({e}), reconnecting", flush=True)
      self._set_alive(False)
      print(f"[webcamerad] {self.name}: stream lost, reconnecting in {RECONNECT_DELAY}s", flush=True)
      time.sleep(RECONNECT_DELAY)
      # 不使用 cam.reopen():cv.VideoCapture 无超时,设备拔出/卡住时会无限阻塞
      # 挂死本线程,导致该源永远不恢复。统一回 _open_once(带 OPEN_TIMEOUT)。
      cam = None

  def is_alive(self) -> bool:
    with self.lock:
      return self.alive

  def get_latest(self):
    with self.lock:
      return self.latest


class Role:
  """一个发布角色(road/wide)。按优先级挑活着的源,发布其最新帧。"""

  def __init__(self, cam_type_state, stream_type, candidates, pm, vipc_server):
    self.cam_type_state = cam_type_state
    self.stream_type = stream_type
    self.candidates = [c for c in candidates if c is not None]
    self.pm = pm
    self.vipc_server = vipc_server
    self._last_frame_id = -1
    self._cur = None
    self._switch_time = 0.0
    self.preferred = self.candidates[0] if self.candidates else None

  def pick(self):
    # 每次按候选优先级重扫:高优先级源恢复存活后自动切回(带防抖,避免抖动源来回切)
    now = time.monotonic()
    best = None
    for s in self.candidates:
      if s.is_alive():
        best = s
        break
    if best is None:
      self._cur = None
      return None
    if self._cur is best:
      return best
    if self._cur is not None and self._cur.is_alive() and now - self._switch_time < STICKY_SECONDS:
      return self._cur  # 当前源仍活着,防抖期内不切换
    self._cur = best
    self._switch_time = now
    # 新源 frame_id 从 0 起,与旧源可能撞号导致漏发一帧;重置后强制发布下一帧
    self._last_frame_id = -1
    print(f"[webcamerad] {self.cam_type_state} -> {best.name} ({best.cam_device})", flush=True)
    return best

  def _write_status(self):
    try:
      status = {
        "src": self._cur.name if self._cur is not None else None,
        "preferred": self.preferred.name if self.preferred is not None else None,
        "using_preferred": self._cur is self.preferred,
      }
      # 读-合并-写必须串行:多个角色线程并发会互相覆盖
      with ROLE_STATUS_LOCK:
        try:
          with open(ROLE_STATUS_FILE) as f:
            all_status = json.load(f)
        except Exception:
          all_status = {}
        all_status[self.cam_type_state] = status
        with open(ROLE_STATUS_FILE, "w") as f:
          json.dump(all_status, f)
    except Exception:
      pass

  def run(self):
    rk = Ratekeeper(FRAME_HZ, None)
    last_status = 0.0
    while True:
      # 状态文件降频 1Hz(60 次/秒 JSON 写是无谓 I/O;calibd 读它做防污染判断,1Hz 足够)
      now_s = time.monotonic()
      if now_s - last_status >= 1.0:
        self._write_status()
        last_status = now_s
      src = self.pick()
      if src is None:
        time.sleep(0.5)
        continue
      latest = src.get_latest()
      if latest is not None and latest[0] != self._last_frame_id:
        frame_id, nv12, eof = latest
        self._last_frame_id = frame_id
        sof = eof - 50_000_000  # 估计 20Hz 帧起始
        self.vipc_server.send(self.stream_type, nv12, frame_id, sof, eof)
        dat = messaging.new_message(self.cam_type_state, valid=True, logMonoTime=eof)
        msg = {
          "frameId": frame_id,
          "timestampSof": sof,
          "timestampEof": eof,
          "transform": [1.0, 0.0, 0.0,
                        0.0, 1.0, 0.0,
                        0.0, 0.0, 1.0],
        }
        setattr(dat, self.cam_type_state, msg)
        self.pm.send(self.cam_type_state, dat)
      rk.keep_time()


class Camerad:
  def __init__(self):
    self.pm = messaging.PubMaster(["roadCameraState", "wideRoadCameraState", "driverCameraState"])
    self.vipc_server = VisionIpcServer("camerad")

    # 物理源(去重)
    src_ids = []
    for cid in (ROAD_CAM, WIDE_CAM, DRIVER_CAM):
      cid = str(cid).strip()
      if cid and cid not in src_ids:
        src_ids.append(cid)
    self.sources = []
    for cid in src_ids:
      dev = f"/dev/video{cid}" if platform.system() != "Darwin" else cid
      self.sources.append(Source(f"cam{cid}", dev))

    def find(tag):
      for s in self.sources:
        if s.name == f"cam{tag}":
          return s
      return None

    road_src = find(str(ROAD_CAM).strip())
    wide_src = find(str(WIDE_CAM).strip()) if WIDE_CAM else None
    drv_src = find(str(DRIVER_CAM).strip()) if DRIVER_CAM else None

    # 角色与候选优先级:
    #   road  = 30°(远)优先,挂时依次由 90°、196° 顶替
    #   wide  = 196°(近/广)优先,挂时依次由 90°、30° 顶替
    #   driver= 90°(中)专属,喂 lane 车道线推理(小鸽)
    self.roles = []
    self.roles.append(Role("roadCameraState", VisionStreamType.VISION_STREAM_ROAD,
                           [road_src, drv_src, wide_src], self.pm, self.vipc_server))
    if WIDE_CAM:
      self.roles.append(Role("wideRoadCameraState", VisionStreamType.VISION_STREAM_WIDE_ROAD,
                             [wide_src, drv_src, road_src], self.pm, self.vipc_server))
    if DRIVER_CAM:
      self.roles.append(Role("driverCameraState", VisionStreamType.VISION_STREAM_DRIVER,
                             [drv_src], self.pm, self.vipc_server))

    # 每个角色的 stream buffer(所有源都缩放到 CAM_WIDTH x CAM_HEIGHT)
    for role in self.roles:
      self.vipc_server.create_buffers(role.stream_type, 20, CAM_WIDTH, CAM_HEIGHT)
    self.vipc_server.start_listener()
    print(f"[webcamerad] v5 role/source model: {len(self.sources)} sources, "
          f"{len(self.roles)} roles ({[r.cam_type_state for r in self.roles]})", flush=True)

  def run(self):
    for src in self.sources:
      threading.Thread(target=src.run, daemon=True).start()
    for role in self.roles:
      threading.Thread(target=role.run, daemon=True).start()
    if not self.sources:
      print("[webcamerad] no sources configured, exiting", flush=True)
      return
    while True:
      time.sleep(1)


def main():
  Camerad().run()


if __name__ == "__main__":
  main()