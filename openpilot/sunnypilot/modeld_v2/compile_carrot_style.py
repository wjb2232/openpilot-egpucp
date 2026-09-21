#!/usr/bin/env python3
"""Compile a supercombo ONNX into a "carrot-style" combined pkl for modeld_v2.

Layout produced:
  {
    'metadata': {model_checkpoint, output_slices, input_shapes, output_shapes, warp_dev},
    'run_policy': TinyJit,           # supercombo body, compiled on Device.DEFAULT (eGPU)
    (cam_w, cam_h): TinyJit,         # warp, compiled on WARP_DEV (internal GPU)
  }

This mirrors carrot-wip's openpilot/selfdrive/modeld/compile_modeld.py:
the image warp stays on the internal GPU so only the small warped tensor
travels to the eGPU, instead of shipping full camera frames every frame.
"""
import argparse
import os
import sys

os.environ['GMMU'] = '0'

import numpy as np

from tinygrad import dtypes
from tinygrad.device import Device
from tinygrad.engine.jit import TinyJit
from tinygrad.helpers import Context
from tinygrad.tensor import Tensor

from openpilot.selfdrive.modeld.get_model_metadata import make_metadata_dict
from openpilot.selfdrive.modeld.helpers import dump_oob
from openpilot.system.camerad.cameras.nv12_info import get_nv12_info
from openpilot.sunnypilot.modeld_v2.compile_modeld import (
  POLICY_INPUTS,
  WARP_INPUTS,
  _parse_size,
  compile_jit,
  derive_frame_skip,
  make_random_images,
  make_run_policy,
  make_supercombo_input_queues,
  make_warp_queues,
)

WARP_DEV = os.getenv('WARP_DEV') or Device.DEFAULT


def warp_perspective(src_flat, M_inv, dst_shape, src_shape, stride_pad, border_fill_val=None):
  w_dst, h_dst = dst_shape
  h_src, w_src = src_shape

  x = Tensor.arange(w_dst).reshape(1, w_dst).expand(h_dst, w_dst).reshape(-1).to(WARP_DEV)
  y = Tensor.arange(h_dst).reshape(h_dst, 1).expand(h_dst, w_dst).reshape(-1).to(WARP_DEV)

  src_x = M_inv[0, 0] * x + M_inv[0, 1] * y + M_inv[0, 2]
  src_y = M_inv[1, 0] * x + M_inv[1, 1] * y + M_inv[1, 2]
  src_w = M_inv[2, 0] * x + M_inv[2, 1] * y + M_inv[2, 2]

  src_x = src_x / src_w
  src_y = src_y / src_w

  x_round = Tensor.round(src_x)
  y_round = Tensor.round(src_y)
  x_nn_clipped = x_round.clip(0, w_src - 1).cast('int')
  y_nn_clipped = y_round.clip(0, h_src - 1).cast('int')
  idx = y_nn_clipped * (w_src + stride_pad) + x_nn_clipped
  sampled = src_flat[idx]

  if border_fill_val is None:
    return sampled

  in_bounds = ((x_round >= 0) & (x_round <= w_src - 1) &
               (y_round >= 0) & (y_round <= h_src - 1)).cast(sampled.dtype)
  return sampled * in_bounds + Tensor(border_fill_val, dtype=sampled.dtype) * (1 - in_bounds)


