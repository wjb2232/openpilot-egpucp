#!/usr/bin/env python3
"""TrtModelState: TRT-based big-model backend for modeld.

Replaces the tinygrad run_model with an OpenCV warp + numpy queues + TensorRT
pipeline. Used when a serialized TRT plan exists next to the ONNX model. Falls
back to the original tinygrad ModelState when the plan is absent.

Interface mirrors ModelState (sunnypilot modeld_v2): __init__(cam_w, cam_h,
chestnut), run(bufs, transforms, inputs, after_enqueue), warmup().
"""
import os
import numpy as np
import cv2

from openpilot.common.params import Params
from openpilot.selfdrive.modeld.helpers import modeld_pkl_path, load_oob
from openpilot.selfdrive.modeld.compile_modeld import nv12_copy_size
from openpilot.common.file_chunker import open_file_chunked
from openpilot.selfdrive.modeld.constants import ModelConstants
from openpilot.selfdrive.modeld.parse_model_outputs import Parser
from openpilot.system.camerad.cameras.nv12_info import get_nv12_info
from openpilot.selfdrive.modeld.trt_runner import TrtRunner


def _make_metadata_from_pkl(chestnut: bool):
  """Reuse metadata (output_slices, input_shapes) from the compiled tinygrad pkl
  so we don't need a separate metadata file; the model outputs are identical."""
  pkl = modeld_pkl_path(chestnut)
  jits = load_oob(open_file_chunked(pkl))
  return jits['metadata']


