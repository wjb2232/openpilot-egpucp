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
    # ROAD_WARP_PY = 采样窗垂直偏移(px, 源图Y坐标): 正值采样窗下移→画面内容上移→水平线上移,
    # 用于对齐训练分布的水平线位置(记录仪支架与训练相机安装差异)。
    try:
      wp = float(os.getenv("ROAD_WARP_PY", "0") or 0)
    except ValueError:
      wp = 0.0
    if self.is_file and wf > 0:
      ft = 2648.0
      scale = wf / ft
      sw = int(self.cap.get(cv.CAP_PROP_FRAME_WIDTH)) or 1920
      sh = int(self.cap.get(cv.CAP_PROP_FRAME_HEIGHT)) or 1080
      mx = ((np.arange(TARGET_W, dtype=np.float32) - TARGET_W / 2) * scale * (sw / TARGET_W) + sw / 2)
      my = ((np.arange(TARGET_H, dtype=np.float32) - TARGET_H / 2) * scale * (sh / TARGET_H) + sh / 2 + wp)
      self._warp_map = (np.ascontiguousarray(np.broadcast_to(mx.reshape(1, TARGET_W), (TARGET_H, TARGET_W))),
                        np.ascontiguousarray(np.broadcast_to(my.reshape(TARGET_H, 1), (TARGET_H, TARGET_W))))
      self._warp_uv_map = (np.ascontiguousarray(self._warp_map[0][0::2, 0::2] * 0.5),
                           np.ascontiguousarray(self._warp_map[1][0::2, 0::2] * 0.5))
      fov = 2 * np.degrees(np.arctan(TARGET_W / 2 / wf))
      print(f"ROAD_WARP_F={wf} PY={wp:+.0f}px: 源中心 {fov:.1f}° 视场放大到 40° 训练视角")

    # ROAD_VP_LOCK=1: 消失点锚定动态 warp —— 低频估计道路消失点(VP)横向位置,
    # 采样窗水平中心跟随 VP, 弯道远端路面保持居中, 提升模型远端车道信息完整性。
    # VP 估计+EMA 平滑+限幅+死区全部在输入侧闭环, 无跨进程依赖。
    self._vp = None
    if self._warp_map is not None and os.getenv("ROAD_VP_LOCK", "0") == "1":
      self._vp = {
        "mx1d": self._warp_map[0][0].copy(),     # (TARGET_W,) 基础水平采样行
        "map_y": self._warp_map[1].copy(),       # (H,W) 垂直 map 常驻复用(重建免拷)
        "uv_my": self._warp_uv_map[1].copy(),    # UV 垂直 map 常驻复用
        "rng": 0.12 * sw,                        # 满偏移 = ±12% 源宽(窗界 ±29% 内安全)
        "dx": 0.0, "ema": 0.0, "miss": 0, "fc": 0,
        "clahe": cv.createCLAHE(2.0, (2, 2)),
      }
      print("ROAD_VP_LOCK=1: 消失点锚定动态采样窗开启")

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

  def _vp_estimate(self, bgr):
    """480 宽缩小灰度上 Hough 拟合左右车道线求消失点, 返回归一化横向偏移 nx∈[-1,1], None=本帧无效。"""
    vw = 480
    vh = int(bgr.shape[0] * vw / bgr.shape[1])
    g = self._vp["clahe"].apply(cv.cvtColor(cv.resize(bgr, (vw, vh), interpolation=cv.INTER_AREA), cv.COLOR_BGR2GRAY))
    segs = cv.HoughLinesP(cv.Canny(g, 40, 120), 1, np.pi / 180, 50,
                          minLineLength=int(vw * 0.18), maxLineGap=10)
    if segs is None:
      return None
    yb0, yb1 = int(vh * 0.45), int(vh * 0.92)   # 路面车道线纵带(地平线以下)
    lns = []                                     # (b, a, xm): x = a + b*y
    for x1, y1, x2, y2 in segs[:, 0]:
      if not (yb0 <= min(y1, y2) and max(y1, y2) <= yb1) or abs(y2 - y1) < 8:
        continue                                 # 出带/近水平(路面横纹)段剔除
      b = (x2 - x1) / (y2 - y1)
      if 0.15 < abs(b) < 3.0:                    # 透视车道线斜率窗
        lns.append((b, x1 - b * y1, 0.5 * (x1 + x2)))
    left = [(b, a) for b, a, xm in lns if xm < vw / 2]
    right = [(b, a) for b, a, xm in lns if xm >= vw / 2]
    if not left or not right:                    # 单侧检出: 无交点证据
      return None
    bl, al = np.median([b for b, _ in left]), np.median([a for _, a in left])
    br, ar = np.median([b for b, _ in right]), np.median([a for _, a in right])
    yv = (ar - al) / (bl - br) if abs(bl - br) > 1e-3 else 0.45 * vh
    yv = float(np.clip(yv, -0.6 * vh, 0.55 * vh))   # VP 越界(近平行)退化为该行左右线中点
    xv = float(np.clip(0.5 * (al + bl * yv + ar + br * yv), 0.15 * vw, 0.85 * vw))
    return (xv / vw - 0.5) * 2.0

  def _vp_rebuild(self):
    """水平平移 dx 重建采样 LUT: 垂直 map 常驻复用, 只重算 mx(Y 全图) 与 mx/2(UV)。"""
    mx1d = self._vp["mx1d"] + self._vp["dx"]
    self._warp_map = (np.ascontiguousarray(np.broadcast_to(mx1d.reshape(1, TARGET_W), (TARGET_H, TARGET_W))),
                      self._vp["map_y"])
    self._warp_uv_map = (np.ascontiguousarray(self._warp_map[0][0::2, 0::2] * 0.5), self._vp["uv_my"])

  def _warp_nv12(self, yuv):
    """NV12 平面重映射: Y 平面 LINEAR(CUBIC 实测超该盒 CPU 预算回退: 8~17fps 且被 GPU 争抢掩盖收益), UV 平面 NEAREST(色度无需插值精度), 数据量较 BGR 省 3 倍。"""
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
          if self._vp is not None:
            self._vp["fc"] += 1
            if self._vp["fc"] % 8 == 0:      # 低频评估: 弯道横移是秒级缓变
              nx = self._vp_estimate(frame)
              if nx is None:
                self._vp["miss"] += 1
                if self._vp["miss"] > 25:    # ~10s 无检测: 缓慢回中(直道无证据)
                  self._vp["ema"] *= 0.95
                  self._vp["miss"] = 20
              else:
                self._vp["miss"] = 0
                self._vp["ema"] += 0.25 * (float(np.clip(nx, -1.0, 1.0)) * self._vp["rng"] - self._vp["ema"])
              step = float(np.clip(self._vp["ema"] - self._vp["dx"], -30.0, 30.0))  # 限幅: ~3s 收敛一次弯道
              if abs(self._vp["ema"] - self._vp["dx"]) > 1.5:   # 死区: 直道零重建
                self._vp["dx"] += step
                self._vp_rebuild()
              if self._vp["fc"] % 800 == 0:
                print(f"[VP] fc={self._vp['fc']} nx={nx} ema={self._vp['ema']:.0f}px dx={self._vp['dx']:.0f}px")
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
