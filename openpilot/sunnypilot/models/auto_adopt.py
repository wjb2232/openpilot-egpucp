#!/usr/bin/env python3
"""auto_adopt: bridge between sunnypilot's model selector UI and the local TRT
backend.

The UI (models_manager) writes `ModelManager_ActiveBundleChestnut` when the
user picks a big model. Those bundles are AMD-compiled tinygrad pkls that
cannot run on this NVIDIA box — but the SAME model's official ONNX exists
(author NAS mirror + sunnypilot git LFS). This daemon:

1. watches the chestnut slot for a new user selection
2. resolves the official ONNX for that model (NAS manifest.json, else git LFS)
3. downloads it, rewrites UINT8 inputs → FLOAT, builds a TRT plan
4. swaps big_driving_supercombo_trt.plan (+ .onnx) so modeld's existing TRT
   backend runs the new model — modeld.py already auto-restarts under system
   python3 when a plan exists and picks it up via trt_plan_path().
5. keeps `is_stock_model` gate open (see process_config patch) so modeld is
   not suppressed by the tinygrad runner latch.

Idempotent: on restart it re-checks bundle ref vs adopted ref and does
nothing if already adopted. State: ModelAutoAdopt_* params.
"""
import json
import hashlib
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.sunnypilot.models.helpers import ACTIVE_BUNDLE_KEYS, get_active_bundle, get_selected_bundle

# Where the local TRT backend expects the model (resolve relative to this repo)
# .../sunnypilot/models/auto_adopt.py -> parents[2] = .../openpilot (nested layout)
MODELS_DIR = Path(__file__).resolve().parents[2] / "selfdrive/modeld/models"
TRT_ONNX = MODELS_DIR / "big_driving_supercombo_trt.onnx"
TRT_PLAN = MODELS_DIR / "big_driving_supercombo_trt.plan"
ADOPTED_REF_PARAM = "ModelAutoAdopt_Ref"
ADOPTED_SHA_PARAM = "ModelAutoAdopt_Sha"
STATUS_PARAM = "ModelAutoAdopt_Status"

# ONNX origins, in order
NAS_BASE = "https://upload.shind0.synology.me/models/"
LFS_REPO = "https://github.com/sunnypilot/sunnypilot"
LFS_ONNX_PATH = "openpilot/selfdrive/modeld/models/big_driving_supercombo.onnx"

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("http_proxy") or "http://192.168.1.129:7897"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
urllib.request.install_opener(opener)


def _http_get(url: str, timeout: int = 30) -> bytes:
  req = urllib.request.Request(url, headers={"User-Agent": "auto_adopt/1.0"})
  with urllib.request.urlopen(req, timeout=timeout) as r:
    return r.read()


def _nas_onnx_for(short_name: str, display_name: str) -> tuple[str, str] | None:
  """Return (url, sha256) from the author's NAS mirror, or None."""
  candidates = {
    "TT": "comma4-big",
    "HBM": "comma4-big-hb",
    "TGC": "comma4-big-tgc",
  }
  dirname = candidates.get(short_name)
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


def _lfs_onnx_for(ref: str) -> tuple[str, str] | None:
  """Download the ONNX via github.com/raw/<ref> (LFS pointer resolves)."""
  url = f"{LFS_REPO}/raw/{ref}/{LFS_ONNX_PATH}"
  try:
    data = _http_get(url, timeout=3600)
    if len(data) < 10_000_000:  # LFS pointer is tiny; model is >= 700MB
      return None
    return url, hashlib.sha256(data).hexdigest()
  except Exception:
    return None


