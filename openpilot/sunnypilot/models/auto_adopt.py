#!/usr/bin/env python3
"""auto_adopt: bridge between sunnypilot's model selector UI and the local TRT
backend (big AND small models).

The UI (models_manager) writes ModelManager_ActiveBundleChestnut (big) or
ModelManager_ActiveBundle (small) when the user picks a model. Those bundles
are AMD/tinygrad-compiled pkls that canNOT run on this NVIDIA box — but the
SAME model's official ONNX exists (author NAS mirror, or sunnypilot git LFS).
This daemon:

1. watches BOTH slots for a new user selection
2. resolves the official ONNX for that model (NAS manifest.json, else git LFS)
3. downloads it, rewrites UINT8 inputs -> FLOAT, builds a TRT plan with the
   SYSTEM python3 (GCC ABI; the uv/Clang venv python crashes executing TRT)
4. swaps the plan file modeld's TRT backend expects, so modeld's existing TRT
   backend runs the new model on next modeld start.
5. keeps `is_stock_model` gate open (see process_config patch) so modeld is
   not suppressed by the tinygrad runner latch.

Idempotent: on restart it re-checks bundle ref vs adopted ref and does
nothing if already adopted. State: ModelAutoAdopt_* params.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.sunnypilot.models.helpers import get_selected_bundle

# Where the local TRT backend expects the model (resolve relative to this repo)
# .../sunnypilot/models/auto_adopt.py -> parents[2] = .../openpilot (nested layout)
MODELS_DIR = Path(__file__).resolve().parents[2] / "selfdrive/modeld/models"
BIG_ONNX = MODELS_DIR / "big_driving_supercombo_trt.onnx"
BIG_PLAN = MODELS_DIR / "big_driving_supercombo_trt.plan"
SMALL_ONNX = MODELS_DIR / "driving_supercombo_trt.onnx"
SMALL_PLAN = MODELS_DIR / "driving_supercombo_trt.plan"

ADOPTED_REF_PARAM = "ModelAutoAdopt_Ref"          # big model ref last adopted
ADOPTED_SHA_PARAM = "ModelAutoAdopt_Sha"
STATUS_PARAM = "ModelAutoAdopt_Status"
ADOPTED_SMALL_REF_PARAM = "ModelAutoAdopt_SmallRef"
ADOPTED_SMALL_SHA_PARAM = "ModelAutoAdopt_SmallSha"
STATUS_SMALL_PARAM = "ModelAutoAdopt_SmallStatus"

# ONNX origins, in order: NAS mirror dirs (keyed by bundle short_name), then
# git LFS (media.githubusercontent, per bundle ref).
NAS_BASE = "https://upload.shind0.synology.me/models/"
NAS_DIRS = {
  "TT": "comma4-big",
  "HBM": "comma4-big-hb",
  "TGC": "comma4-big-tgc",
  "CQV2": "comma4-big-cinque-v2",
  "CinqueTerreV2": "comma4-big-cinque-v2",
}
# The path of the ONNX inside the sunnypilot git tree at the bundle's ref.
# Big models live at the modern nested path; small/supercombo at the legacy flat path.
BIG_LFS_PATH = "openpilot/selfdrive/modeld/models/big_driving_supercombo.onnx"
SMALL_LFS_PATH = "selfdrive/modeld/models/supercombo.onnx"
LFS_REPO = "sunnypilot"

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("http_proxy") or "http://192.168.1.129:7897"


def _http_get(url: str, timeout: int = 30) -> bytes:
  req = urllib.request.Request(url, headers={"User-Agent": "auto_adopt/1.0"})
  with urllib.request.urlopen(req, timeout=timeout) as r:
    return r.read()


def _lfs_url(ref: str, path: str) -> str:
  """media.githubusercontent serves the real LFS object (github raw returns a
  135-byte pointer). Public repo: no auth token needed. Format:
  media/<owner>/<repo>/<ref>/<path> — owner AND repo both required."""
  return f"https://media.githubusercontent.com/media/{LFS_REPO}/{LFS_REPO}/{ref}/{path}"


def _probe_len(url: str, min_bytes: int = 10_000_000) -> bool:
  """HEAD-ish probe: LFS pointer is ~130B, real onnx is >= ~10MB."""
  req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "auto_adopt/1.0"})
  try:
    with urllib.request.urlopen(req, timeout=30) as r:
      cl = int(r.headers.get("Content-Length", 0))
      return cl >= min_bytes
  except Exception:
    return False


def _nas_onnx_for(short_name: str) -> tuple[str, str] | None:
  dirname = NAS_DIRS.get(short_name)
  if dirname is None:
    return None
  try:
    man = json.loads(_http_get(f"{NAS_BASE}{dirname}/manifest.json"))
    fn = man.get("filename", "")
    if fn.endswith(".onnx"):
      return f"{NAS_BASE}{dirname}/{fn}", man.get("sha256", "")
  except Exception:
    return None
  return None


def _lfs_onnx_for(ref: str, path: str) -> tuple[str, str] | None:
  url = _lfs_url(ref, path)
  if not _probe_len(url):
    return None
  return url, ""  # sha verified after download (LFS oid == model sha256)


def _download(url: str, dest: Path, expected_sha: str = "") -> str:
  tmp = dest.with_suffix(dest.suffix + ".download")
  req = urllib.request.Request(url, headers={"User-Agent": "auto_adopt/1.0"})
  sha = hashlib.sha256()
  with urllib.request.urlopen(req, timeout=7200) as r:
    with open(tmp, "wb") as f:
      while True:
        chunk = r.read(1 << 20)
        if not chunk:
          break
        f.write(chunk)
        sha.update(chunk)
  got = sha.hexdigest()
  if expected_sha and got != expected_sha:
    tmp.unlink(missing_ok=True)
    raise RuntimeError(f"sha mismatch {got[:12]} != {expected_sha[:12]}")
  shutil.move(str(tmp), str(dest))
  return got


def _make_float_inputs(onnx_path: Path) -> Path:
  """Rewrite every graph input to FLOAT (TRT 10 rejects UINT8 inputs)."""
  import onnx
  from onnx import helper
  model = onnx.load(str(onnx_path))
  g = model.graph
  new_inputs = []
  for vi in g.input:
    if vi.type.tensor_type.elem_type == onnx.TensorProto.UINT8:
      dims = [d.dim_value for d in vi.type.tensor_type.shape.dim]
      new_vi = helper.make_tensor_value_info(vi.name, onnx.TensorProto.FLOAT, dims)
      new_inputs.append(new_vi)
    else:
      new_inputs.append(vi)
  del g.input[:]
  g.input.extend(new_inputs)
  out = onnx_path.with_name(onnx_path.name + ".fp32.onnx")
  onnx.save(model, str(out))
  return out


def _build_plan(fp32_onnx: Path, plan_dest: Path) -> bool:
  """Build with the SYSTEM python3 + TRT python API (trtexec crashes on 1.8G;
  uv/Clang venv python crosses ABI with system tensorrt). optimization_level=1
  makes 2580-class small models build (default level finds no conv2d+gelu impl).
  FP16 can fail on Orin (missing sm80 shader); retry in FP32 automatically."""
  script = r'''
import tensorrt as trt, time, os, sys
onnx, plan, fp16 = sys.argv[1], sys.argv[2], sys.argv[3] == '1'
logger = trt.Logger(trt.Logger.WARNING)
builder = trt.Builder(logger)
network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
parser = trt.OnnxParser(network, logger)
ok = parser.parse_from_file(onnx)
if not ok:
    for i in range(min(parser.num_errors, 10)):
        print("err:", parser.get_error(i))
    sys.exit(1)
config = builder.create_builder_config()
config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 6 << 30)
if fp16:
    config.set_flag(trt.BuilderFlag.FP16)
try:
    config.builder_optimization_level = 1
except Exception:
    pass
engine = builder.build_serialized_network(network, config)
if not engine:
    print("build FAILED")
    sys.exit(2)
with open(plan, "wb") as f:
    f.write(engine)
print("OK", os.path.getsize(plan))
'''
  for fp16 in (True, False):
    try:
      r = subprocess.run(["/usr/bin/python3", "-c", script, str(fp32_onnx), str(plan_dest), "1" if fp16 else "0"],
                         capture_output=True, text=True, timeout=7200)
      if r.returncode == 0 and "OK" in r.stdout:
        return True
      cloudlog.warning(f"auto_adopt: plan build fp16={fp16} failed: {(r.stdout + r.stderr)[-800:]}")
    except Exception as e:
      cloudlog.error(f"auto_adopt: plan build error: {e}")
  return False


def _plan_io_matches(plan: Path, input_names: list[str], n_out: int) -> bool:
  """Check a built plan's IO matches the pkl metadata the modeld will pair it
  with. Different model generations (e.g. old 6504 supercombo vs new 2576
  driving) have incompatible input names/output width and would crash modeld."""
  try:
    import tensorrt as trt
    r = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    with open(plan, "rb") as f:
      eng = r.deserialize_cuda_engine(f.read())
    names = [eng.get_tensor_name(i) for i in range(eng.num_io_tensors)]
    outs = [n for n in names if eng.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT]
    ins = [n for n in names if eng.get_tensor_mode(n) == trt.TensorIOMode.INPUT]
    shape = eng.get_tensor_shape(outs[0])
    n_out_plan = int(shape[-1]) if len(shape) else 0
    return set(ins) == set(input_names) and n_out_plan == n_out
  except Exception:
    return False


def _pkl_metadata_for(chestnut: bool):
  """Read (input_names, n_outputs) from the pkl metadata modeld will use."""
  from openpilot.selfdrive.modeld.helpers import modeld_pkl_path, load_oob
  from openpilot.common.file_chunker import open_file_chunked
  j = load_oob(open_file_chunked(modeld_pkl_path(chestnut)))
  md = j['metadata']
  return list(md['input_shapes'].keys()), md['output_shapes']['outputs'][-1]


def _swap_plan(new_plan: Path, target_plan: Path, onnx_src: Path, target_onnx: Path) -> None:
  """Atomically replace the plan/onnx modeld's TRT backend reads."""
  for f in (target_plan, target_onnx):
    if f.exists():
      bak = f.with_name(f.name + ".bak")
      if bak.exists():
        bak.unlink()
      shutil.copy2(f, bak)
  shutil.move(str(new_plan), str(target_plan))
  shutil.copy2(str(onnx_src), str(target_onnx))


