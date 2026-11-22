#!/usr/bin/env python3
"""SIM7600 4G 模块 GNSS（NMEA 串口）→ gpsLocation。

非 TICI 车机（如 Jetson）上 manager 关闭了 qcomgpsd/ubloxd，gpsLocation 没有发布者，
mapsd 因等不到 GPS 拒绝渲染实时路线图。本进程在 ttyUSB0-4 中自动找到 SIM7600 的
NMEA 输出口（出厂映射为 ttyUSB1），解析 RMC/GGA 并按 NMEA 原生 1Hz 发布 gpsLocation。

要求模块 GNSS 已开机（SIM7600: AT+CGPS=1，模块常供电时一直保持）。
"""
import datetime
import os
import time
from typing import NoReturn

import openpilot.cereal.messaging as messaging
from openpilot.cereal import log
from openpilot.common.swaglog import cloudlog

try:
  import serial
except ImportError:
  serial = None

KNOTS_TO_MS = 0.514444
NMEA_BAUD = 9600
CANDIDATE_PORTS = [f'/dev/ttyUSB{i}' for i in range(5)]
REOPEN_DELAY = 5.


def checksum_ok(line: bytes) -> bool:
  r"""NMEA "$...*hh" 校验和。"""
  if not line.startswith(b'$') or b'*' not in line:
    return False
  body, _, given = line[1:].partition(b'*')
  parity = 0
  for byte in body:
    parity ^= byte
  try:
    return parity == int(given[:2], 16)
  except ValueError:
    return False


def find_nmea_port() -> str | None:
  """依次打开候选口读几秒，返回正在吐 NMEA 的串口。"""
  for port_path in CANDIDATE_PORTS:
    if not os.path.exists(port_path):
      continue
    try:
      with serial.Serial(port_path, NMEA_BAUD, timeout=0.5) as port:
        for _ in range(6):
          line = port.readline().strip()
          if line.startswith(b'$G') and checksum_ok(line):
            return port_path
    except (OSError, ValueError):
      continue
  return None


class Fix:
  """最近一次 RMC/GGA 合并的定位结果。"""

  def __init__(self):
    self.latitude = 0.
    self.longitude = 0.
    self.altitude = 0.
    self.speed = 0.
    self.bearing = 0.
    self.hdop = 0.
    self.has_fix = False
    self.timestamp = 0

  @staticmethod
  def _angle(value: str, hemisphere: str) -> float:
    """ddmm.mmmmm / dddmm.mmmmm + 半球 -> 带符号十进制度。"""
    if not value:
      return 0.
    value = float(value)
    degrees = int(value // 100)
    minutes = value - degrees * 100
    signed = degrees + minutes / 60.
    return -signed if hemisphere in ('S', 'W') else signed

  @staticmethod
  def _utc_millis(stamp: str) -> int:
    """hhmmss.ss + ddmmyy -> unix 毫秒。"""
    stamp = stamp.replace('.', '')
    try:
      hh, mm, ss = int(stamp[0:2]), int(stamp[2:4]), int(stamp[4:6])
      dd, mo, yy = int(stamp[6:8]), int(stamp[8:10]), int(stamp[10:12])
      parsed = datetime.datetime(2000 + yy, mo, dd, hh, mm, ss, tzinfo=datetime.UTC)
    except (ValueError, OverflowError):
      return 0
    return int(parsed.timestamp() * 1000)

  def apply_rmc(self, fields: list[str]):
    # $xxRMC, hhmmss.ss, A|V, lat, N|S, lon, E|W, knots, course, ddmmyy, ...
    if len(fields) < 10:
      return
    self.has_fix = fields[2] == 'A'
    if not self.has_fix:
      self.speed = 0.
      self.bearing = 0.
      return
    self.latitude = self._angle(fields[3], fields[4])
    self.longitude = self._angle(fields[5], fields[6])
    self.speed = float(fields[7] or 0.) * KNOTS_TO_MS
    self.bearing = float(fields[8] or 0.)
    self.timestamp = self._utc_millis(fields[1] + fields[9])

  def apply_gga(self, fields: list[str]):
    # $xxGGA, hhmmss.ss, lat, N|S, lon, E|W, quality, sats, hdop, alt, M, ...
    if len(fields) < 10:
      return
    if int(fields[6] or 0) <= 0:
      self.has_fix = False
      return
    self.hdop = float(fields[8] or 0.)
    self.altitude = float(fields[9] or 0.)


def build_message(fix: Fix):
  msg = messaging.new_message('gpsLocation', valid=True)
  gps = msg.gpsLocation
  gps.latitude = fix.latitude
  gps.longitude = fix.longitude
  gps.altitude = fix.altitude
  gps.speed = fix.speed
  gps.bearingDeg = fix.bearing
  # NMEA 只有 hdop 一种精度指示，按典型比例系数折算成米级估计
  hdop = max(fix.hdop, 0.5)
  gps.horizontalAccuracy = hdop * 3.
  gps.verticalAccuracy = hdop * 4.
  gps.speedAccuracy = 1.
  gps.bearingAccuracyDeg = 5.
  gps.unixTimestampMillis = fix.timestamp
  gps.vNED = [0., 0., 0.]
  gps.hasFix = fix.has_fix
  gps.source = log.GpsLocationData.SensorSource.external
  return msg


def main() -> NoReturn:
  pm = messaging.PubMaster(['gpsLocation'])
  fix = Fix()
  port_path = None
  while True:
    if serial is None:
      cloudlog.error('sim7600_nmead: pyserial 缺失，无法读取 NMEA')
      time.sleep(30.)
      continue
    if port_path is None:
      port_path = find_nmea_port()
      if port_path is None:
        time.sleep(REOPEN_DELAY)
        continue
      cloudlog.event('sim7600_nmea_port', port=port_path)
    try:
      with serial.Serial(port_path, NMEA_BAUD, timeout=2.) as port:
        last_publish = 0.
        while True:
          line = port.readline().strip()
          if not line or not checksum_ok(line):
            continue
          text = line.decode('ascii', 'ignore')
          fields = text.split(',')
          if fields[0].endswith('RMC'):
            fix.apply_rmc(fields)
          elif fields[0].endswith('GGA'):
            fix.apply_gga(fields)
          else:
            continue
          # RMC 每秒一帧，用它触发 1Hz 发布
          if fields[0].endswith('RMC') and time.monotonic() - last_publish >= 0.8:
            last_publish = time.monotonic()
            pm.send('gpsLocation', build_message(fix))
    except (OSError, ValueError):
      cloudlog.event('sim7600_nmea_lost', port=port_path)
      port_path = None
      time.sleep(REOPEN_DELAY)


if __name__ == '__main__':
  main()
