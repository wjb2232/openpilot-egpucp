#!/usr/bin/env python3
"""TRT ONNX inference backend for modeld.

Loads a serialized TensorRT plan (built from the ONNX model) and runs it as a
drop-in replacement for the tinygrad model runner. The caller keeps tinygrad's
warp/queue logic; only the final ONNX execution is delegated here.

CUDA context isolation: tinygrad creates its own CUDA context; TRT must run in
its own context to avoid clobbering tinygrad's current-context state. We create
a dedicated context on init and push/pop it around every execute + memcpy.
"""
import ctypes
import numpy as np
import tensorrt as trt


class TrtRunner:
  def __init__(self, plan_path: str, feedback_pairs: dict[str, str] | None = None,
               d2h_outputs: list[str] | None = None):
    """feedback_pairs: 状态回环映射 {输入名: 输出名}。每帧 execute 前把上帧
    输出缓冲 D2D 拷回输入缓冲, 输入不再走 H2D、输出不再 D2H —— 数据本来就在
    显存里, 每帧两趟 8.4MB 的 memcpy 是纯浪费。
    d2h_outputs: 需要拷回宿主的输出名列表; None = 全部拷回(旧行为)。"""
    self.plan_path = plan_path
    self.feedback_pairs = dict(feedback_pairs or {})
    self._d2h_outputs = d2h_outputs  # IO 布局建立后再解析(None = 全部)
    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    with open(plan_path, 'rb') as f:
      self.engine = runtime.deserialize_cuda_engine(f.read())
    self.ctx = self.engine.create_execution_context()

    # cudart + cuda driver API
    self.cudart = ctypes.CDLL('/usr/local/cuda/lib64/libcudart.so.13')
    self.cudart.cudaMalloc.restype = ctypes.c_int
    self.cudart.cudaFree.restype = ctypes.c_int
    self.cudart.cudaMemcpy.restype = ctypes.c_int
    self.cudart.cudaDeviceSynchronize.restype = ctypes.c_int
    # CRITICAL: without argtypes, ctypes converts Python int args to 32-bit
    # c_int — a host pointer like 0xffff9ade04d20 truncates to 0xade04d20 and
    # memcpy SIGSEGVs in cudaMemcpy during warmup. Declare all signatures.
    self.cudart.cudaMalloc.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
    self.cudart.cudaFree.argtypes = [ctypes.c_void_p]
    self.cudart.cudaMemcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    self.cudart.cudaMemset.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
    self.cudart.cudaMemset.restype = ctypes.c_int
    self.cudart.cudaDeviceSynchronize.argtypes = []
    self.drv = ctypes.CDLL('/usr/lib/aarch64-linux-gnu/libcuda.so')
    self.drv.cuInit.restype = ctypes.c_int
    self.drv.cuCtxCreate_v2.restype = ctypes.c_int
    self.drv.cuCtxPushCurrent_v2.restype = ctypes.c_int
    self.drv.cuCtxPopCurrent_v2.restype = ctypes.c_int
    self.drv.cuCtxCreate_v2.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int]
    self.drv.cuCtxPushCurrent_v2.argtypes = [ctypes.c_void_p]

    # 自建 context(隔离 tinygrad)。
    # NOTE: 不能用 assert 检查返回码!manager 以 PYTHONOPTIMIZE=1 运行,
    # assert 全被剥离后 CUDA 错误被静默吞掉(dev=None, 输出全 0, 无轨迹)。
    # 显式检查 + 抛异常,任何模式都生效。
    def cuda_check(rc: int, what: str) -> None:
      if rc != 0:
        raise RuntimeError(f"CUDA {what} failed rc={rc}")

    cuda_check(self.drv.cuInit(0), "cuInit")
    self.cu_ctx = ctypes.c_void_p()
    cuda_check(self.drv.cuCtxCreate_v2(ctypes.byref(self.cu_ctx), 0, 0), "cuCtxCreate_v2")
    if not self.cu_ctx.value:
      raise RuntimeError("cuCtxCreate_v2 returned NULL context")
    cuda_check(self.drv.cuCtxPushCurrent_v2(self.cu_ctx), "cuCtxPushCurrent_v2")

    # IO layout
    dtype_map = {trt.DataType.FLOAT: np.float32, trt.DataType.HALF: np.float16, trt.DataType.UINT8: np.uint8}
    self.io = {}
    self.input_names = []
    self.output_names = []
    names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]
    for n in names:
      shape = self.engine.get_tensor_shape(n)
      dt = self.engine.get_tensor_dtype(n)
      npdt = dtype_map[dt]
      nbytes = int(np.prod(shape)) * np.dtype(npdt).itemsize
      dev = self._cuda_malloc(nbytes)
      self.io[n] = dict(shape=tuple(shape), dt=dt, npdt=npdt, nbytes=nbytes, dev=dev)
      if self.engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT:
        self.input_names.append(n)
      else:
        self.output_names.append(n)
    self.bindings = [self.io[n]['dev'] for n in names]
    self.d2h_outputs = set(self.output_names) if self._d2h_outputs is None else set(self._d2h_outputs)
    # skip_h2d: 调用方(如 GPU warp)直接写设备缓冲的输入, run_np 不再上传覆盖
    self.skip_h2d: set[str] = set()
    # stateful 契约(N16 等)是 1 个 outputs + 5 个 next_state_* 输出;全部拷回。
    self.out_hosts = {n: np.zeros(int(np.prod(self.io[n]['shape'])), dtype=self.io[n]['npdt'])
                      for n in self.output_names}

  def _push(self):
    rc = self.drv.cuCtxPushCurrent_v2(self.cu_ctx)
    if rc != 0:
      raise RuntimeError(f"cuCtxPushCurrent_v2 rc={rc}")

  def _pop(self):
    ctx = ctypes.c_void_p()
    rc = self.drv.cuCtxPopCurrent_v2(ctypes.byref(ctx))
    if rc != 0:
      raise RuntimeError(f"cuCtxPopCurrent_v2 rc={rc}")

  def _cuda_malloc(self, nbytes: int) -> int:
    ptr = ctypes.c_void_p()
    rc = self.cudart.cudaMalloc(ctypes.byref(ptr), nbytes)
    if rc != 0 or not ptr.value:
      raise RuntimeError(f"cudaMalloc rc={rc} size={nbytes}")
    return ptr.value

  def run_np(self, inputs: dict[str, np.ndarray]) -> np.ndarray:
    self._push()
    try:
      # 状态回环: 上帧 next_* 输出仍在显存, D2D 直接回填本帧输入缓冲。
      for dst, src in self.feedback_pairs.items():
        rc = self.cudart.cudaMemcpy(ctypes.c_void_p(self.io[dst]['dev']),
                                    ctypes.c_void_p(self.io[src]['dev']),
                                    self.io[dst]['nbytes'], 3)  # D2D
        if rc != 0:
          raise RuntimeError(f"cudaMemcpy D2D {dst}<-{src} rc={rc}")
      for n in self.input_names:
        if n in self.feedback_pairs or n in self.skip_h2d:
          continue
        arr = inputs[n]
        if arr.dtype != self.io[n]['npdt']:
          raise TypeError(f'{n}: want {self.io[n]["npdt"]}, got {arr.dtype}')
        arr = np.ascontiguousarray(arr).ravel()
        rc = self.cudart.cudaMemcpy(ctypes.c_void_p(self.io[n]['dev']),
                                    arr.ctypes.data, arr.nbytes, 1)  # H2D
        if rc != 0:
          raise RuntimeError(f"cudaMemcpy H2D {n} rc={rc}")
      if not self.ctx.execute_v2(self.bindings):
        raise RuntimeError("TRT execute_v2 returned False")
      for n in self.output_names:
        if n not in self.d2h_outputs:
          continue
        rc = self.cudart.cudaMemcpy(self.out_hosts[n].ctypes.data,
                                    ctypes.c_void_p(self.io[n]['dev']),
                                    self.out_hosts[n].nbytes, 2)  # D2H
        if rc != 0:
          raise RuntimeError(f"cudaMemcpy D2H {n} rc={rc}")
      if len(self.output_names) == 1:
        return self.out_hosts[self.output_names[0]].copy()
      # 多输出: 返回宿主缓冲视图。缓冲在下次 run_np 前保持有效, 调用方必须
      # 在下一帧之前完成解析/回填(modeld 的单线程帧循环保证这一点)。
      return {n: self.out_hosts[n] for n in self.output_names if n in self.d2h_outputs}
    finally:
      self._pop()

  def zero_device_feedback(self) -> None:
    """清零回环两端(输入+输出)的设备缓冲, 配合 reset() 使用。"""
    if not self.feedback_pairs:
      return
    self._push()
    try:
      for dst, src in self.feedback_pairs.items():
        for n in (dst, src):
          rc = self.cudart.cudaMemset(ctypes.c_void_p(self.io[n]['dev']), 0, self.io[n]['nbytes'])
          if rc != 0:
            raise RuntimeError(f"cudaMemset {n} rc={rc}")
    finally:
      self._pop()

  def close(self):
    for v in self.io.values():
      self.cudart.cudaFree(v['dev'])

  def __del__(self):
    try:
      self.close()
    except Exception:
      pass


if __name__ == '__main__':
  import time
  r = TrtRunner('/data/openpilot_c3/openpilot/selfdrive/modeld/models/big_driving_supercombo_trt.plan')
  inputs = {}
  for n in r.input_names:
    shape = r.io[n]['shape']
    inputs[n] = np.random.randn(*shape).astype(r.io[n]['npdt'])
    if n in ('img', 'big_img'):
      inputs[n] = np.random.randint(0, 255, shape).astype(r.io[n]['npdt'])
  for _ in range(3):
    out = r.run_np(inputs)
  t0 = time.perf_counter()
  for _ in range(10):
    out = r.run_np(inputs)
  print(f'10 runs avg {(time.perf_counter()-t0)*100:.1f}ms')
  print('out shape:', out.shape, 'sample:', out[:6])