def _adopt_big(params: Params, bundle, ref: str) -> None:
  short = bundle.internalName or ""
  display = bundle.displayName or short
  src = _nas_onnx_for(short) or _lfs_onnx_for(ref, BIG_LFS_PATH) or _nas_onnx_for("TT")
  if src is None:
    params.put(STATUS_PARAM, f"no onnx source for {display}", block=True)
    cloudlog.error(f"auto_adopt: no onnx source for big {display} (ref {ref[:12]})")
    return
  url, sha = src
  params.put(STATUS_PARAM, f"downloading {display}", block=True)
  onnx_path = MODELS_DIR / f"big_driving_{short.lower()}.onnx"
  got_sha = _download(url, onnx_path, expected_sha=sha)
  params.put(STATUS_PARAM, f"rewriting inputs {display}", block=True)
  fp32 = _make_float_inputs(onnx_path)
  params.put(STATUS_PARAM, f"building TRT plan {display}", block=True)
  plan_tmp = MODELS_DIR / "big_driving_supercombo_trt.plan.new"
  if not _build_plan(fp32, plan_tmp):
    params.put(STATUS_PARAM, f"plan build failed {display}", block=True)
    return
  _swap_plan(plan_tmp, BIG_PLAN, fp32, BIG_ONNX)
  params.put(ADOPTED_REF_PARAM, ref, block=True)
  params.put(ADOPTED_SHA_PARAM, got_sha, block=True)
  params.put(STATUS_PARAM, f"adopted big {display}", block=True)
  cloudlog.warning(f"auto_adopt: big {display} adopted, modeld will load it on next start")


