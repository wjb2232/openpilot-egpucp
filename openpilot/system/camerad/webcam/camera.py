import os
import ctypes
import fcntl
import mmap

import cv2 as cv
import numpy as np

# --- v4l2 ioctl numbers (tegra kernel quirks baked in, see v4l2_reader note) ---
VIDIOC_S_FMT = 0xc0d05605        # 208B v4l2_format; textbook 0xC0C85605 -> ENOTTY
VIDIOC_REQBUFS = 0xC0145608
VIDIOC_QUERYBUF = 0xc0585609
VIDIOC_QBUF = 0xc058560f
VIDIOC_DQBUF = 0xc0585611
VIDIOC_STREAMON = 0x40045612
VIDIOC_STREAMOFF = 0x40045613
V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_MEMORY_MMAP = 1
V4L2_PIX_FMT_UYVY = 0x59565955    # 'UYVY' little-endian

CAM_WIDTH = int(os.environ.get("CAM_WIDTH", "1344"))
CAM_HEIGHT = int(os.environ.get("CAM_HEIGHT", "760"))
CAM_BRIGHTNESS = float(os.environ.get("CAM_BRIGHTNESS", "1.0"))


class V4L2PixFormat(ctypes.Structure):
  _fields_ = [
    ("width", ctypes.c_uint32), ("height", ctypes.c_uint32),
    ("pixelformat", ctypes.c_uint32), ("field", ctypes.c_uint32),
    ("bytesperline", ctypes.c_uint32), ("sizeimage", ctypes.c_uint32),
    ("colorspace", ctypes.c_uint32), ("priv", ctypes.c_uint32),
    ("flags", ctypes.c_uint32), ("ycbcr_enc", ctypes.c_uint32),
    ("quantization", ctypes.c_uint32), ("xfer_func", ctypes.c_uint32),
    ("reserved", ctypes.c_uint32 * 4),
  ]


class V4L2FmtUnion(ctypes.Union):
  _fields_ = [("pix", V4L2PixFormat), ("raw", ctypes.c_uint8 * 204)]


class V4L2Format(ctypes.Structure):
  _fields_ = [("type", ctypes.c_uint32), ("fmt", V4L2FmtUnion)]


class V4L2RequestBuffers(ctypes.Structure):
  _fields_ = [
    ("count", ctypes.c_uint32), ("type", ctypes.c_uint32),
    ("memory", ctypes.c_uint32), ("capabilities", ctypes.c_uint32),
    ("flags", ctypes.c_uint8), ("reserved", ctypes.c_uint8 * 3),
  ]


class V4L2Buffer(ctypes.Structure):
  """88 bytes on arm64."""
  _fields_ = [
    ("index", ctypes.c_uint32), ("type", ctypes.c_uint32),
    ("bytesused", ctypes.c_uint32), ("flags", ctypes.c_uint32),
    ("field", ctypes.c_uint32), ("_pad0", ctypes.c_uint32),
    ("timestamp", ctypes.c_int64 * 2), ("timecode", ctypes.c_uint32 * 4),
    ("sequence", ctypes.c_uint32), ("memory", ctypes.c_uint32),
    ("m_offset", ctypes.c_uint64), ("length", ctypes.c_uint32),
    ("_pad1", ctypes.c_uint32), ("reserved", ctypes.c_uint32 * 2),
  ]


class V4L2Reader:
  """Direct v4l2 mmap reader — replaces cv.VideoCapture (~30fps vs ~10fps).

  Te gra quirks:
    * S_FMT ioctl = 0xc0d05605 (208B format struct)
    * DQBUF buffers come back 4x nominal frame size — slice w*h*2 real bytes
    * Physical byte order is V0 Y0 U0 Y1 (UYVY request -> swapped 4:2:2)
  """

  def __init__(self, device, width=1920, height=1080,
               pixelformat=V4L2_PIX_FMT_UYVY, nbufs=4):
    self.fd = os.open(device, os.O_RDWR)
    self.width = width
    self.height = height
    self.nbufs = nbufs
    self.buffers = []
    self.frame_id = 0

    fmt = V4L2Format()
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
    fmt.fmt.pix.width = width
    fmt.fmt.pix.height = height
    fmt.fmt.pix.pixelformat = pixelformat
    fmt.fmt.pix.field = 0
    try:
      fcntl.ioctl(self.fd, VIDIOC_S_FMT, fmt)
    except OSError as e:
      os.close(self.fd)
      raise RuntimeError(f"S_FMT failed: {e}")
    self.bytesperline = fmt.fmt.pix.bytesperline or width * 2
    self.sizeimage = fmt.fmt.pix.sizeimage or width * height * 2

    rb = V4L2RequestBuffers()
    rb.count = nbufs
    rb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
    rb.memory = V4L2_MEMORY_MMAP
    fcntl.ioctl(self.fd, VIDIOC_REQBUFS, rb)

    for i in range(nbufs):
      qb = V4L2Buffer()
      qb.index = i
      qb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
      qb.memory = V4L2_MEMORY_MMAP
      fcntl.ioctl(self.fd, VIDIOC_QUERYBUF, qb)
      buf = mmap.mmap(self.fd, qb.length, mmap.MAP_SHARED, mmap.PROT_READ,
                      offset=qb.m_offset)
      self.buffers.append(buf)
      fcntl.ioctl(self.fd, VIDIOC_QBUF, qb)

    on = ctypes.c_uint32(V4L2_BUF_TYPE_VIDEO_CAPTURE)
    fcntl.ioctl(self.fd, VIDIOC_STREAMON, on)

  def read(self):
    dq = V4L2Buffer()
    dq.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
    dq.memory = V4L2_MEMORY_MMAP
    fcntl.ioctl(self.fd, VIDIOC_DQBUF, dq)
    idx = dq.index
    # tegra driver returns 4x nominal; slice the first frame-sized chunk
    n = min(dq.bytesused, self.width * self.height * 2)
    data = bytes(self.buffers[idx][:n])
    qb = V4L2Buffer()
    qb.index = idx
    qb.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
    qb.memory = V4L2_MEMORY_MMAP
    fcntl.ioctl(self.fd, VIDIOC_QBUF, qb)
    self.frame_id += 1
    return self.frame_id, data, dq.sequence

  def close(self):
    try:
      off = ctypes.c_uint32(V4L2_BUF_TYPE_VIDEO_CAPTURE)
      fcntl.ioctl(self.fd, VIDIOC_STREAMOFF, off)
    except OSError:
      pass
    for b in self.buffers:
      b.close()
    os.close(self.fd)


