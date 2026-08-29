#!/usr/bin/env python3
# simple pandad wrapper that updates the panda first
import os
import usb1
import time
import signal
import subprocess

from panda import Panda, PandaDFU, PandaProtocolMismatch, McuType, FW_PATH
from openpilot.common.basedir import BASEDIR
from openpilot.common.params import Params
from openpilot.common.hardware import HARDWARE
from openpilot.common.swaglog import cloudlog

from openpilot.sunnypilot.selfdrive.pandad.rivian_long_flasher import flash_rivian_long


def get_expected_signature(panda) -> bytes:
  fn = os.path.join(FW_PATH, panda.mcu_type.config.app_fn)
  return Panda.get_signature_from_firmware(fn)

def flash_panda(panda_serial: str):
  panda = Panda(panda_serial)

  # skip flashing if the detected panda is not supported
  if panda.get_type() not in Panda.SUPPORTED_DEVICES:
    cloudlog.warning(f"Panda {panda_serial} is not supported (hw_type: {panda.get_type()}), skipping flash...")
    panda.close()
    return

  fw_signature = get_expected_signature(panda)
  internal_panda = panda.is_internal()

  panda_version = "bootstub" if panda.bootstub else panda.get_version()
  panda_signature = b"" if panda.bootstub else panda.get_signature()
  cloudlog.warning(f"Panda {panda_serial} connected, version: {panda_version}, signature {panda_signature.hex()[:16]}, expected {fw_signature.hex()[:16]}")

  if panda.bootstub or panda_signature != fw_signature:
    cloudlog.info("Panda firmware out of date, update required")
    try:
      panda.flash()
    except Exception:
      cloudlog.exception("flasher-based flash failed, falling back to DFU recover")
      panda = Panda(panda_serial)
      panda.recover(reset=(not internal_panda))
    cloudlog.info("Done flashing")

  if panda.bootstub:
    bootstub_version = panda.get_version()
    cloudlog.info(f"Flashed firmware not booting, flashing development bootloader. {bootstub_version=}, {internal_panda=}")
    if internal_panda:
      HARDWARE.recover_internal_panda()
    panda.recover(reset=(not internal_panda))
    cloudlog.info("Done flashing bootstub")

  if panda.bootstub:
    cloudlog.info("Panda still not booting, exiting")
    raise AssertionError

  panda_signature = panda.get_signature()
  if panda_signature != fw_signature:
    cloudlog.info("Version mismatch after flashing, exiting")
    raise AssertionError

  panda.close()


def check_panda_support(panda_serials: list[str]) -> list[str]:
  spi_serials = set(Panda.spi_list())
  for serial in panda_serials:
    if serial in spi_serials:
      return [serial]

  # no internal panda found: allow a supported external panda (e.g. USB black panda / dos)
  for serial in panda_serials:
    try:
      panda = Panda(serial)
      is_supported = panda.get_type() in Panda.SUPPORTED_DEVICES
      panda.close()
      if is_supported:
        return [serial]
    except Exception:
      continue

  return []


def main() -> None:
  # signal pandad to close the relay and exit
  def signal_handler(signum, frame):
    cloudlog.info(f"Caught signal {signum}, exiting")
    nonlocal do_exit
    do_exit = True
    if process is not None:
      process.send_signal(signal.SIGINT)

  process = None
  do_exit = False
  signal.signal(signal.SIGINT, signal_handler)

  # check health for lost heartbeat
  try:
    for s in Panda.list():
      with Panda(s) as p:
        health = p.health()
        if p.is_internal() and health["heartbeat_lost"]:
          Params().put_bool("PandaHeartbeatLost", True, block=True)
          cloudlog.event("heartbeat lost", deviceState=health)
  except Exception:
    cloudlog.exception("pandad.uncaught_exception")

  count = 0
  no_internal_panda_count = 0
  while not do_exit:
    try:
      cloudlog.event("pandad.flash_and_connect", count=count)
      count += 1

      # Handle missing internal panda
      if no_internal_panda_count > 0:
        # The internal panda's USB may not be enumerated yet shortly after
        # boot. Poll for it before resetting: resetting before it has finished
        # enumerating kicks it into the ROM bootloader/DFU, which makes it take
        # much longer to come online.
        panda_serials: list[str] = Panda.list()
        if not panda_serials:
          cloudlog.info("Panda not found yet, waiting for USB enumeration...")
          for _ in range(20):
            time.sleep(1)
            panda_serials = Panda.list()
            if len(panda_serials):
              cloudlog.info(f"Panda appeared after waiting: {panda_serials}")
              break
        if not panda_serials:
          cloudlog.info("No pandas found, resetting internal panda")
          HARDWARE.reset_internal_panda()
          # The internal panda takes a few seconds to boot its app after a reset.
          # Wait for it to come back in normal (non-bootstub) mode before
          # deciding whether to flash. Only fall back to the bootloader
          # (recover) path if it never appears.
          for _ in range(16):
            panda_serials = Panda.list()
            if len(panda_serials) == 1:
              try:
                with Panda(panda_serials[0]) as p:
                  if not p.bootstub:
                    break
              except Exception:
                pass
            time.sleep(0.5)
          if not panda_serials:
            cloudlog.info("Panda did not appear after reset, trying recover...")
            HARDWARE.recover_internal_panda()
            time.sleep(5)
      else:
        panda_serials = Panda.list()

      # Only touch DFU when the panda truly never came up in normal mode
      if not panda_serials:
        for serial in PandaDFU.list():
          cloudlog.info(f"Panda in DFU mode found, flashing recovery {serial}")
          PandaDFU(serial).recover()
          time.sleep(1)
        panda_serials = Panda.list()

      if len(panda_serials):
        # custom flasher for xnor's Rivian Longitudinal Upgrade Kit
        flash_rivian_long(panda_serials)
        # prefer an internal panda; otherwise fall back to a supported external panda (e.g. USB black panda / dos)
        panda_serials = check_panda_support(panda_serials)

        if len(panda_serials) == 1:
          cloudlog.info(f"{len(panda_serials)} panda found, connecting - {panda_serials}")
          flash_panda(panda_serials[0])

          # give the python libusb handles a moment to fully release the USB
          # interface before handing off to the C++ pandad
          time.sleep(2)

          # run real pandad. Pass the serial explicitly: the C3XL panda is
          # USB-only (no SPI), and relying on Panda::list() from a fresh C++
          # process right after a python session was unreliable.
          os.environ['MANAGER_DAEMON'] = 'pandad'
          process = subprocess.Popen(["./pandad", panda_serials[0]], cwd=os.path.join(BASEDIR, "openpilot/selfdrive/pandad"))
          process.wait()
          no_internal_panda_count = 0
        elif len(panda_serials) > 1:
          cloudlog.warning(f"multiple supported pandas found, cannot run single-panda pandad: {panda_serials}")
          no_internal_panda_count += 1
        else:
          cloudlog.warning("no supported panda found, retrying...")
          no_internal_panda_count += 1
      else:
        cloudlog.warning("no panda found, retrying...")
        no_internal_panda_count += 1
    # TODO: wrap all panda exceptions in a base panda exception
    except (usb1.USBErrorNoDevice, usb1.USBErrorPipe):
      # a panda was disconnected while setting everything up. let's try again
      cloudlog.exception("Panda USB exception while setting up")
    except PandaProtocolMismatch:
      cloudlog.exception("pandad.protocol_mismatch")
    except Exception:
      cloudlog.exception("pandad.uncaught_exception")


if __name__ == "__main__":
  main()
