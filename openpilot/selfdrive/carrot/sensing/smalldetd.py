# 受管小目标检测守护(§7.2/§7.16,sensing 垫片,yolo11n GPU fp16)
# manager 经 process_config.py 按参数键 SmalldetEnabled 托管;CLI/tools 薄壳共用此逻辑。
import argparse
import json
import math
import sys
import time

import cv2
import numpy as np

from openpilot.cereal import messaging
from openpilot.selfdrive.modeld.trt_runner import TrtRunner
from msgq.visionipc import VisionIpcClient, VisionStreamType

W, H = 640, 640
CONF_TH = 0.45                  # 解码预筛(后续精筛)
# 置信度门(修订24 距离自适应, 分界 FAR_CONF_M): 近场 0.60——家具误报实测聚 0.50-0.55
# (0.62 门实测全灭=纯误报); 远场 0.55(修订26, 原 0.50)——0.50-0.55 恰是误报高发带,
# 远处真目标由 3 帧发布门保证纯度。残余误报由发布确认兜底。
CONF_TH_NEAR = 0.60
CONF_TH_FAR = 0.55
IOU_TH = 0.45
MAX_DET = 64
D_MAX_ODD = 160.0    # 修订24: ODD 距离上限(m)。旧底边门 570/1080 等效量程 f*1.2/(570-540)≈40m, 高速远车全灭
FAR_CONF_M = 50.0    # 修订24: 置信度/coast 两档距离分界(m)
PERIOD_NS = 50_000_000
# 几何常量按实际帧尺寸自适应(1080 基准比例: f≈1003.8px@1920宽, 光轴中心=帧中心, CAM_H=1.2)。
# 旧版硬编码 1920x1080; 视频回放流为 1928x1208, 硬编码会错地平线门(570<真实中心604,地平线上方
# 杂物入 ODD)并使距离标尺偏大。
F_IMG = 1129.29 * 1920.0 / 2160.0   # f@1920宽基准, on_frame 内按实际 fw 线性缩放
CAM_H = 1.2
# COCO→文档类别: 0=ped 1=child 2=cyclist 3=motorcycle/car 4=animal 5=cone 6=debris 7=unknown
COCO_MAP = {0: 0, 1: 2, 2: 3, 3: 3, 5: 3, 7: 3, 15: 4, 16: 4}
KEEP = set(COCO_MAP.keys())

HB_PATH = "/tmp/smalldetd_proto.json"


def sigmoid(x):
  return 1.0 / (1.0 + np.exp(-x))


def decode_nms(out, num_classes=80):
  # out: (1, 4+nc, 8400) raw
  o = out.reshape(4 + num_classes, -1)
  boxes = o[:4, :].T               # (N,4) cx,cy,w,h @640
  scores = sigmoid(o[4:, :].T)     # (N,80)
  cls_ids = scores.argmax(axis=1)
  confs = scores.max(axis=1)
  keep = np.where((confs > CONF_TH) & np.isin(cls_ids, list(KEEP)))[0]
  if len(keep) == 0:
    return []
  boxes, confs, cls_ids = boxes[keep], confs[keep], cls_ids[keep]
  # NMS per class(boxes 为 cx,cy,w,h 中心格式,先转角点)
  x0 = boxes[:, 0] - boxes[:, 2] / 2
  y0 = boxes[:, 1] - boxes[:, 3] / 2
  x1 = boxes[:, 0] + boxes[:, 2] / 2
  y1 = boxes[:, 1] + boxes[:, 3] / 2
  order = confs.argsort()[::-1][:MAX_DET * 2]
  picked = []
  for i in order:
    suppressed = False
    for j in picked:
      if cls_ids[j] != cls_ids[i]:
        continue
      ix = max(0.0, min(x1[i], x1[j]) - max(x0[i], x0[j]))
      iy = max(0.0, min(y1[i], y1[j]) - max(y0[i], y0[j]))
      inter = ix * iy
      union = boxes[i, 2] * boxes[i, 3] + boxes[j, 2] * boxes[j, 3] - inter
      if union > 0 and inter / union > IOU_TH:
        suppressed = True
        break
    if not suppressed:
      picked.append(i)
    if len(picked) >= MAX_DET:
      break
  dets = []
  for i in picked:
    cx, cy, bw, bh = boxes[i]
    dets.append((float(cx - bw / 2), float(cy - bh / 2), float(bw), float(bh),
                 float(confs[i]), int(cls_ids[i])))
  return dets


def letterback(bx, by, bw, bh):
  # 640 系→全帧(1920x1080): scale=1/3, pad_y=140
  s = 3.0
  x0 = bx * s
  y0 = (by - 140.0) * s
  return x0, y0, bw * s, bh * s