class TrtModelState:
  prev_desire: np.ndarray

  def __init__(self, cam_w: int, cam_h: int, chestnut: bool, plan_path: str):
    self.lat_delay = Params().get("LagdValueCache", return_default=True)
    self.cam_w, self.cam_h = cam_w, cam_h
    self.chestnut = chestnut
    self.plan_path = plan_path
    self.trt = TrtRunner(plan_path)
    md = _make_metadata_from_pkl(chestnut)
    self.input_shapes = md['input_shapes']
    self.vision_input_names = [k for k in self.input_shapes if 'img' in k]
    self.output_slices = md['output_slices']
    self.parser = Parser()
    self.prev_desire = np.zeros(ModelConstants.DESIRE_LEN, dtype=np.float32)
    self.frame_skip = ModelConstants.MODEL_RUN_FREQ // ModelConstants.MODEL_CONTEXT_FREQ
    self.frame_copy_size = nv12_copy_size(*get_nv12_info(cam_w, cam_h)[:3])
    self.nv12 = get_nv12_info(cam_w, cam_h)
    self.stride, self.y_h, self.uv_h, self._size = self.nv12

    # numpy queues
    img_shp = self.input_shapes['img']  # (1, 12, 128, 256)
    n_frames = img_shp[1] // 6
    fb = self.input_shapes['features_buffer']
    feat_dim = int(np.prod(fb[2:]))
    dp = self.input_shapes['desire_pulse']
    self.img_buf_shape = (self.frame_skip * (n_frames - 1) + 1, 6, img_shp[2], img_shp[3])
    self.feat_dim = feat_dim
    self.img_q = np.zeros(self.img_buf_shape, dtype=np.uint8)
    self.big_q = np.zeros(self.img_buf_shape, dtype=np.uint8)
    self.feat_q = np.zeros((self.frame_skip * fb[1], fb[0], feat_dim), dtype=np.float32)
    self.desire_q = np.zeros((self.frame_skip * dp[1], dp[0], dp[2]), dtype=np.float32)
    self.model_dtypes = {n: self.trt.io[n]['npdt'] for n in self.trt.input_names}
    self.prev_feat = np.zeros((1, feat_dim), dtype=np.float32)

  def slice_outputs(self, model_outputs: np.ndarray, output_slices: dict[str, slice]) -> dict[str, np.ndarray]:
    return {k: model_outputs[np.newaxis, v] for k, v in output_slices.items()}

  def _warp(self, frame_buf, M):
    W, H = self.cam_w, self.cam_h
    stride, y_h = self.stride, self.y_h
    mw, mh = 512, 256
    y = frame_buf[:stride * y_h].reshape(y_h, stride)
    uv = frame_buf[stride * y_h:].reshape(self.uv_h, stride)
    M_uv = M * np.array([[1.0, 1.0, 0.5], [1.0, 1.0, 0.5], [2.0, 2.0, 1.0]], dtype=np.float32)
    yw = cv2.warpPerspective(y[:H, :W], M, (mw, mh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    uw = cv2.warpPerspective(uv[:self.y_h // 2, :W:2], M_uv, (mw // 2, mh // 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    vw = cv2.warpPerspective(uv[:self.y_h // 2, 1:W:2], M_uv, (mw // 2, mh // 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    yuv = np.concatenate([yw.reshape(-1), uw.reshape(-1), vw.reshape(-1)]).reshape(mh * 3 // 2, mw)
    Hh, Ww = mh // 2, mw // 2
    return np.stack([
      yuv[0:mh:2, 0::2], yuv[1:mh:2, 0::2], yuv[0:mh:2, 1::2], yuv[1:mh:2, 1::2],
      yuv[mh:mh + mh // 4].reshape(Hh, Ww), yuv[mh + mh // 4:mh + mh // 2].reshape(Hh, Ww),
    ])

  def _sample_skip(self, buf):
    return buf[::self.frame_skip].reshape(1, -1)

  def _sample_desire(self, buf):
    b = buf.reshape(-1, self.frame_skip, *buf.shape[1:])
    return b.max(1).reshape(1, -1)

  def run(self, bufs, transforms, inputs, after_enqueue=None):
    frame_buf = np.frombuffer(bufs['img'].data, dtype=np.uint8, count=self.frame_copy_size)
    big_frame_buf = np.frombuffer(bufs['big_img'].data, dtype=np.uint8, count=self.frame_copy_size)

    # desire pulse (rising edge, same as ModelState)
    inputs['desire_pulse'][0] = 0
    desire = np.where(inputs['desire_pulse'] - self.prev_desire > .99, inputs['desire_pulse'], 0)
    self.prev_desire[:] = inputs['desire_pulse']
    tfm = transforms['img'].copy()
    big_tfm = transforms['big_img'].copy()

    # warp + queues
    w1 = self._warp(frame_buf, tfm)
    w2 = self._warp(big_frame_buf, big_tfm)
    self.img_q[:-1] = self.img_q[1:]
    self.img_q[-1] = w1
    self.big_q[:-1] = self.big_q[1:]
    self.big_q[-1] = w2
    self.feat_q[:-1] = self.feat_q[1:]
    self.feat_q[-1] = self.prev_feat.reshape(1, 1, -1)
    self.desire_q[:-1] = self.desire_q[1:]
    self.desire_q[-1] = desire.reshape(1, 1, -1)

    trt_inputs = {
      'img': self._sample_skip(self.img_q).reshape(self.input_shapes['img']).astype(self.model_dtypes['img']),
      'big_img': self._sample_skip(self.big_q).reshape(self.input_shapes['big_img']).astype(self.model_dtypes['big_img']),
      'desire_pulse': self._sample_desire(self.desire_q).reshape(self.input_shapes['desire_pulse']).astype(self.model_dtypes['desire_pulse']),
      'features_buffer': self._sample_skip(self.feat_q).reshape(self.input_shapes['features_buffer']).astype(self.model_dtypes['features_buffer']),
      'traffic_convention': inputs['traffic_convention'].reshape(1, 2).astype(self.model_dtypes['traffic_convention']),
      'action_t': inputs['action_t'].reshape(1, 2).astype(self.model_dtypes['action_t']),
    }
    model_output = self.trt.run_np(trt_inputs)  # (18452,)
    if after_enqueue is not None:
      after_enqueue()
    if self.chestnut and not np.all(np.isfinite(model_output)):
      raise RuntimeError("model output not finite")
    outputs_dict = self.parser.parse_outputs(self.slice_outputs(model_output, self.output_slices))
    self.prev_feat[:] = model_output[self.output_slices['hidden_state']]
    if os.environ.get('SEND_RAW_PRED'):
      outputs_dict['raw_pred'] = model_output.copy()
    return outputs_dict

  def warmup(self) -> None:
    dummy_frames = {k: np.zeros(self.frame_copy_size, dtype=np.uint8) for k in self.vision_input_names}
    eye = np.eye(3, dtype=np.float32)
    dims = {'desire_pulse': ModelConstants.DESIRE_LEN, 'traffic_convention': 2, 'action_t': 2}
    self.run(dummy_frames, dict.fromkeys(self.vision_input_names, eye),
             {k: np.zeros(v, dtype=np.float32) for k, v in dims.items()})
    # 重置队列
    self.img_q[:] = 0
    self.big_q[:] = 0
    self.feat_q[:] = 0
    self.desire_q[:] = 0
    self.prev_desire[:] = 0