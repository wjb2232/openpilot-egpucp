"""L5 sidecar 专项设置 API (热重载)。

提供:
  GET  /api/l5/status            → 所有 L5 参数 + 运行时状态 (常驻进程/决策流)
  POST /api/l5/set               → {"key": "L5ControlEnabled", "value": true} 热重载单参数

说明: 用 Params.put_bool/put 直接写, 不走通用 /api/param_set 的 check_key 路径,
      避免旧 libparams_c.so 键表不一致导致 L5 参数被拒。参数变化立即生效,
      无需重启 (controlsd 每帧读 L5ControlEnabled, manager 每周期读 L5SidecarEnabled)。
"""
from __future__ import annotations

import json
import shutil

from aiohttp import web

from openpilot.common.params import Params
from openpilot.sunnypilot.carrot.server.features.params import PARAMS_KEY

# 暴露给 web 的 L5 参数键 → (类型, 说明)
L5_KEYS: dict[str, tuple[str, str]] = {
  "L5Enabled": ("bool", "L5 总开关"),
  "L5SidecarEnabled": ("bool", "L5 sidecar 常驻进程 (manager 拉起)"),
  "L5ControlEnabled": ("bool", "L5 决策覆盖 c3 控制 (上车必须 False!)"),
  "L5ReplayMode": ("bool", "L5 回放模式"),
  "L5ModelDir": ("str", "L5 模型目录"),
  "L5Route": ("str", "L5 路线 (JSON)"),
}


def _read_key(params: Params, key: str) -> object:
  """读一个 L5 参数值 (按类型)。读取失败(如参数未注册)返回 None。"""
  try:
    kind = L5_KEYS[key][0]
    if kind == "bool":
      return bool(params.get_bool(key))
    return params.get(key, return_default=True) if kind == "str" else str(params.get(key, return_default=True) or "")
  except Exception:
    return None


def _write_key(params: Params, key: str, value: object) -> str | None:
  """写一个 L5 参数值, 失败返回错误信息, 成功返回 None。"""
  try:
    kind = L5_KEYS[key][0]
    if kind == "bool":
      params.put_bool(key, bool(value), block=True)
    else:
      params.put(key, str(value), block=True)
    return None
  except Exception as exc:  # pragma: no cover
    return str(exc)


def _l5_runtime_status(params: Params) -> dict:
  """L5 运行时状态: 常驻进程是否在跑, 决策是否在 c3 总线流。"""
  status: dict = {"resident_running": False, "decision_in_stream": False}
  try:
    import subprocess

    out = subprocess.run(["pgrep", "-f", "real_chain_loop"],
                         capture_output=True, text=True, timeout=2)
    status["resident_running"] = out.returncode == 0 and bool(out.stdout.strip())
  except Exception:
    pass
  try:
    import openpilot.cereal.messaging as messaging
    import time

    sm = messaging.SubMaster(["l5FinalDecision"], poll="l5FinalDecision")
    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.8:
      sm.update(50)
      if sm.updated.get("l5FinalDecision", False):
        status["decision_in_stream"] = True
        try:
          status["last_mode"] = str(sm["l5FinalDecision"].mode)
        except Exception:
          pass
        break
  except Exception:
    pass
  return status


async def api_l5_status(request: web.Request) -> web.Response:
  params = request.app[PARAMS_KEY]
  values = {key: _read_key(params, key) for key in L5_KEYS}
  return web.json_response({
    "ok": True,
    "values": values,
    "runtime": _l5_runtime_status(params),
  })


async def api_l5_set(request: web.Request) -> web.Response:
  try:
    body = await request.json()
  except Exception:
    return web.json_response({"ok": False, "error": "invalid json"}, status=400)
  if not isinstance(body, dict):
    return web.json_response({"ok": False, "error": "body must be a JSON object"}, status=400)

  key = body.get("key")
  if key not in L5_KEYS:
    return web.json_response({"ok": False, "error": f"unknown L5 key: {key}"}, status=400)
  if "value" not in body:
    return web.json_response({"ok": False, "error": "missing value"}, status=400)

  params = request.app[PARAMS_KEY]
  err = _write_key(params, key, body.get("value"))
  if err is not None:
    return web.json_response({"ok": False, "error": err}, status=400)
  return web.json_response({"ok": True, "key": key, "value": _read_key(params, key)})


def register(app: web.Application) -> None:
  app.router.add_get("/api/l5/status", api_l5_status)
  app.router.add_post("/api/l5/set", api_l5_set)