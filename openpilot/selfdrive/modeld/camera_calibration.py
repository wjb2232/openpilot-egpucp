#!/usr/bin/env python3
"""camera_calibration: 内参/外参自进化结果的读取与合成。

消费 intrinsic_calibd.py 写入 Params 的 CamCalibRoad / CamCalibWide(json):
  {"f": float, "pitch_offset": float, "samples": int, "span": float,
   "std": float, "converged": bool, "mode": str, "t": int}

- f: 该镜头的有效焦距(fx=fy), 覆盖 DEVICE_CAMERAS 的出厂内参
- pitch_offset: 镜头安装俯仰偏置(rad), 叠加到 calibrationd 的 rpyCalib[1]

CalibrationCache: 带 TTL 的缓存, modeld 每帧调用 resolve() 不落盘。
compose_camera_euler: 把 calibrationd 的设备-标定欧拉角与镜头俯仰偏置合成
  最终的相机欧拉角, 供 get_warp_matrix 使用。
"""
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class CameraCalib:
  f: float
  pitch_offset: float = 0.0
  converged: bool = True
  source: str = "prior"

  @property
  def focal_length(self) -> float:
    return self.f


@dataclass
class CameraCalibration:
  road: CameraCalib = field(default_factory=lambda: CameraCalib(2508.0))
  wide: CameraCalib = field(default_factory=lambda: CameraCalib(405.2))
  as_of: float = 0.0


def _read_param(param_name: str, default_f: float) -> Optional[CameraCalib]:
  from openpilot.common.params import Params
  try:
    raw = Params().get(param_name)
  except Exception:
    return None
  if not raw:
    return None
  try:
    d = json.loads(raw)
  except Exception:
    return None
  f = float(d.get("f", default_f))
  # 未收敛的值绝不采用:坏标定比无标定更危险(modeld 会拿它算 warp)
  converged = bool(d.get("converged", False))
  if not converged:
    return None
  pitch_offset = float(d.get("pitch_offset", 0.0))
  return CameraCalib(f, pitch_offset, True, d.get("mode", "params"))


def compose_camera_euler(device_from_calib_euler: np.ndarray,
                         wide_from_device_euler: Optional[np.ndarray],
                         pitch_offset: float = 0.0) -> np.ndarray:
  """合成最终相机欧拉角:
  - road:  device_from_calib + pitch_offset(沿设备 pitch 轴叠加)
  - wide:  device_from_calib + wide_from_device + pitch_offset
  """
  e = np.array(device_from_calib_euler, dtype=np.float32).copy()
  if wide_from_device_euler is not None:
    w = np.array(wide_from_device_euler, dtype=np.float32)
    # 简单加法近似:wide 相对 device 的欧拉角叠加(与 upstream 一致)
    e[1] += w[1]
    e[2] += w[2]
    e[0] += w[0]
  if pitch_offset != 0.0:
    e[1] += float(pitch_offset)
  return e


class CalibrationCache:
  """TTL 缓存 CamCalib* 参数, 避免 modeld 每帧读 Params。"""

  def __init__(self, ttl: float = 5.0):
    self.ttl = ttl
    self._cache: Optional[CameraCalibration] = None
    self._fetched_at: float = 0.0

  def resolve(self, params, dc, now: float) -> CameraCalibration:
    if self._cache is not None and (now - self._fetched_at) < self.ttl:
      return self._cache

    # 默认:DEVICE_CAMERAS 出厂内参
    try:
      default_road = float(np.array(dc.fcam.intrinsics)[0, 0]) if hasattr(dc, "fcam") else 2508.0
      default_wide = float(np.array(dc.ecam.intrinsics)[0, 0]) if hasattr(dc, "ecam") else 405.2
    except Exception:
      default_road, default_wide = 2508.0, 405.2

    # try DEVICE_CAMERAS narrow/wide_road names (c3 fork)
    try:
      if hasattr(dc, "narrow_road"):
        default_road = float(np.array(dc.narrow_road.intrinsics)[0, 0])
      if hasattr(dc, "wide_road"):
        default_wide = float(np.array(dc.wide_road.intrinsics)[0, 0])
    except Exception:
      pass

    road = _read_param("CamCalibRoad", default_road)
    wide = _read_param("CamCalibWide", default_wide)
    calib = CameraCalibration(
      road=road or CameraCalib(default_road, 0.0, True, "prior"),
      wide=wide or CameraCalib(default_wide, 0.0, True, "prior"),
      as_of=now,
    )
    self._cache = calib
    self._fetched_at = now
    return calib