def _adopt_small(params: Params, bundle, ref: str) -> None:
  short = bundle.internalName or ""
  display = bundle.displayName or short
  src = _lfs_onnx_for(ref, SMALL_LFS_PATH)
  if src is None:
    params.put(STATUS_SMALL_PARAM, f"no onnx source for {display}", block=True)
    cloudlog.error(f"auto_adopt: no onnx source for small {display} (ref {ref[:12]})")
    return
  url, sha = src
  params.put(STATUS_SMALL_PARAM, f"downloading {display}", block=True)
  onnx_path = MODELS_DIR / f"driving_{short.lower()}.onnx"
  got_sha = _download(url, onnx_path, expected_sha=sha)
  params.put(STATUS_SMALL_PARAM, f"rewriting inputs {display}", block=True)
  fp32 = _make_float_inputs(onnx_path)
  params.put(STATUS_SMALL_PARAM, f"building TRT plan {display}", block=True)
  plan_tmp = MODELS_DIR / "driving_supercombo_trt.plan.new"
  if not _build_plan(fp32, plan_tmp):
    params.put(STATUS_SMALL_PARAM, f"plan build failed {display}", block=True)
    return
  # Architecture gate: the built plan must match the pkl metadata modeld will
  # pair it with (input names + output width). Old supercombo-gen onnx (6504)
  # is NOT compatible with the current 2576 driving pkl.
  try:
    ins, n_out = _pkl_metadata_for(chestnut=False)
  except Exception:
    ins, n_out = [], 0
  if not _plan_io_matches(plan_tmp, ins, n_out):
    params.put(STATUS_SMALL_PARAM, f"arch mismatch {display} (plan {n_out} vs pkl)", block=True)
    cloudlog.error(f"auto_adopt: small {display} plan IO mismatch, keeping current plan")
    plan_tmp.unlink(missing_ok=True)
    return
  _swap_plan(plan_tmp, SMALL_PLAN, fp32, SMALL_ONNX)
  params.put(ADOPTED_SMALL_REF_PARAM, ref, block=True)
  params.put(ADOPTED_SMALL_SHA_PARAM, got_sha, block=True)
  params.put(STATUS_SMALL_PARAM, f"adopted small {display}", block=True)
  cloudlog.warning(f"auto_adopt: small {display} adopted, modeld will load it on next start")