def frames_to_tensor(frames):
  H = (frames.shape[0] * 2) // 3
  W = frames.shape[1]
  in_img1 = Tensor.cat(frames[0:H:2, 0::2],
                       frames[1:H:2, 0::2],
                       frames[0:H:2, 1::2],
                       frames[1:H:2, 1::2],
                       frames[H:H + H // 4].reshape((H // 2, W // 2)),
                       frames[H + H // 4:H + H // 2].reshape((H // 2, W // 2)), dim=0).reshape((6, H // 2, W // 2))
  return in_img1


def make_frame_prepare(nv12, model_w, model_h):
  cam_w, cam_h, stride, y_height, uv_height = nv12
  uv_offset = stride * y_height
  stride_pad = stride - cam_w

  def frame_prepare_tinygrad(input_frame, M_inv):
    M_inv_uv = M_inv * Tensor([[1.0, 1.0, 0.5], [1.0, 1.0, 0.5], [2.0, 2.0, 1.0]], device=WARP_DEV)
    uv = input_frame[uv_offset:uv_offset + uv_height * stride].reshape(uv_height, stride)
    with Context(SPLIT_REDUCEOP=0):
      y = warp_perspective(input_frame[:cam_h * stride], M_inv, (model_w, model_h),
                           (cam_h, cam_w), stride_pad).realize()
      u = warp_perspective(uv[:cam_h // 2, :cam_w:2].flatten(), M_inv_uv, (model_w // 2, model_h // 2),
                           (cam_h // 2, cam_w // 2), 0).realize()
      v = warp_perspective(uv[:cam_h // 2, 1:cam_w:2].flatten(), M_inv_uv, (model_w // 2, model_h // 2),
                           (cam_h // 2, cam_w // 2), 0).realize()
    yuv = y.cat(u).cat(v).reshape((model_h * 3 // 2, model_w))
    return frames_to_tensor(yuv)

  return frame_prepare_tinygrad


def make_warp(nv12, model_w, model_h):
  frame_prepare = make_frame_prepare(nv12, model_w, model_h)

  def warp(tfm, big_tfm, frame, big_frame):
    tfm = tfm.to(WARP_DEV)
    big_tfm = big_tfm.to(WARP_DEV)
    Tensor.realize(tfm, big_tfm)

    warped_frame = frame_prepare(frame, tfm).unsqueeze(0)
    warped_big_frame = frame_prepare(big_frame, big_tfm).unsqueeze(0)
    return Tensor.cat(warped_frame, warped_big_frame)

  return warp


def nv12_copy_size(stride, y_height, uv_height):
  return stride * (y_height + uv_height)


if __name__ == "__main__":
  from tinygrad.nn.onnx import OnnxRunner

  p = argparse.ArgumentParser(description="Compile a supercombo ONNX into carrot-style warp+policy pkl")
  p.add_argument('--onnx', required=True)
  p.add_argument('--output', required=True)
  p.add_argument('--model-size', type=_parse_size, required=True, help='model input WxH')
  p.add_argument('--camera-resolutions', type=_parse_size, nargs='+', required=True)
  p.add_argument('--frame-skip', type=int, default=None)
  p.add_argument('--benchmark-runs', type=int, default=1)
  args = p.parse_args()

  model_path = args.onnx
  model_w, model_h = args.model_size

  print(f"Device.DEFAULT={Device.DEFAULT} WARP_DEV={WARP_DEV}", flush=True)
  print(f"loading onnx: {model_path}", flush=True)
  model_runner = OnnxRunner(model_path)
  metadata = make_metadata_dict(model_path)
  input_shapes = metadata['input_shapes']
  print(f"input_shapes: {input_shapes}", flush=True)

  frame_skip = args.frame_skip or derive_frame_skip({}, input_shapes)
  print(f"frame_skip: {frame_skip}", flush=True)

  # 'model' key makes modeld_v2 treat this as a supercombo body with a separate warp JIT,
  # and 'warp_dev' tells it which device the warp JIT was compiled for.
  out = {'metadata': {'model': metadata, 'warp_dev': WARP_DEV}}

  # --- policy (supercombo body) on Device.DEFAULT (eGPU) ---
  run_policy_func = make_run_policy(None, [model_runner], None, frame_skip, input_shapes)
  run_policy_jit = TinyJit(run_policy_func, prune=True)
  img_shape = input_shapes['img']
  make_policy_queues = lambda device: make_supercombo_input_queues(input_shapes, frame_skip, device=device)
  make_random_warped = lambda rng=None: make_random_images(['warped'], (2, 6, *img_shape[2:]), WARP_DEV, rng)
  print("compiling run_policy JIT...", flush=True)
  out['run_policy'] = compile_jit(run_policy_jit, POLICY_INPUTS, make_policy_queues,
                                  make_random_inputs=make_random_warped, benchmark_runs=args.benchmark_runs)

  # --- warp on WARP_DEV (internal GPU) ---
  for cam_w, cam_h in args.camera_resolutions:
    stride, y_height, uv_height, frame_size = get_nv12_info(cam_w, cam_h)
    nv12 = (cam_w, cam_h, stride, y_height, uv_height)
    warp_jit = TinyJit(make_warp(nv12, model_w, model_h), prune=True)
    make_random_frames = lambda rng=None: make_random_images(['frame', 'big_frame'], frame_size, WARP_DEV, rng)
    print(f"compiling warp JIT for {cam_w}x{cam_h}...", flush=True)
    out[(cam_w, cam_h)] = compile_jit(warp_jit, WARP_INPUTS, make_warp_queues,
                                      make_random_inputs=make_random_frames, benchmark_runs=args.benchmark_runs)

  print(f"saving {args.output}", flush=True)
  with open(args.output, "wb") as f:
    dump_oob(out, f)
  print(f"saved {args.output} ({os.path.getsize(args.output) / 1e6:.2f} MB)", flush=True)
