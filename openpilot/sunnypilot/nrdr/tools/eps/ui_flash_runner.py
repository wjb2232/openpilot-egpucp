#!/usr/bin/env python3
"""Detached EPS UI runner.

The settings UI watches status.json while this process releases only the Panda
USB interface, validates and flashes the selected image, then restores pandad.
It never stops the comma service or the UI.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

EPS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EPS_DIR.parents[4]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EPS_DIR))


def _load_eps_flash():
  spec = importlib.util.spec_from_file_location("eps_flash_module", EPS_DIR / "flash.py")
  if spec is None or spec.loader is None:
    raise ImportError("Could not load EPS flash module")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


flash = _load_eps_flash()
from openpilot.cereal import messaging  # noqa: E402
STATE_DIR = Path("/data/eps_flash")
STATUS_PATH = STATE_DIR / "status.json"
LOG_PATH = STATE_DIR / "run.log"
LOCK_PATH = STATE_DIR / "runner.lock"
PANDAD_BLOCK_FILE = STATE_DIR / "block_pandad"
DRY_RUN_MARKERS = ("Using real client", "Safe mode: aborting before mutating actions")


def _timestamp() -> str:
  return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(message: str) -> None:
  STATE_DIR.mkdir(parents=True, exist_ok=True)
  with LOG_PATH.open("a", encoding="utf-8") as f:
    f.write(f"[{_timestamp()}] {message.rstrip()}\n")


def _write_status(record: dict, **updates) -> None:
  record.update(updates)
  record["updated_at"] = time.time()
  STATE_DIR.mkdir(parents=True, exist_ok=True)
  tmp = STATUS_PATH.with_suffix(f".tmp.{os.getpid()}")
  with tmp.open("w", encoding="utf-8") as f:
    json.dump(record, f, ensure_ascii=False, sort_keys=True)
  os.chmod(tmp, 0o644)
  os.replace(tmp, STATUS_PATH)


def _vehicle_is_offroad() -> bool:
  messaging.reset_context()
  sm = messaging.SubMaster(["deviceState"])
  # A fresh SubMaster can need a few cycles before deviceState is valid. Poll
  # instead of treating one unlucky timeout as an onroad state.
  for _ in range(20):
    sm.update(250)
    if sm.all_checks(["deviceState"]):
      return not sm["deviceState"].started
  return False


def _pandad_pids() -> list[int]:
  pids: list[int] = []
  for entry in Path("/proc").iterdir():
    if not entry.name.isdigit():
      continue
    try:
      raw_tokens = [t for t in (entry / "cmdline").read_bytes().split(b"\0") if t]
    except (OSError, PermissionError):
      continue
    if any(token == b"openpilot.selfdrive.pandad.pandad" for token in raw_tokens) or \
       any(Path(os.fsdecode(token)).name == "pandad" for token in raw_tokens):
      pids.append(int(entry.name))
  return sorted(pids)


def _wait_for_pandad(absent: bool, timeout: float) -> bool:
  deadline = time.monotonic() + timeout
  while time.monotonic() < deadline:
    pids = _pandad_pids()
    if bool(not pids) == absent:
      return True
    time.sleep(0.2)
  return bool(not _pandad_pids()) == absent


def _set_block_pandad(blocked: bool) -> None:
  STATE_DIR.mkdir(parents=True, exist_ok=True)
  if blocked:
    PANDAD_BLOCK_FILE.write_text(f"{os.getpid()}\n", encoding="utf-8")
    os.chmod(PANDAD_BLOCK_FILE, 0o644)
  else:
    PANDAD_BLOCK_FILE.unlink(missing_ok=True)


def _run_streamed(state: dict, command: list[str], env: dict[str, str], phase: str) -> tuple[int, str]:
  _log("RUN " + " ".join(command))
  _write_status(state, phase=phase, message=f"Running {Path(command[1]).name}")
  proc = subprocess.Popen(
    command,
    cwd=EPS_DIR,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
  )
  lines: list[str] = []
  assert proc.stdout is not None
  for raw in proc.stdout:
    line = raw.rstrip("\n")
    lines.append(raw)
    if line.strip():
      _log(line)
      if line.startswith("PROGRESS "):
        try:
          _, progress_phase, percent = line.split(maxsplit=2)
          progress = max(0, min(100, int(percent)))
          _write_status(state, phase=progress_phase, progress=progress,
                        message=f"{progress_phase} {progress}%")
        except (TypeError, ValueError):
          _write_status(state, phase=phase, message=line.strip()[-240:])
      else:
        _write_status(state, phase=phase, message=line.strip()[-240:])
  rc = proc.wait()
  _write_status(state, phase=phase, message=f"{Path(command[1]).name} exited {rc}")
  return rc, "".join(lines)


def _validated_image(raw_path: str) -> Path:
  path = Path(raw_path)
  if not path.is_absolute():
    path = EPS_DIR / path
  path = path.resolve()
  allowed = {Path(p).resolve() for p in flash.find_images()}
  if path not in allowed:
    raise ValueError("Firmware is not in the curated EPS guided-flash list")
  if not flash.validate(str(path)):
    raise ValueError("Firmware failed check_rwd validation")
  return path


def _image_matches_car(image: Path) -> bool:
  car_fw = flash.car_eps_fw()
  if not car_fw:
    try:
      car_fw = json.loads(STATUS_PATH.read_text(encoding="utf-8")).get("detected_fw")
    except (OSError, ValueError, TypeError):
      car_fw = None
  if not car_fw:
    return False
  versions = flash.rwd_supported_versions(str(image)) or set()
  return flash.norm_fw(car_fw) in versions


def _read_live_eps_info() -> dict:
  info = {
    "eps_online": False,
    "eps_bus": None,
    "eps_part_number": None,
    "eps_vin": None,
    "eps_read_at": time.time(),
  }
  try:
    from panda import Panda
    from opendbc.car.structs import CarParams
    from opendbc.car.uds import DATA_IDENTIFIER_TYPE, SESSION_TYPE, UdsClient, NegativeResponseError
  except Exception as exc:
    _log(f"Live EPS identify unavailable: {exc}")
    return info

  panda = None
  try:
    panda = Panda(disable_checks=True)
    panda.set_safety_mode(CarParams.SafetyModel.elm327)
    for bus in (1, 0):
      uds = UdsClient(panda, flash.EPS_ADDR, bus=bus, timeout=2.0)
      try:
        uds.tester_present()
      except NegativeResponseError:
        pass
      except Exception:
        continue

      info["eps_online"] = True
      info["eps_bus"] = bus
      _log(f"EPS responded on bus {bus}")

      try:
        uds.diagnostic_session_control(SESSION_TYPE.DEFAULT)
      except Exception:
        pass

      try:
        data = uds.read_data_by_identifier(DATA_IDENTIFIER_TYPE.APPLICATION_SOFTWARE_IDENTIFICATION)
        part_number = bytes(data).decode("latin-1", "replace").strip("\x00").strip()
        if part_number:
          info["eps_part_number"] = part_number
          _log(f"Live EPS part number: {part_number}")
      except Exception as exc:
        _log(f"EPS part number read failed on bus {bus}: {exc}")

      try:
        data = uds.read_data_by_identifier(DATA_IDENTIFIER_TYPE.VIN)
        vin = bytes(data).decode("latin-1", "replace").strip("\x00").strip()
        if vin:
          info["eps_vin"] = vin
          _log(f"EPS VIN: {vin}")
      except Exception:
        pass
      break
  except Exception as exc:
    _log(f"Live EPS identify failed: {exc}")
  finally:
    if panda is not None:
      panda.close()
  return info


def _resolve_bus(requested: str, image: Path, state: dict) -> int:
  if requested != "auto":
    return int(requested, 0)

  _write_status(state, phase="bus_detect", message="Detecting EPS CAN bus")
  addr = flash.rwd_can_address(str(image)) or flash.EPS_ADDR
  output = io.StringIO()
  with contextlib.redirect_stdout(output):
    alive = flash.probe_eps_buses(addr)
  for line in output.getvalue().splitlines():
    if line.strip():
      _log(line)
  if 1 in alive:
    return 1
  if alive:
    return alive[0]
  _log("No live EPS bus detected; falling back to bus 1")
  return 1


def _new_state(action: str, image: Path | None = None) -> dict:
  return {
    "state": "running",
    "phase": f"{action}_starting",
    "message": f"Starting {action}",
    "action": action,
    "image": flash.image_display_name(str(image)) if image else "",
    "image_path": str(image) if image else "",
    "started_at": time.time(),
    "updated_at": time.time(),
    "bus": None,
    "progress": 0,
    "returncode": None,
  }


def _failed(state: dict, exc: Exception) -> int:
  _log(f"FAILED: {exc}")
  _log(traceback.format_exc())
  _write_status(state, state="failed", phase="failed", message=str(exc))
  return 1


def _release_panda(state: dict, args: argparse.Namespace) -> int:
  try:
    if not _vehicle_is_offroad():
      raise RuntimeError("Vehicle must be offroad before releasing Panda")
    _write_status(state, phase="releasing_panda", message="Stopping pandad and releasing Panda USB")
    _set_block_pandad(True)
    if not _wait_for_pandad(absent=True, timeout=args.release_timeout):
      _set_block_pandad(False)
      raise RuntimeError("pandad did not exit; Panda was not released")
    time.sleep(args.release_delay)
    eps_info = _read_live_eps_info()
    detected_fw = eps_info.get("eps_part_number")
    if detected_fw:
      message = f"Panda released; EPS {detected_fw} on bus {eps_info.get('eps_bus')}"
    else:
      message = "Panda released; EPS did not respond"
    _write_status(state, detected_fw=detected_fw, state="success", phase="panda_released", **eps_info)
    _write_status(state, message=message)
    _log("Panda released")
    return 0
  except Exception as exc:
    _set_block_pandad(False)
    return _failed(state, exc)


def _restore_panda(state: dict, args: argparse.Namespace) -> int:
  try:
    _write_status(state, phase="restoring_panda", message="Removing Panda release lock")
    _set_block_pandad(False)
    if not _wait_for_pandad(absent=False, timeout=args.restore_timeout):
      raise RuntimeError("pandad did not restart before timeout")
    _write_status(state, state="success", phase="panda_restored", message="pandad restored")
    _log("pandad restored")
    return 0
  except Exception as exc:
    return _failed(state, exc)


def _identify_eps(state: dict, args: argparse.Namespace) -> int:
  try:
    if not _vehicle_is_offroad():
      raise RuntimeError("Vehicle must be offroad before reading EPS")
    if not PANDAD_BLOCK_FILE.exists():
      raise RuntimeError("Release Panda first")
    if not _wait_for_pandad(absent=True, timeout=args.release_timeout):
      raise RuntimeError("pandad is still running")
    _write_status(state, phase="identify", message="Reading EPS software ID and VIN")
    eps_info = _read_live_eps_info()
    detected_fw = eps_info.get("eps_part_number")
    message = f"EPS {detected_fw} on bus {eps_info.get('eps_bus')}" if detected_fw else "No EPS part number received"
    _write_status(state, detected_fw=detected_fw, state="success", phase="eps_identified", message=message, **eps_info)
    return 0
  except Exception as exc:
    return _failed(state, exc)


def _flash_panda(state: dict, args: argparse.Namespace, image: Path) -> int:
  try:
    if not _vehicle_is_offroad():
      raise RuntimeError("Vehicle must be offroad before flashing EPS")
    if not _image_matches_car(image):
      raise RuntimeError("Selected firmware does not match the reported EPS firmware")
    if not PANDAD_BLOCK_FILE.exists():
      raise RuntimeError("Release Panda first")
    if not _wait_for_pandad(absent=True, timeout=args.release_timeout):
      raise RuntimeError("pandad is still running; restore and release Panda again")

    env = flash.subprocess_env()
    bus = _resolve_bus(args.bus, image, state)
    _write_status(state, bus=bus)
    _log(f"Using CAN bus {bus}")

    dry_cmd = [
      sys.executable,
      str(EPS_DIR / "eps-update.py"),
      str(image),
      "-b",
      str(bus),
      "--seed-timeout",
      str(args.seed_timeout),
    ]
    dry_rc, dry_output = _run_streamed(state, dry_cmd, env, "dry_run")
    if not all(marker in dry_output for marker in DRY_RUN_MARKERS):
      raise RuntimeError(f"Dry run did not reach the safe abort point (exit {dry_rc})")
    if not _vehicle_is_offroad():
      raise RuntimeError("Vehicle left offroad during the dry run; refusing to flash")
    _write_status(state, phase="dry_run_ok", message="Dry run passed; flashing now")

    flash_rc, _ = _run_streamed(state, [*dry_cmd, "--danger"], env, "flashing")
    _write_status(state, returncode=flash_rc)
    if flash_rc != 0:
      raise RuntimeError(f"EPS flash failed with exit code {flash_rc}")

    _write_status(state, state="success", phase="complete", message="EPS flash completed; restore Panda when ready")
    _log("EPS flash completed successfully")
    return 0
  except Exception as exc:
    return _failed(state, exc)


def run(args: argparse.Namespace) -> int:
  image = None
  if args.action == "flash":
    try:
      image = _validated_image(args.rwd)
    except Exception as exc:
      return _failed(_new_state(args.action), exc)

  state = _new_state(args.action, image)
  _write_status(state)
  if args.action == "release":
    return _release_panda(state, args)
  if args.action == "restore":
    return _restore_panda(state, args)
  if args.action == "identify":
    return _identify_eps(state, args)
  return _flash_panda(state, args, image)

def main() -> int:
  parser = argparse.ArgumentParser(description="UI-owned Honda/Acura EPS helper")
  parser.add_argument("--action", choices=("release", "restore", "identify", "flash"), default="flash")
  parser.add_argument("--rwd", help="Curated .rwd path or path relative to eps/")
  parser.add_argument("--bus", default="auto", help="auto, 0, or 1")
  parser.add_argument("--seed-timeout", type=float, default=600.0, help="Security-access seed wait in seconds")
  parser.add_argument("--release-timeout", type=float, default=20.0, help="Seconds to wait for pandad to exit")
  parser.add_argument("--release-delay", type=float, default=2.0, help="Extra USB release settling time")
  parser.add_argument("--restore-timeout", type=float, default=20.0, help="Seconds to wait for pandad to restart")
  args = parser.parse_args()
  if args.action == "flash" and not args.rwd:
    parser.error("--rwd is required for --action flash")

  STATE_DIR.mkdir(parents=True, exist_ok=True)
  lock_file = LOCK_PATH.open("a+")
  try:
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError:
    _log("Another EPS UI flash runner is already active")
    return 2

  try:
    return run(args)
  finally:
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    lock_file.close()


if __name__ == "__main__":
  raise SystemExit(main())