#!/usr/bin/env python3
"""GPU warp: NV12 camera frame -> 6-plane model input via the CUDA kernel in
warp_kernel.cu (compiled to libgpuwarp.so, see build_gpu_warp.sh).

Replaces the per-frame cv2.warpPerspective CPU work in TrtModelState._warp.
All calls run inside the TrtRunner CUDA context (the caller pushes it around a
whole frame): raw NV12 is uploaded H2D once and the kernel writes the warped
planes straight into the engine's new_img device buffer, so run_np skips the
new_img H2D entirely. Any load/launch failure raises and the caller flips back
to the CPU path permanently.
"""
import ctypes

import numpy as np


class Mat3(ctypes.Structure):
  _fields_ = [('m', ctypes.c_float * 9)]


def _mat3(a: np.ndarray) -> Mat3:
  m = Mat3()
  a = np.ascontiguousarray(a, dtype=np.float32).reshape(-1)
  for i in range(9):
    m.m[i] = float(a[i])
  return m


class GpuWarp:
  """One instance per TrtRunner. Single-threaded use (modeld frame loop /
  loader thread), caller owns context push/pop."""

  def __init__(self, runner, lib_path: str):
    self.runner = runner
    self.lib = ctypes.CDLL(lib_path)
    ptr, i = ctypes.c_void_p, ctypes.c_int
    lib = self.lib
    lib.gpuw_upload.restype = i
    lib.gpuw_upload.argtypes = [ptr, ptr, i]
    lib.gpuw_y4.restype = i
    lib.gpuw_y4.argtypes = [ptr, i, i, i, i, Mat3, ptr, i, i, i]
    lib.gpuw_uv2.restype = i
    lib.gpuw_uv2.argtypes = [ptr, i, i, i, Mat3, ptr, i, i, i]
    lib.gpuw_sync.restype = i
    lib.gpuw_sync.argtypes = []
    self._staging: dict[int, int] = {}     # cam idx -> dev ptr
    self._staging_bytes: dict[int, int] = {}
    # 零拷贝: cudaHostRegister(Mapped) 把 VisionBuf 的 mmap 共享内存注册成
    # GPU 可直读的映射 (Tegra 统一内存), kernel 直接读帧, 免去每帧
    # 2x~4.4MB 的同步 H2D memcpy。按 host 地址缓存 (VisionIpc 缓冲轮转,
    # 地址集合有限); 任一次注册失败则整个功能降级回 staging 上传路径。
    cud = self.runner.cudart
    cud.cudaHostRegister.argtypes = [ptr, ctypes.c_size_t, ctypes.c_uint]
    cud.cudaHostRegister.restype = i
    cud.cudaHostGetDevicePointer.argtypes = [ctypes.POINTER(ptr), ptr, i]
    cud.cudaHostGetDevicePointer.restype = i
    self._mapped: dict[int, int] = {}      # host addr -> device-readable ptr
    self._mapped_ok = True

  def _mapped_for(self, host_addr: int, nbytes: int) -> int | None:
    d = self._mapped.get(host_addr)
    if d is not None:
      return d
    cud = self.runner.cudart
    rc = cud.cudaHostRegister(ctypes.c_void_p(host_addr), nbytes, 2)  # cudaHostRegisterMapped
    if rc == 0:
      dptr = ctypes.c_void_p()
      rc = cud.cudaHostGetDevicePointer(ctypes.byref(dptr), ctypes.c_void_p(host_addr), 0)
      if rc == 0:
        self._mapped[host_addr] = dptr.value or host_addr  # Tegra 统一地址时两者相同
        return self._mapped[host_addr]
      cud.cudaHostUnregister(ctypes.c_void_p(host_addr))
    self._mapped_ok = False  # memlock 限制/不支持映射: 不再反复尝试
    return None

  def _staging_for(self, cam_idx: int, nbytes: int) -> int:
    # 两路相机分辨率可能不同, 缓冲按需增长
    if self._staging.get(cam_idx) is None or self._staging_bytes[cam_idx] < nbytes:
      if cam_idx in self._staging:
        self.runner.cudart.cudaFree(ctypes.c_void_p(self._staging[cam_idx]))
      self._staging[cam_idx] = self.runner._cuda_malloc(nbytes)
      self._staging_bytes[cam_idx] = nbytes
    return self._staging[cam_idx]

  def warp_camera(self, cam_idx: int, frame: np.ndarray, src_stride: int, src_uv_offset: int,
                  src_w: int, src_h: int, transform: np.ndarray,
                  out_dev: int, out_base: int, out_w: int, out_h: int) -> None:
    """Warp one camera into out_dev[out_base : out_base + 6*out_w*out_h].
    transform: OUTPUT->INPUT (model->camera), same convention as the CPU path.
    Zero-copy when the frame buffer is registered mapped; else staging H2D."""
    host = frame.ctypes.data
    src_dev = self._mapped_for(host, frame.nbytes) if self._mapped_ok else None
    if src_dev is None:
      stage = self._staging_for(cam_idx, frame.nbytes)
      rc = self.lib.gpuw_upload(ctypes.c_void_p(stage), ctypes.c_void_p(host),
                                int(frame.nbytes))
      if rc != 0:
        raise RuntimeError(f'gpuw_upload rc={rc}')
      src_dev = stage
    # 与 CPU 路径数值对齐。注意 cv2.warpPerspective 默认 flag 下会先 invert
    # 传入矩阵再采样 dst(x,y)=src(inv(H)·(x,y)), 所以 CPU 两条 warp 的真实
    # 采样矩阵是: Y = inv(M_inv) = transform 本身; UV = inv(M_inv ⊙ A)
    # (⊙ 为逐元素乘)。kernel 只认最终采样矩阵, 这里把 invert 先做完传下去。
    T = np.asarray(transform, dtype=np.float32)
    M_inv = np.linalg.inv(T)
    M_uv = M_inv * np.array([[1.0, 1.0, 0.5], [1.0, 1.0, 0.5], [2.0, 2.0, 1.0]], dtype=np.float32)
    M_uv_s = np.linalg.inv(M_uv)
    plane = out_w * out_h
    rc = self.lib.gpuw_y4(ctypes.c_void_p(src_dev), int(src_stride), int(src_uv_offset),
                          int(src_w), int(src_h), _mat3(T),
                          ctypes.c_void_p(out_dev), int(out_base), int(out_w), int(out_h))
    if rc != 0:
      raise RuntimeError(f'gpuw_y4 rc={rc}')
    rc = self.lib.gpuw_uv2(ctypes.c_void_p(src_dev), int(src_stride), int(src_uv_offset),
                           int(src_w), _mat3(M_uv_s),
                           ctypes.c_void_p(out_dev), int(out_base + 4 * plane),
                           int(out_w), int(out_h))
    if rc != 0:
      raise RuntimeError(f'gpuw_uv2 rc={rc}')