def _download(url: str, dest: Path) -> str:
  tmp = dest.with_suffix(".download")
  data = _http_get(url, timeout=7200)
  tmp.write_bytes(data)
  sha = hashlib.sha256(data).hexdigest()
  shutil.move(str(tmp), str(dest))
  return sha


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
  cmd = ["trtexec",
         f"--onnx={fp32_onnx}",
         f"--saveEngine={plan_dest}",
         "--fp16",
         "--memPoolSize=workspace:6000"]
  try:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    ok = r.returncode == 0 and "PASSED" in (r.stdout + r.stderr)
    if not ok:
      cloudlog.error(f"auto_adopt: trtexec failed: {r.stderr[-2000:]}")
    return ok
  except Exception as e:
    cloudlog.error(f"auto_adopt: trtexec error: {e}")
    return False


def _run_once(params: Params) -> None:
  bundle = get_selected_bundle(params, "chestnut")
  if bundle is None:
    return
  ref = bundle.ref or ""
  if not ref:
    return
  adopted_ref = params.get(ADOPTED_REF_PARAM)
  if isinstance(adopted_ref, bytes):
    adopted_ref = adopted_ref.decode()
  if adopted_ref == ref:
    return  # already adopted
  short_name = bundle.internalName or ""
  display = bundle.displayName or short_name
  cloudlog.warning(f"auto_adopt: user selected {display} (ref {ref[:12]}), resolving ONNX")
  params.put(STATUS_PARAM, f"resolving {display}", block=True)

  # 1. find the official onnx
  url, sha = None, ""
  src = _nas_onnx_for(short_name, display)
  if src is not None:
    url, sha = src
    cloudlog.warning(f"auto_adopt: NAS mirror for {display}")
  else:
    got = _lfs_onnx_for(ref)
    if got is not None:
      url, sha = got
      cloudlog.warning(f"auto_adopt: git LFS for {display}")
  if url is None:
    params.put(STATUS_PARAM, f"no onnx source for {display}", block=True)
    return

  # 2. download + rewrite + build
  params.put(STATUS_PARAM, f"downloading {display}", block=True)
  onnx_path = MODELS_DIR / f"big_driving_{short_name.lower() or 'model'}.onnx"
  got_sha = _download(url, onnx_path)
  if sha and got_sha != sha:
    cloudlog.error(f"auto_adopt: sha mismatch {got_sha[:12]} != {sha[:12]}")
    params.put(STATUS_PARAM, f"sha mismatch {display}", block=True)
    return

  params.put(STATUS_PARAM, f"rewriting inputs (UINT8→FLOAT)", block=True)
  fp32 = _make_float_inputs(onnx_path)

  params.put(STATUS_PARAM, f"building TRT plan ({display}, ~4min)", block=True)
  plan_tmp = MODELS_DIR / "big_driving_supercombo_trt.plan.new"
  if not _build_plan(fp32, plan_tmp):
    params.put(STATUS_PARAM, f"plan build failed {display}", block=True)
    return

  # 3. atomic swap: the new model becomes the active TRT backend
  # back up current ones
  for f in (TRT_ONNX, TRT_PLAN):
    if f.exists():
      bak = f.with_name(f.name + ".bak")
      if bak.exists():
        bak.unlink()
      shutil.copy2(f, bak)
  shutil.move(str(plan_tmp), str(TRT_PLAN))
  shutil.copy2(str(fp32), str(TRT_ONNX))
  # keep the fp32 rewrite for re-runs
  final_onnx = fp32
  # cleanup temp fp32 if it equals onnx path with suffix
  if fp32 != onnx_path:
    fp32.unlink(missing_ok=True)

  params.put(ADOPTED_REF_PARAM, ref, block=True)
  params.put(ADOPTED_SHA_PARAM, got_sha, block=True)
  params.put(STATUS_PARAM, f"adopted {display} (sha {got_sha[:12]})", block=True)
  cloudlog.warning(f"auto_adopt: {display} adopted, TRT plan swapped. Restart modeld to load it.")


def main():
  params = Params()
  cloudlog.warning("auto_adopt: starting (chestnut-slot watcher)")
  while True:
    try:
      _run_once(params)
    except Exception as e:
      cloudlog.error(f"auto_adopt: loop error: {e}")
    time.sleep(10)


if __name__ == "__main__":
  main()