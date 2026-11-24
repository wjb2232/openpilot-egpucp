import os

import av
import cv2 as cv
import numpy as np

# imx390 真机标定分辨率: 预编译 modeld 工件只含 (1928,1208)/(1344,760) 两种键,
# 视频输入必须打包成 1928x1208 的 VENUS 布局, modeld 才能命中 jits[(1928,1208)]。
TARGET_W, TARGET_H = 1928, 1208
# VENUS(NV12) 对齐布局, 与 get_nv12_info(1928,1208) 完全一致 -> (2048, 1216, 608, 4804608)
VENUS_STRIDE = 2048                   # align(1928, 128)
Y_HEIGHT = 1216                       # align(1208, 32)
UV_HEIGHT = 608                       # align(604, 16)
FRAME_SIZE = 4804608                  # get_nv12_info 总字节数
Y_PLANE = VENUS_STRIDE * Y_HEIGHT     # 2490368: Y 平面大小, 也是 UV 平面起点 (uv_offset)
UV_VALID_ROWS = TARGET_H // 2         # 604 有效 UV 行


class Camera:
  def __init__(self, cam_type_state, stream_type, camera_id):
    self.cam_type_state = cam_type_state
    self.stream_type = stream_type
    self.cur_frame_id = 0

    # 媒体文件路径 -> 视频输入模式(不翻转, 缩放到标定尺寸)
    self.is_file = isinstance(camera_id, str) and os.path.isfile(camera_id)
    if not self.is_file:
      try:
        camera_id = int(camera_id)
      except ValueError:  # allow strings, ex: /dev/video0
        pass

    print(f"Opening {cam_type_state} at {camera_id} (file={self.is_file})")

    self.cap = cv.VideoCapture(camera_id)

    # 视频→训练视角重映射: openpilot road 训练相机为 2648@1928 (约40°窄视场),
    # 手机/记录仪视频是 ~70-80° 直线视角, 直接喂模型几何失真(车道置信度低、路面 z 倾斜、标定漂移)。
    # ROAD_WARP_F = 视频源等效焦距(1928宽基准): 将其中心区域放大到 2648 视角再喂模型。
    # 0/未设 = 关闭。以模型车道置信度为目标扫参选优, 即素材自标定。
    self._warp_map = None
    try:
      wf = float(os.getenv("ROAD_WARP_F", "0") or 0)
    except ValueError:
      wf = 0.0
    if self.is_file and wf > 0:
      ft = 2648.0
      scale = wf / ft
      sw = int(self.cap.get(cv.CAP_PROP_FRAME_WIDTH)) or 1920
      sh = int(self.cap.get(cv.CAP_PROP_FRAME_HEIGHT)) or 1080
      mx = ((np.arange(TARGET_W, dtype=np.float32) - TARGET_W / 2) * scale * (sw / TARGET_W) + sw / 2)
      my = ((np.arange(TARGET_H, dtype=np.float32) - TARGET_H / 2) * scale * (sh / TARGET_H) + sh / 2)
      self._warp_map = (np.ascontiguousarray(np.broadcast_to(mx.reshape(1, TARGET_W), (TARGET_H, TARGET_W))),
                        np.ascontiguousarray(np.broadcast_to(my.reshape(TARGET_H, 1), (TARGET_H, TARGET_W))))
      self._warp_uv_map = (np.ascontiguousarray(self._warp_map[0][0::2, 0::2] * 0.5),
                           np.ascontiguousarray(self._warp_map[1][0::2, 0::2] * 0.5))
      fov = 2 * np.degrees(np.arctan(TARGET_W / 2 / wf))
      print(f"ROAD_WARP_F={wf}: 源中心 {fov:.1f}° 视场放大到 40° 训练视角")

    if self.is_file:
      self.W, self.H = TARGET_W, TARGET_H
      self.stride, self.uv_offset, self.frame_size = VENUS_STRIDE, Y_PLANE, FRAME_SIZE
      self.src_fps = self.cap.get(cv.CAP_PROP_FPS) or 30.0
      print(f"video {int(self.cap.get(cv.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(self.cap.get(cv.CAP_PROP_FRAME_HEIGHT))} @{self.src_fps:.0f}fps"
            f" -> NV12 {TARGET_W}x{TARGET_H} VENUS (stride {VENUS_STRIDE}, "
            f"{Y_HEIGHT}+{UV_HEIGHT} rows, {FRAME_SIZE}B)")
    else:
      self.cap.set(cv.CAP_PROP_FRAME_WIDTH, 1280.0)
      self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, 720.0)
      self.cap.set(cv.CAP_PROP_FPS, 25.0)
      self.W = int(self.cap.get(cv.CAP_PROP_FRAME_WIDTH))
      self.H = int(self.cap.get(cv.CAP_PROP_FRAME_HEIGHT))
      self.src_fps = 25.0
      self.stride, self.uv_offset, self.frame_size = self.W, self.W * self.H, self.W * self.H * 3 // 2

  @classmethod
  def bgr2nv12(self, bgr):
    frame = av.VideoFrame.from_ndarray(bgr, format='bgr24')
    return frame.reformat(format='nv12').to_ndarray()

  def _warp_nv12(self, yuv):
    """NV12 平面重映射: Y 平面 LINEAR, UV 平面 NEAREST(色度无需插值精度), 数据量较 BGR 省 3 倍。"""
    h3, w = yuv.shape
    y = yuv[:h3 * 2 // 3, :]
    uv = yuv[h3 * 2 // 3:, :].reshape(h3 // 3, w // 2, 2)
    y2 = cv.remap(y, self._warp_map[0], self._warp_map[1], interpolation=cv.INTER_LINEAR, borderMode=cv.BORDER_REPLICATE)
    uv2 = cv.remap(uv, self._warp_uv_map[0], self._warp_uv_map[1], interpolation=cv.INTER_NEAREST, borderMode=cv.BORDER_REPLICATE)
    return np.vstack([y2, uv2.reshape(uv2.shape[0], -1)])

  def _pack_venus(self, raw):
    """把紧密 NV12(1928x1208) 重排成 VENUS 对齐布局(stride 2048, Y 1216 行 + UV 608 行)。"""
    src = np.asarray(raw, dtype=np.uint8).reshape(-1)
    out = np.zeros(FRAME_SIZE, dtype=np.uint8)
    dst_y = out[:Y_PLANE].reshape(Y_HEIGHT, VENUS_STRIDE)
    dst_y[:TARGET_H, :TARGET_W] = src[:TARGET_W * TARGET_H].reshape(TARGET_H, TARGET_W)
    dst_uv = out[Y_PLANE:Y_PLANE + VENUS_STRIDE * UV_HEIGHT].reshape(UV_HEIGHT, VENUS_STRIDE)
    dst_uv[:UV_VALID_ROWS, :TARGET_W] = src[TARGET_W * TARGET_H:].reshape(UV_VALID_ROWS, TARGET_W)
    return out

  def read_frames(self):
    while True:
      ret, frame = self.cap.read()
      if not ret:
        if self.is_file:
          # LOOP_PLAYBACK: 视频播完回到开头继续, 便于长时间观察叠加效果
          self.cap.set(cv.CAP_PROP_POS_FRAMES, 0)
          ret, frame = self.cap.read()
          if not ret:
            break
        else:
          break
      if self.is_file:
        # 视频不翻转(行车记录仪本就正向), 缩放到真机标定尺寸
        if self._warp_map is not None:
          frame = self._warp_nv12(Camera.bgr2nv12(frame))
        elif frame.shape[1] != TARGET_W or frame.shape[0] != TARGET_H:
          frame = Camera.bgr2nv12(cv.resize(frame, (TARGET_W, TARGET_H), interpolation=cv.INTER_LINEAR))
        else:
          frame = Camera.bgr2nv12(frame)
        yield self._pack_venus(frame).tobytes()
      else:
        # 倒装 webcam 需要 180 度翻转
        frame = cv.flip(frame, -1)
        yield Camera.bgr2nv12(frame).data.tobytes()
    self.cap.release()
