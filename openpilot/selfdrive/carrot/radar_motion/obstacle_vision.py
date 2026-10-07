#!/usr/bin/env python3
"""obstacle_vision.py —— 视觉小目标检测(行人/自行车/动物/锥桶等)。

用 YOLOv8n(COCO)在 roadCameraState 画面上检测小目标,
经内参投影换算成"虚拟障碍"(距离/横向偏移),供 avoidance 融合。

检测类别(COCO):person=0, bicycle=1, motorcycle=3, cat=15, dog=16, horse=17
动物/锥桶可扩展(锥桶需自定义模型,COCO 无;先用 person/bicycle/motorcycle/动物)。

关键点:
- 只处理低频(每 3 帧)降低 CPU(软渲染设备 YOLO 每帧很贵)
- 检测框底部中点 = 目标着地点 → 用 pinhole 模型换算距离
- 只报告"足够近"的目标(< 40m),远处交给雷达/模型
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np
import cv2

# COCO 类别索引(需检测的目标)
INTEREST_CLASSES = {
  0: "person",
  1: "bicycle",
  3: "motorcycle",
  15: "cat",
  16: "dog",
  17: "horse",
  18: "cow",
  19: "sheep",
}

# 相机内参(与 camera.py 的 J501 一致:1344x760, road f=2508)
CAM_W = 1344
CAM_H = 760
ROAD_FOCAL = 2508.0
CY = CAM_H / 2.0

MIN_DETECT_DREL_M = 2.0    # 最近检测距离
MAX_DETECT_DREL_M = 40.0   # 最远检测距离
CONF_THRESHOLD = 0.45      # 检测置信度
NMS_THRESHOLD = 0.45
DETECT_EVERY_N = 3         # 每 N 帧检测一次


@dataclass(frozen=True)
class VisionObstacle:
  cls: str
  d_rel: float    # 纵向距离 m
  y_rel: float    # 横向偏移 m(正=右)
  conf: float
  bbox: tuple     # (x1,y1,x2,y2) 原图坐标


class VisionObstacleDetector:
  """YOLOv8n 小目标检测 → 虚拟障碍。"""

  def __init__(self, model_path: str = "/home/nvidia/yolov8n.onnx"):
    self.net = cv2.dnn.readNetFromONNX(model_path)
    self._frame_count = 0

  def _pixel_to_meter(self, bbox_bottom_center_x: float, bbox_bottom_y: float) -> tuple[float, float]:
    """检测框底部中点(着地点)→ (d_rel, y_rel)。
    pinhole: d_rel = f * h / (y - cy)?? 这里用简化:假设相机高 1.3m, pitch≈0
    实际:y_rel = (x - cx) * d_rel / f; d_rel 由目标高度估算。
    简化:用目标框高度反推距离(目标典型高度 person 1.7m)。
    """
    return 0.0, 0.0  # 由调用方按类别高度计算

  def detect(self, y_plane: np.ndarray) -> list[VisionObstacle]:
    """输入 road Y 平面(1344x760 uint8),返回障碍列表。"""
    self._frame_count += 1
    if self._frame_count % DETECT_EVERY_N != 0:
      return []

    # YOLO 输入 640x640,letterbox(保持宽高比)
    h_in, w_in = y_plane.shape[:2]
    scale = 640 / max(w_in, h_in)
    nw, nh = int(w_in * scale), int(h_in * scale)
    # 单通道 Y → 3 通道(blobFromImage 单通道会导致检测为空)
    if y_plane.ndim == 2:
      img3 = cv2.cvtColor(y_plane, cv2.COLOR_GRAY2BGR)
    else:
      img3 = y_plane
    resized = cv2.resize(img3, (nw, nh))
    canvas = np.full((640, 640, 3), 114, np.uint8)
    dx, dy = (640 - nw) // 2, (640 - nh) // 2
    canvas[dy:dy + nh, dx:dx + nw] = resized
    blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (640, 640), swapRB=True, crop=False)
    self.net.setInput(blob)
    t0 = time.time()
    try:
      outs = self.net.forward()
    except Exception:
      return []
    infer_ms = (time.time() - t0) * 1000

    # YOLOv8 输出: [1, 84, 8400] → 转置 [8400, 84]
    outs = outs[0].T
    boxes = []
    scores = []
    classes = []
    for row in outs:
      classes_scores = row[4:]
      cls_id = int(np.argmax(classes_scores))
      conf = float(classes_scores[cls_id])
      if conf < CONF_THRESHOLD:
        continue
      if cls_id not in INTEREST_CLASSES:
        continue
      cx, cy_, w, h = row[:4]
      # letterbox 逆映射回原图坐标
      x1n = (cx - w / 2 - dx) / scale
      y1n = (cy_ - h / 2 - dy) / scale
      x2n = (cx + w / 2 - dx) / scale
      y2n = (cy_ + h / 2 - dy) / scale
      boxes.append([x1n, y1n, x2n, y2n])
      scores.append(conf)
      classes.append(cls_id)

    if not boxes:
      return []
    idxs = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, NMS_THRESHOLD)
    result = []
    for i in idxs:
      i = int(i)
      x1, y1, x2, y2 = boxes[i]
      conf = scores[i]
      cls = INTEREST_CLASSES[classes[i]]
      # 目标典型高度(米)按类别估算,用框高反推距离
      obj_h = {"person": 1.7, "bicycle": 1.1, "motorcycle": 1.3,
               "cat": 0.3, "dog": 0.4, "horse": 1.5, "cow": 1.4, "sheep": 0.8}.get(cls, 1.0)
      box_h = max(y2 - y1, 10.0)
      d_rel = ROAD_FOCAL * obj_h / box_h  # f * 高度 / 像素高
      if not (MIN_DETECT_DREL_M <= d_rel <= MAX_DETECT_DREL_M):
        continue
      # 横向:底部中点相对图像中心
      bottom_cx = (x1 + x2) / 2
      y_rel = (bottom_cx - CAM_W / 2) * d_rel / ROAD_FOCAL
      result.append(VisionObstacle(cls, d_rel, y_rel, conf, (x1, y1, x2, y2)))
    return result