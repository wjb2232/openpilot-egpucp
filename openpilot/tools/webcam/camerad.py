#!/usr/bin/env python3
import threading
import os
import platform
from collections import namedtuple

from msgq.visionipc import VisionIpcServer, VisionStreamType
from openpilot.cereal import messaging

from openpilot.tools.webcam.camera import Camera
from openpilot.common.realtime import Ratekeeper

ROAD_CAM = os.getenv("ROAD_CAM", "0")
WIDE_CAM = os.getenv("WIDE_CAM")
DRIVER_CAM = os.getenv("DRIVER_CAM")

CameraType = namedtuple("CameraType", ["msg_name", "stream_type", "cam_id"])

CAMERAS = [
  CameraType("roadCameraState", VisionStreamType.VISION_STREAM_ROAD, ROAD_CAM)
]
if WIDE_CAM:
  CAMERAS.append(CameraType("wideRoadCameraState", VisionStreamType.VISION_STREAM_WIDE_ROAD, WIDE_CAM))
if DRIVER_CAM:
  CAMERAS.append(CameraType("driverCameraState", VisionStreamType.VISION_STREAM_DRIVER, DRIVER_CAM))

class Camerad:
  def __init__(self):
    self.pm = messaging.PubMaster([c.msg_name for c in CAMERAS])
    self.vipc_server = VisionIpcServer("camerad")

    self.cameras = []
    for c in CAMERAS:
      # VIDEO_FILE_OK: cam_id 可以是 /dev/videoN、数字索引, 或媒体文件路径
      cam_id = str(c.cam_id)
      if os.path.isfile(cam_id):
        cam_device = cam_id          # 视频文件直接喂 cv2.VideoCapture
      elif os.path.isdir(cam_id):
        cam_device = cam_id
      elif platform.system() != "Darwin":
        cam_device = f"/dev/video{cam_id}"
      else:
        cam_device = cam_id
      cam = Camera(c.msg_name, c.stream_type, cam_device)
      self.cameras.append(cam)
      # 带 stride/uv_offset 建缓冲: 文件模式按 VENUS(2048/2490368) 布局,
      # 与 get_nv12_info(1928,1208) 一致, modeld 免 CPU repack 直接快路径。
      self.vipc_server.create_buffers_with_sizes(
        c.stream_type, 20, cam.W, cam.H, cam.frame_size, cam.stride, cam.uv_offset)

    self.vipc_server.start_listener()

  def _send_yuv(self, yuv, frame_id, pub_type, yuv_type):
    eof = int(frame_id * 0.05 * 1e9)
    self.vipc_server.send(yuv_type, yuv, frame_id, eof, eof)
    dat = messaging.new_message(pub_type, valid=True)
    msg = {
      "frameId": frame_id,
      "transform": [1.0, 0.0, 0.0,
                    0.0, 1.0, 0.0,
                    0.0, 0.0, 1.0]
    }
    setattr(dat, pub_type, msg)
    self.pm.send(pub_type, dat)

  def camera_runner(self, cam):
    # 20Hz: 本视频 20fps, 按真实帧率节拍回放
    rk = Ratekeeper(20, None)
    for yuv in cam.read_frames():
      self._send_yuv(yuv, cam.cur_frame_id, cam.cam_type_state, cam.stream_type)
      cam.cur_frame_id += 1
      rk.keep_time()

  def run(self):
    threads = []
    for cam in self.cameras:
      cam_thread = threading.Thread(target=self.camera_runner, args=(cam,))
      cam_thread.start()
      threads.append(cam_thread)

    for t in threads:
      t.join()


def main():
  camerad = Camerad()
  camerad.run()


if __name__ == "__main__":
  main()