class Track:
  __slots__ = ("tid", "cls", "conf", "bbox", "hits", "miss", "seen_ns", "last", "matched")
  def __init__(self, tid, cls, conf, bbox, now_ns):
    self.tid, self.cls, self.conf, self.bbox = tid, cls, conf, bbox
    self.hits, self.miss, self.seen_ns = 1, 0, now_ns


def iou_match(a, b):
  ax0, ay0, aw, ah = a
  bx0, by0, bw, bh = b
  ix = max(0.0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
  iy = max(0.0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
  inter = ix * iy
  return inter / max(1e-6, aw * ah + bw * bh - inter)


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument("--plan", default="/data/trt_build/yolo11n_gpu_fp16.plan")
  ap.add_argument("--hz", type=float, default=20.0)
  args, _ = ap.parse_known_args(argv if argv is not None else sys.argv[1:])

  runner = TrtRunner(args.plan)
  in_name = runner.input_names[0]

  vic = VisionIpcClient("camerad", VisionStreamType.VISION_STREAM_ROAD, conflate=True)
  assert vic.connect(True), "visionipc road connect failed"
  stride = vic.buffer.stride if hasattr(vic, "buffer") else 2048
  fw, fh = 1920, 1080   # 从首帧元数据校正

  pm = messaging.PubMaster(["smallObjectTracks"])
  tracks = {}
  next_tid = 1
  dt = 1.0 / args.hz
  print(f"smalldetd proto: plan={args.plan} hz={args.hz} stride={stride}")

  def on_frame(buf):
    nonlocal next_tid, fh, fw, stride
    try:
      fh = buf.height
      fw = buf.width
      stride = buf.stride
      uv_off = buf.uv_offset
      raw = bytes(buf.data)
    except Exception as e:
      return None, str(e)
    y = np.frombuffer(raw[:fh * stride], dtype=np.uint8).reshape(fh, stride)[:fh, :fw]
    uv = np.frombuffer(raw[uv_off: uv_off + (fh // 2) * stride],
                       dtype=np.uint8).reshape(fh // 2, stride)[:, :fw]
    nv12 = np.ascontiguousarray(np.vstack([y, uv]))
    bgr = cv2.cvtColor(nv12, cv2.COLOR_YUV2BGR_NV12)   # (fh,fw,3)
    # 640×640:按高等比缩放 + 横向中裁,无灰填充带(旧版底部 280 行灰边在 y≈360 交界
    # 产生整幅"person"巨框——红框满屏的直接元凶)
    s = H / float(fh)
    nw_full = int(round(fw * s))
    res = cv2.resize(bgr, (nw_full, H), interpolation=cv2.INTER_LINEAR)
    ox = (nw_full - W) // 2
    canvas = np.ascontiguousarray(res[:, ox:ox + W])
    k = fh / float(H)          # 640系→全帧 等比回映系数(乘法)
    f_img = F_IMG * fw / 1920.0          # 焦距按实际帧宽缩放
    cx_img, cy_img = fw * 0.5, fh * 0.5  # 光轴中心=帧中心
    x = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    out = runner.run_np({in_name: x})
    dets = decode_nms(out)
    now_ns = time.monotonic_ns()

    # 640 系 box(canvas 左上角格式)→ 全帧坐标:full = (canvas + ox) × k
    full = []
    for (bx, by, bw, bh, conf, cid) in dets:
      gx = (bx + ox) * k
      gby = by * k
      gw, gh = bw * k, bh * k
      v_b = gby + gh
      # 距离估计先行(门序依赖距离): 贴地平线(v_b<=cy+2px)距离无定义, 置 HUGE 由 D_MAX_ODD 丢弃
      d_est = 9999.0
      if v_b > cy_img + 2:
        d_est = f_img * CAM_H / (v_b - cy_img)
      # 修订24: 距离自适应置信度门(替代修订22 全距 0.60)——近场保误报抑制, 远场保高速小目标
      if conf < (CONF_TH_NEAR if d_est < FAR_CONF_M else CONF_TH_FAR):
        continue
      # 杂框门:占全帧>30% 或 人形宽高比出 [0.2,0.95] 的板砖直接丢
      area_ratio = (gw * gh) / (fw * fh)
      if area_ratio > 0.30:
        continue
      wcls = COCO_MAP[cid]
      if wcls in (0, 1, 2) and not (0.20 <= gw / max(1e-6, gh) <= 0.95):
        continue
      # 修订24: 旧底边比例门在此处(等效量程~40m, 高速远车全灭)改为 ODD 距离门
      if d_est > D_MAX_ODD:
        continue
      u_c = gx + gw / 2
      y_est = (cx_img - u_c) * d_est / f_img
      full.append(dict(bx=max(0.0, gx), by=max(0.0, gby), bw=gw, bh=gh,
                        x0=max(0.0, min(1.0, gx / fw)),
                        y0=max(0.0, min(1.0, gby / fh)),
                        x1=max(0.0, min(1.0, (gx + gw) / fw)),
                        y1=max(0.0, min(1.0, (gby + gh) / fh)),
                        conf=conf, cid=cid, wcls=COCO_MAP[cid],
                        d=math.hypot(d_est, y_est), x=d_est, y=y_est,
                        px=int(max(2, gh * 1280.0 / fw))))

    # IoU 贪心匹配
    assigned = set()
    for t in list(tracks.values()):
      t.matched = False
    for det in sorted(full, key=lambda d: -d["conf"]):
      best, best_iou = None, 0.3
      for tid, t in tracks.items():
        if tid in assigned or t.cls != det["wcls"]:
          continue
        v = iou_match((t.bbox[0], t.bbox[1], t.bbox[2], t.bbox[3]),
                      (det["bx"], det["by"], det["bw"], det["bh"]))
        if v > best_iou:
          best, best_iou = tid, v
      if best is not None:
        t = tracks[best]
        t.bbox = (det["bx"], det["by"], det["bw"], det["bh"])
        t.conf = det["conf"]
        t.hits += 1
        t.miss = 0
        t.seen_ns = now_ns
        t.last = det
        assigned.add(best)
        det["tid"] = best
      else:
        t = Track(next_tid, det["wcls"], det["conf"],
                  (det["bx"], det["by"], det["bw"], det["bh"]), now_ns)
        t.last = det
        det["tid"] = next_tid
        tracks[next_tid] = t
        assigned.add(next_tid)
        next_tid += 1
    # 未匹配 → miss
    for tid, t in tracks.items():
      if tid not in assigned:
        t.miss += 1
    # 发布(≥2 帧稳定才上屏,单帧闪烁不进); 修订24: coast 按距离两档——远场(>FAR_CONF_M)
    # 检测闪烁多, 0.5s coast 会忽隐忽现, 放宽到 1.25s
    def _miss_lim(t):
      return 25 if t.last["x"] > FAR_CONF_M else 10
    def _hits_min(t):
      # 修订26: 远场 3 帧才发布(150ms@20fps)——闪现 1-2 帧的远景误报直接不显示;
      # 真远目标持续可见, 3 帧后直接以实框出现。近场保持 2 帧弱框渐进。
      return 3 if t.last["x"] > FAR_CONF_M else 2
    live = [t for t in tracks.values() if t.miss <= _miss_lim(t) and t.hits >= _hits_min(t)]
    dead = [tid for tid, t in tracks.items() if t.miss > _miss_lim(t)]
    for tid in dead:
      tracks.pop(tid)
    live.sort(key=lambda t: -t.conf)
    live = live[:32]

    msg = messaging.new_message("smallObjectTracks")
    st = msg.smallObjectTracks
    st.frameId = getattr(buf, "frame_id", 0) or 0
    st.modelLatencyMs = 8.0
    lst = st.init("tracks", len(live))
    for j, t in enumerate(live):
      det = t.last
      lst[j].trackId = t.tid
      lst[j].cls = t.cls
      lst[j].x = det["x"]
      lst[j].y = det["y"]
      lst[j].vx = 0.0
      lst[j].vy = 0.0
      lst[j].sigmaX = 0.4
      lst[j].sigmaY = 0.4
      lst[j].score = t.conf
      lst[j].scoreFused = min(1.0, t.conf * 0.6 + 0.4 * min(t.hits / 5.0, 1.0))
      lst[j].ageFrames = max(1, t.hits)
      lst[j].confirmed = t.hits >= 3
      lst[j].source = 0
      lst[j].tExposureNs = t.seen_ns
      b = lst[j].init("bbox", 4)
      b[0], b[1], b[2], b[3] = det["x0"], det["y0"], det["x1"], det["y1"]
      lst[j].headingRad = 0.0
      lst[j].pStep = 0.0
      lst[j].tFirstSeenNs = t.seen_ns - (t.hits - 1) * PERIOD_NS
      lst[j].validAssocCount = t.hits
      lst[j].actualPeriodNs = PERIOD_NS
      lst[j].detPxH = det["px"]
    pm.send("smallObjectTracks", msg)
    return len(live), None

  last_hb = 0.0
  n_pub = 0
  t0 = time.monotonic()
  try:
    while True:
      buf = vic.recv()
      if buf is None:
        time.sleep(0.002)
        continue
      n, err = on_frame(buf)
      n_pub += 1
      now = time.monotonic()
      if err is None and now - last_hb >= 2.0:
        last_hb = now
        try:
          with open(HB_PATH, "w") as f:
            json.dump({"t": time.time(), "pub": n_pub, "hz_avg": round(n_pub / max(0.1, now - t0), 1),
                       "tracks": n, "live_tracks": len(tracks)}, f)
        except Exception:
          pass
      target = t0 + n_pub * dt
      sl = target - time.monotonic()
      if sl > 0:
        time.sleep(sl)
  except KeyboardInterrupt:
    print("stopped")


if __name__ == "__main__":
  main()
