"""EPS firmware flasher settings panel."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import DialogResult, Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.sunnypilot.widgets.list_view import LineSeparatorSP, button_item_sp

EPS_DIR = Path("/data/openpilot/openpilot/sunnypilot/nrdr/tools/eps")
RUNNER = EPS_DIR / "ui_flash_runner.py"
STATUS_PATH = Path("/data/eps_flash/status.json")
PANDAD_BLOCK_FILE = Path("/data/eps_flash/block_pandad")
if str(EPS_DIR) not in sys.path:
  sys.path.insert(0, str(EPS_DIR))


def _load_eps_flash():
  spec = importlib.util.spec_from_file_location("eps_flash_module", EPS_DIR / "flash.py")
  if spec is None or spec.loader is None:
    raise ImportError("Could not load EPS flash module")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


flash = _load_eps_flash()


class EPSFlashLayout(Widget):
  def __init__(self):
    super().__init__()
    self._status: dict = {}
    self._last_poll = 0.0
    self._last_match_poll = 0.0
    self._launch_grace_until = 0.0
    self._detected_fw = None
    self._matched_images: list[Path] = []
    self._selected_image: Path | None = None

    self._status_item = button_item_sp(
      lambda: tr("EPS Flash"),
      lambda: self._status_label(),
      lambda: self._status_description(),
      callback=self._show_status,
    )

    self._release_item = button_item_sp(
      lambda: tr("Panda USB"),
      lambda: tr("RELEASE"),
      lambda: tr("Offroad only. Stops pandad so Python can open Panda directly."),
      callback=self._confirm_release,
      enabled=self._can_release,
    )

    self._eps_info_item = button_item_sp(
      lambda: tr("EPS Info") + " · " + self._eps_info_label(),
      lambda: self._eps_info_button(),
      lambda: self._eps_info_description(),
      callback=self._read_eps,
      enabled=self._can_read_eps,
    )

    self._restore_item = button_item_sp(
      lambda: tr("Panda USB"),
      lambda: tr("RESTORE"),
      lambda: tr("Removes the release lock and lets manager restart pandad."),
      callback=self._restore_panda,
      enabled=self._can_restore,
    )

    self._match_item = button_item_sp(
      lambda: tr("Detected EPS Firmware"),
      lambda: tr("FLASH"),
      lambda: self._match_description(),
      callback=self._confirm_flash,
      enabled=self._can_flash,
    )

    self._no_match_item = button_item_sp(
      lambda: tr("Detected EPS Firmware"),
      lambda: tr("NO MATCH"),
      lambda: self._no_match_description(),
      callback=None,
      enabled=False,
    )

    self._selection_items: dict[Path, object] = {}
    self._items = [
      self._status_item,
      LineSeparatorSP(40),
      self._release_item,
      LineSeparatorSP(40),
      self._eps_info_item,
      LineSeparatorSP(40),
      self._restore_item,
      LineSeparatorSP(40),
      self._match_item,
      self._no_match_item,
    ]

    for raw_path in flash.find_images():
      image = Path(raw_path).resolve()
      category = tr("Proper Torque Mod") if "Proper Torque Mod" in str(image) else tr("Stock recovery")
      item = button_item_sp(
        flash.image_display_name(str(image)),
        lambda: tr("SELECT"),
        category,
        callback=lambda _=None, p=image: self._select_image(p),
        enabled=lambda: not self._is_running(),
      )
      item.set_visible(False)
      self._selection_items[image] = item
      self._items.extend([item, LineSeparatorSP(40)])

    self._scroller = Scroller(self._items, line_separator=False, spacing=0)
    self._child(self._scroller)
    self._refresh_matches(force=True)

  def _refresh_status(self):
    now = time.monotonic()
    if now - self._last_poll < 0.5:
      return
    self._last_poll = now
    try:
      self._status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
      self._status = {}

  def _refresh_matches(self, force: bool = False):
    now = time.monotonic()
    if not force and now - self._last_match_poll < 1.0:
      return
    self._last_match_poll = now

    self._refresh_status()
    car_fw = flash.car_eps_fw() or self._status.get("detected_fw")
    car_norm = flash.norm_fw(car_fw) if car_fw else None
    matched: list[Path] = []
    if car_norm:
      for raw_path in flash.find_images():
        image = Path(raw_path).resolve()
        versions = flash.rwd_supported_versions(str(image))
        if versions and car_norm in versions and flash.validate(str(image)):
          matched.append(image)

    matched.sort(key=lambda p: (0 if "Proper Torque Mod" in str(p) else 1, str(p)))
    self._detected_fw = car_fw
    self._matched_images = matched

    if self._selected_image not in matched:
      self._selected_image = next((p for p in matched if "Proper Torque Mod" in str(p)), matched[0] if matched else None)

    for image, item in self._selection_items.items():
      item.set_visible(image in matched)

    self._match_item.set_visible(bool(matched))
    self._no_match_item.set_visible(not matched)

  def _is_running(self) -> bool:
    if time.monotonic() < self._launch_grace_until:
      return True
    self._refresh_status()
    if self._status.get("state") != "running":
      return False
    try:
      return time.time() - float(self._status.get("updated_at", 0)) < 30.0
    except (TypeError, ValueError):
      return False

  def _has_panda_lock(self) -> bool:
    return PANDAD_BLOCK_FILE.exists()

  def _can_release(self) -> bool:
    return ui_state.is_offroad() and not self._is_running() and not self._has_panda_lock()

  def _can_restore(self) -> bool:
    return not self._is_running() and self._has_panda_lock()

  def _can_read_eps(self) -> bool:
    return ui_state.is_offroad() and not self._is_running() and self._has_panda_lock()

  def _eps_info_button(self) -> str:
    self._refresh_status()
    if self._is_running() and self._status.get("action") == "identify":
      return tr("READING")
    if self._status.get("eps_read_at"):
      return tr("RE-READ")
    return tr("READ")

  def _eps_info_label(self) -> str:
    self._refresh_status()
    if self._is_running() and self._status.get("action") == "identify":
      return tr("READING")
    if self._status.get("eps_read_at"):
      return tr("ONLINE") if self._status.get("eps_online") else tr("NOT FOUND")
    return tr("NOT READ")

  def _eps_info_description(self) -> str:
    self._refresh_status()
    if not self._has_panda_lock():
      return tr("Release Panda first, then press READ to query EPS software ID and VIN.")
    if self._is_running() and self._status.get("action") == "identify":
      return tr("Reading EPS software ID and VIN...")
    if not self._status.get("eps_read_at"):
      return tr("Panda is released. Press READ to query EPS.")
    if not self._status.get("eps_online"):
      return tr("No EPS response was received.")
    parts = [tr("Bus: {}").format(self._status.get("eps_bus"))]
    if self._status.get("eps_part_number"):
      parts.append(tr("Part: {}").format(self._status.get("eps_part_number")))
    if self._status.get("eps_vin"):
      parts.append(tr("VIN: {}").format(self._status.get("eps_vin")))
    return " · ".join(parts)

  def _read_eps(self):
    self._start_action("identify")

  def _can_flash(self) -> bool:
    return (ui_state.is_offroad() and not self._is_running() and self._has_panda_lock() and
            self._selected_image is not None and self._selected_image in self._matched_images)

  def _status_label(self) -> str:
    self._refresh_status()
    state = self._status.get("state")
    if state == "success":
      phase = self._status.get("phase")
      if phase == "panda_released":
        return tr("PANDA RELEASED")
      if phase == "panda_restored":
        return tr("PANDA RESTORED")
      if phase == "complete":
        return tr("FLASH SUCCESS")
      return tr("SUCCESS")
    if state == "failed":
      return tr("FAILED")
    if self._is_running():
      progress = self._status.get("progress")
      if isinstance(progress, (int, float)) and progress > 0:
        return f"{int(progress)}%"
      return str(self._status.get("phase", "running")).replace("_", " ").upper()
    return tr("PANDA RESTORED") if not self._has_panda_lock() else tr("PANDA RELEASED")

  def _status_description(self) -> str:
    self._refresh_status()
    if not self._status:
      return tr("Use RELEASE first, then select a matched firmware and FLASH.")
    image = self._status.get("image", "")
    message = self._status.get("message", "")
    phase = str(self._status.get("phase", "")).replace("_", " ").title()
    prefix = f"{image}: " if image else ""
    detail = f"{phase}: {message}" if phase and message else str(message)
    return prefix + detail

  def _match_description(self) -> str:
    if not self._detected_fw:
      return tr("No EPS firmware reported by CarParams. Flashing is disabled.")
    if not self._matched_images:
      return tr("No curated firmware matches {}. Flashing is disabled.").format(self._detected_fw)
    name = flash.image_display_name(str(self._selected_image))
    return tr("Matched {} image(s). Selected: {}").format(len(self._matched_images), name)

  def _no_match_description(self) -> str:
    fw = self._detected_fw or tr("(not reported)")
    return tr("No curated firmware matches {}. Flashing is disabled until the exact EPS firmware is supported.").format(fw)

  def _select_image(self, image: Path):
    self._selected_image = image

  def _show_status(self):
    self._refresh_status()
    if not self._status:
      gui_app.push_widget(alert_dialog(tr("No EPS helper action has run yet.")))
      return
    gui_app.push_widget(alert_dialog(f"{self._status_label()}: {self._status.get('message', '')}"))

  def _confirm_release(self):
    text = tr(
      "Release Panda?<br><br>"
      "This stops pandad and keeps the Panda USB interface reserved for EPS flashing. "
      "Use RESTORE afterward. Only run this while the vehicle is offroad."
    )
    dialog = ConfirmDialog(text, tr("RELEASE"), tr("CANCEL"), rich=True,
                           callback=lambda result: self._start_action("release") if result == DialogResult.CONFIRM else None)
    gui_app.push_widget(dialog)

  def _restore_panda(self):
    self._start_action("restore")

  def _confirm_flash(self):
    image = self._selected_image
    if image is None or image not in self._matched_images:
      gui_app.push_widget(alert_dialog(tr("No matching firmware; flashing is disabled.")))
      return
    if not self._has_panda_lock():
      gui_app.push_widget(alert_dialog(tr("Release Panda first.")))
      return

    text = tr(
      "<b>Flash matched firmware?</b><br><br>"
      "Firmware: {}<br><br>"
      "Keep the vehicle in ACCESSORY mode and do not interrupt power.<br><br>"
      "The tool runs a dry run and then flashes automatically. A bad or incompatible "
      "firmware can permanently damage the EPS."
    ).format(flash.image_display_name(str(image)))
    dialog = ConfirmDialog(text, tr("FLASH"), tr("CANCEL"), rich=True,
                           callback=lambda result: self._start_action("flash", image) if result == DialogResult.CONFIRM else None)
    gui_app.push_widget(dialog)

  def _start_action(self, action: str, image: Path | None = None):
    command = [sys.executable, str(RUNNER), "--action", action]
    if image is not None:
      command.extend(["--rwd", str(image)])
    try:
      subprocess.Popen(
        command,
        cwd=EPS_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
      )
    except Exception as exc:
      gui_app.push_widget(alert_dialog(tr("Unable to start EPS action: {}").format(exc)))
      return
    self._launch_grace_until = time.monotonic() + 5.0

  def _update_state(self):
    super()._update_state()
    self._refresh_status()
    self._refresh_matches()

  def _render(self, rect):
    self._scroller.render(rect)

  def show_event(self):
    self._refresh_matches(force=True)
    self._scroller.show_event()