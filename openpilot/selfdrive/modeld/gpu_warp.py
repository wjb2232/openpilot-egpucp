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
    """Upload + warp one camera into out_dev[out_base : out_base + 6*out_w*out_h].
    transform: OUTPUT->INPUT (model->camera), same convention as the CPU path."""
    stage = self._staging_for(cam_idx, frame.nbytes)
    rc = self.lib.gpuw_upload(ctypes.c_void_p(stage), ctypes.c_void_p(frame.ctypes.data),
                              int(frame.nbytes))
    if rc != 0:
      raise RuntimeError(f'gpuw_upload rc={rc}')
    # 与 CPU 路径数值对齐。注意 cv2.warpPerspective 默认 flag 下会先 invert
    # 传入矩阵再采样 dst(x,y)=src(inv(H)·(x,y)), 所以 CPU 两条 warp 的真实
    # 采样矩阵是: Y = inv(M_inv) = transform 本身; UV = inv(M_inv ⊙ A)
    # (⊙ 为逐元素乘)。kernel 只认最终采样矩阵, 这里把 invert 先做完传下去。
    T = np.asarray(transform, dtype=np.float32)
    M_inv = np.linalg.inv(T)
    M_uv = M_inv * np.array([[1.0, 1.0, 0.5], [1.0, 1.0, 0.5], [2.0, 2.0, 1.0]], dtype=np.float32)
    M_uv_s = np.linalg.inv(M_uv)
    plane = out_w * out_h
    rc = self.lib.gpuw_y4(ctypes.c_void_p(stage), int(src_stride), int(src_uv_offset),
                          int(src_w), int(src_h), _mat3(T),
                          ctypes.c_void_p(out_dev), int(out_base), int(out_w), int(out_h))
    if rc != 0:
      raise RuntimeError(f'gpuw_y4 rc={rc}')
    rc = self.lib.gpuw_uv2(ctypes.c_void_p(stage), int(src_stride), int(src_uv_offset),
                           int(src_w), _mat3(M_uv_s),
                           ctypes.c_void_p(out_dev), int(out_base + 4 * plane),
                           int(out_w), int(out_h))
    if rc != 0:
      raise RuntimeError(f'gpuw_uv2 rc={rc}')