class Camera:
  """GMSL camera via direct v4l2 mmap, no rotation."""

  def __init__(self, cam_type_state, stream_type, camera_id, capture_clock=None):
    try:
      camera_id = int(camera_id)
    except ValueError:  # allow strings, ex: /dev/video0
      pass
    self.cam_type_state = cam_type_state
    self.stream_type = stream_type
    self.cur_frame_id = 0

    if isinstance(camera_id, int):
      self.device = f"/dev/video{camera_id}"
    else:
      self.device = camera_id

    print(f"Opening {cam_type_state} at {self.device}")

    # OpenCV/CAP_V4L2 path (2026-10-17: V4L2Reader direct mmap triggers VI
    # corr_err discards; OpenCV reads cleanly at 1920x1080 UYVY).
    self.cap = cv.VideoCapture(self.device, cv.CAP_V4L2)
    self.cap.set(cv.CAP_PROP_FRAME_WIDTH, 1920)
    self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, 1080)
    self.cap.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc(*'UYVY'))
    self.cap.set(cv.CAP_PROP_CONVERT_RGB, 0)
    self.src_w, self.src_h = 1920, 1080

    self.W = CAM_WIDTH
    self.H = CAM_HEIGHT

    if CAM_BRIGHTNESS != 1.0:
      self._bright_lut = np.clip(np.arange(256, dtype=np.float32) * CAM_BRIGHTNESS, 0, 255).astype(np.uint8)
    else:
      self._bright_lut = None

    # VENUS NV12 layout expected by modeld: stride/Y/UV heights are aligned
    # (tight 3/2 frames make modeld raise "buffer is smaller than requested size").
    self.stride = ((self.W + 127) // 128) * 128
    self.y_height = ((self.H + 31) // 32) * 32
    self.uv_height = ((self.H // 2 + 15) // 16) * 16
    self.uv_offset = self.stride * self.y_height
    self.frame_size = self.stride * (self.y_height + self.uv_height)

    # Preallocated resize/assembly buffers.
    self._y_rs = np.empty((self.H, self.W), dtype=np.uint8)
    self._u_rs = np.empty((self.H // 2, self.W // 2), dtype=np.uint8)
    self._v_rs = np.empty((self.H // 2, self.W // 2), dtype=np.uint8)
    self._uv = np.empty((self.H // 2, self.W), dtype=np.uint8)
    self._nv12_out = np.empty(self.frame_size, dtype=np.uint8)

  def _assemble_nv12(self, y, u, v):
    y = cv.resize(y, (self.W, self.H), interpolation=cv.INTER_LINEAR, dst=self._y_rs)
    u = cv.resize(u, (self.W // 2, self.H // 2), interpolation=cv.INTER_LINEAR, dst=self._u_rs)
    v = cv.resize(v, (self.W // 2, self.H // 2), interpolation=cv.INTER_LINEAR, dst=self._v_rs)
    uv = self._uv
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    out = self._nv12_out
    out.fill(0)
    # Y plane: row pitch = stride
    for r in range(self.H):
      out[r * self.stride:r * self.stride + self.W] = y[r]
    # interleaved UV plane: row pitch = stride, W/2 pairs per row
    uvflat = uv.reshape(-1)
    for r in range(self.H // 2):
      dst = self.uv_offset + r * self.stride
      out[dst:dst + self.W] = uvflat[r * self.W:(r + 1) * self.W]
    return out.tobytes()

  def uyvy_to_nv12(self, frame):
    # OpenCV/CAP_V4L2 path byte order (measured 2026-10-17 on this 8MP GMSL):
    # standard YUYV -> Y=a[0::2], U=a[1::4], V=a[3::4] (Ystd=35 real picture).
    # The old V4L2Reader assumption (V0 Y0 U0 Y1, Y=a[1::2]) yields
    # Ystd=8.7 U≈V≈91 -> green screen on this path.
    a = frame.reshape(-1)
    y = a[0::2].reshape(self.src_h, self.src_w)
    u = a[1::4].reshape(self.src_h, self.src_w // 2)
    v = a[3::4].reshape(self.src_h, self.src_w // 2)
    if self._bright_lut is not None:
      y = cv.LUT(y, self._bright_lut)
    return self._assemble_nv12(y, u, v)

  def read_frames(self):
    while True:
      ok, frame = self.cap.read()
      if not ok or frame is None:
        continue
      yield self.uyvy_to_nv12(frame)
    # never reached; stream close handled by manager

  def close(self):
    self.cap.release()