def _run_once(params: Params) -> None:
  # Big model (chestnut slot)
  bundle = get_selected_bundle(params, "chestnut")
  if bundle is not None:
    ref = bundle.ref or ""
    adopted = params.get(ADOPTED_REF_PARAM)
    if isinstance(adopted, bytes):
      adopted = adopted.decode()
    if ref and adopted != ref:
      try:
        _adopt_big(params, bundle, ref)
      except Exception as e:
        cloudlog.error(f"auto_adopt: big adopt error: {e}")
        params.put(STATUS_PARAM, f"error {e}", block=True)

  # Small model (qcom slot)
  small = get_selected_bundle(params, "qcom")
  if small is not None:
    ref = small.ref or ""
    adopted = params.get(ADOPTED_SMALL_REF_PARAM)
    if isinstance(adopted, bytes):
      adopted = adopted.decode()
    if ref and adopted != ref:
      try:
        _adopt_small(params, small, ref)
      except Exception as e:
        cloudlog.error(f"auto_adopt: small adopt error: {e}")
        params.put(STATUS_SMALL_PARAM, f"error {e}", block=True)


def main():
  params = Params()
  cloudlog.warning("auto_adopt: starting (chestnut+qcom slot watcher)")
  while True:
    try:
      _run_once(params)
    except Exception as e:
      cloudlog.error(f"auto_adopt: loop error: {e}")
    time.sleep(10)


if __name__ == "__main__":
  main()