#!/usr/bin/env python3
"""
COM683 CW2 - Behavioural Gateway (v2 + Radar + Stats)
"""

import os
import sys
import time
import math
import json
import uuid
import argparse
from collections import deque, Counter

import requests
import cv2
import numpy as np

try:
    import serial
except ImportError:
    serial = None

# ============================== CONFIG ========================================
SERIAL_PORT   = os.environ.get("PET_SERIAL_PORT", "COM10")
BAUD          = 115200

FRAME_W, FRAME_H = 96, 96
ZONE_COLS, ZONE_ROWS = 2, 2      # 2x2 grid -> zones Z0..Z3

WINDOW_SEC        = 120           # feature window (~70 samples @ 1.18 FPS)
STEP_SEC          = 10           # monitoring: recompute this often (overlap OK here)
MIN_DETECTIONS    = 5            # windows with fewer detections are skipped

# --- calibration ---
CALIBRATION_SEC   = 960      # >= 10 INDEPENDENT windows. 180s gave only ~3.
CALIB_STEP_SEC    = WINDOW_SEC   # non-overlapping -> genuinely independent samples
MIN_BASELINE_N    = 8            # refuse to finalise a baseline thinner than this
BASELINE_FILE     = "baseline.json"

# --- z-score robustness (fixes the degenerate-sigma bug) ---
SIGMA_REL_FLOOR   = 0.15         # sigma >= 15% of |mu|  -> kills exploding z
SIGMA_ABS_FLOOR   = {            # absolute floor per feature, in its own units
    "transition_rate": 0.5,      # transitions/min
    "dwell_entropy":   0.10,     # bits
    "position_var":    25.0,     # px^2
    "activity":        1.0,      # px/s
}
Z_CLIP            = 6.0          # clip each z to +/- this before combining

# --- composite ---
FEATURE_WEIGHTS = {
    "transition_rate": 1.0,
    "dwell_entropy":   1.0,
    "position_var":    1.0,
    "activity":        1.0,
}
COMPOSITE_MODE    = "mean"       # "mean" (all must deviate) or "max" (any may)
Z_THRESHOLD       = 2.0
DEBOUNCE_WINDOWS  = 3

# --- context gate + cloud ---
ALONE_CONTEXT     = True
WEBHOOK_URL       = os.environ.get("PET_WEBHOOK_URL", "http://127.0.0.1:8000/api/episodes")
WEBHOOK_RETRIES   = 3
DEVICE_ID         = os.environ.get("PET_DEVICE_ID", "nano33-01")

NUM_ZONES = ZONE_COLS * ZONE_ROWS

# ============================== SERIAL ========================================
def parse_line(raw):
    try:
        parts = raw.strip().split(",")
        if len(parts) != 5:
            return None
        tag, cx, cy, conf, t = parts
        return {
            "detected": (tag == "D"),
            "cx": float(cx),
            "cy": float(cy),
            "conf": float(conf),
            "t": int(t) / 1000.0,
        }
    except (ValueError, IndexError):
        return None

def iter_serial(port, baud, record_path=None):
    if serial is None:
        sys.exit("[gateway] pyserial not installed:  pip install pyserial")
    ser = serial.Serial(port, baud, timeout=1)
    print(f"[gateway] listening on {port} @ {baud}")
    rec = None
    if record_path:
        os.makedirs(os.path.dirname(record_path) or ".", exist_ok=True)
        rec = open(record_path, "w", encoding="utf-8")
        print(f"[gateway] RECORDING raw stream -> {record_path}")
    try:
        while True:
            raw = ser.readline().decode("utf-8", "ignore")
            if not raw.strip():
                continue
            if rec:
                rec.write(raw if raw.endswith("\n") else raw + "\n")
                rec.flush()
            yield raw
    finally:
        if rec:
            rec.close()
        ser.close()

def iter_file(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield line

# ============================== ZONES =========================================
def zone_of(cx, cy):
    col = min(int(cx / (FRAME_W / ZONE_COLS)), ZONE_COLS - 1)
    row = min(int(cy / (FRAME_H / ZONE_ROWS)), ZONE_ROWS - 1)
    return row * ZONE_COLS + col

# ============================== FEATURES ======================================
def extract_features(samples):
    pts = [s for s in samples if s["detected"]]
    if len(pts) < MIN_DETECTIONS:
        return None

    span_min = max((pts[-1]["t"] - pts[0]["t"]) / 60.0, 1e-6)
    total = len(pts)

    changes = sum(1 for i in range(1, total) if pts[i]["zone"] != pts[i - 1]["zone"])
    transition_rate = changes / span_min

    counts = Counter(s["zone"] for s in pts)
    entropy = 0.0
    for z in counts:
        p = counts[z] / total
        entropy -= p * math.log2(p)

    mx = sum(s["cx"] for s in pts) / total
    my = sum(s["cy"] for s in pts) / total
    position_var = sum((s["cx"] - mx) ** 2 + (s["cy"] - my) ** 2 for s in pts) / total

    speeds = []
    for i in range(1, total):
        dt = pts[i]["t"] - pts[i - 1]["t"]
        if dt <= 0:
            continue
        d = math.hypot(pts[i]["cx"] - pts[i - 1]["cx"], pts[i]["cy"] - pts[i - 1]["cy"])
        speeds.append(d / dt)
    activity = (sum(speeds) / len(speeds)) if speeds else 0.0

    return {
        "transition_rate": transition_rate,
        "dwell_entropy":   entropy,
        "position_var":    position_var,
        "activity":        activity,
    }

# ============================== BASELINE ======================================
class Baseline:
    def __init__(self):
        self.samples = {k: [] for k in FEATURE_WEIGHTS}
        self.mu, self.sigma, self.raw_sigma = {}, {}, {}
        self.n = 0

    def add(self, feats):
        for k, v in feats.items():
            self.samples[k].append(v)
        self.n += 1

    def finalise(self):
        warnings = []
        for k, vals in self.samples.items():
            n = len(vals)
            m = sum(vals) / n if n else 0.0
            var = sum((x - m) ** 2 for x in vals) / (n - 1) if n > 1 else 0.0
            raw = math.sqrt(var)

            floor = max(SIGMA_REL_FLOOR * abs(m), SIGMA_ABS_FLOOR.get(k, 1e-3))
            self.mu[k] = m
            self.raw_sigma[k] = raw
            self.sigma[k] = max(raw, floor)

            if raw < floor:
                warnings.append(
                    f"    ! {k}: observed sigma {raw:.3f} below floor {floor:.3f} "
                    f"-> floored. Calibration may have been too static for this feature."
                )
        return warnings

    def score(self, feats):
        zs = {}
        for k in FEATURE_WEIGHTS:
            z = (feats[k] - self.mu[k]) / self.sigma[k]
            zs[k] = max(-Z_CLIP, min(Z_CLIP, z))
        weighted = [FEATURE_WEIGHTS[k] * zs[k] for k in FEATURE_WEIGHTS
                    if FEATURE_WEIGHTS[k] > 0]
        if not weighted:
            return zs, 0.0
        composite = max(weighted) if COMPOSITE_MODE == "max" else sum(weighted) / len(weighted)
        return zs, composite

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"mu": self.mu, "sigma": self.sigma,
                       "raw_sigma": self.raw_sigma, "n_windows": self.n}, f, indent=2)

    @classmethod
    def load(cls, path):
        b = cls()
        with open(path) as f:
            d = json.load(f)
        b.mu, b.sigma = d["mu"], d["sigma"]
        b.raw_sigma = d.get("raw_sigma", {})
        b.n = d.get("n_windows", 0)
        return b

    def report(self):
        print(f"\n  Baseline built from {self.n} independent window(s)")
        print(f"  {'feature':<18}{'mean':>12}{'sigma':>12}{'raw sigma':>12}")
        print("  " + "-" * 54)
        for k in FEATURE_WEIGHTS:
            raw = self.raw_sigma.get(k, float('nan'))
            flag = "  <- floored" if raw < self.sigma[k] - 1e-9 else ""
            print(f"  {k:<18}{self.mu[k]:>12.3f}{self.sigma[k]:>12.3f}{raw:>12.3f}{flag}")
        print()

# ============================== VISUALIZER ====================================
def render_radar(cx, cy, detected, zone=None):
    canvas_size = 384
    scale = canvas_size / 96.0
    
    canvas = np.zeros((canvas_size, canvas_size, 3), dtype=np.uint8)
    canvas[:] = (25, 25, 25)
    
    mid = canvas_size // 2
    cv2.line(canvas, (mid, 0), (mid, canvas_size), (80, 80, 80), 2)
    cv2.line(canvas, (0, mid), (canvas_size, mid), (80, 80, 80), 2)
    
    cv2.putText(canvas, "Zone 0", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
    cv2.putText(canvas, "Zone 1", (mid + 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
    cv2.putText(canvas, "Zone 2", (10, mid + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
    cv2.putText(canvas, "Zone 3", (mid + 10, mid + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
    
    if detected and cx >= 0 and cy >= 0:
        px = int(cx * scale)
        py = int(cy * scale)
        cv2.circle(canvas, (px, py), 10, (0, 255, 0), -1)
        cv2.circle(canvas, (px, py), 16, (0, 220, 0), 2)
        cv2.putText(canvas, f"Centroid: ({int(cx)}, {int(cy)}) | Zone: {zone}", (10, canvas_size - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    else:
        cv2.putText(canvas, "NO TARGET DETECTED", (10, canvas_size - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
        
    cv2.imshow("Pet Centroid Radar (Testing Window)", canvas)
    cv2.waitKey(1)

# ============================== WEBHOOK =======================================
def post_episode(payload):
    for attempt in range(1, WEBHOOK_RETRIES + 1):
        try:
            r = requests.post(WEBHOOK_URL, json=payload, timeout=4)
            if r.status_code < 300:
                print(f"    -> episode POSTed ({r.status_code})")
                return True
            print(f"    -> webhook {r.status_code}; retry {attempt}/{WEBHOOK_RETRIES}")
        except requests.RequestException as e:
            print(f"    -> webhook error ({type(e).__name__}); retry {attempt}/{WEBHOOK_RETRIES}")
        time.sleep(1.5 * attempt)
    print("    -> POST failed; queued locally")
    with open("episodes_pending.jsonl", "a") as f:
        f.write(json.dumps(payload) + "\n")
    return False

# ============================== CORE LOOP =====================================
def run(source, calibrate, replay, post=True):
    window = deque()
    step = CALIB_STEP_SEC if calibrate else STEP_SEC

    if calibrate:
        baseline = Baseline()
        print(f"[gateway] MODE = CALIBRATING  ({CALIBRATION_SEC}s, "
              f"non-overlapping {WINDOW_SEC}s windows)")
        print("[gateway] feed genuinely CALM behaviour - hands out of frame")
    else:
        if not os.path.exists(BASELINE_FILE):
            sys.exit(f"[gateway] no {BASELINE_FILE}. Run with --calibrate first.")
        baseline = Baseline.load(BASELINE_FILE)
        print(f"[gateway] MODE = MONITORING  (baseline from {baseline.n} windows)")

    t0 = None
    next_eval = None
    streak = 0
    dropped = 0
    scored = 0

    for raw in source:
        s = parse_line(raw)
        if not s:
            continue
        if t0 is None:
            t0 = s["t"]
            next_eval = t0 + step
        if s["detected"]:
            s["zone"] = zone_of(s["cx"], s["cy"])
        window.append(s)
        
        # Draw the radar frame
        render_radar(s["cx"], s["cy"], s["detected"], s.get("zone"))

        now = s["t"]
        while window and window[0]["t"] < now - WINDOW_SEC:
            window.popleft()

        if now < next_eval:
            continue
        next_eval = now + step

        feats = extract_features(list(window))
        if not feats:
            dropped += 1
            det = sum(1 for x in window if x["detected"])
            print(f"[window] only {det} detection(s) in {WINDOW_SEC}s - skipped "
                  f"(need {MIN_DETECTIONS}). Check occlusion / object in frame.")
            continue

        scored += 1

        if calibrate:
            baseline.add(feats)
            left = max(0, int(CALIBRATION_SEC - (now - t0)))
            print(f"[calib {baseline.n:>2}] {_fmt(feats)}   ({left}s left)")
            if now - t0 >= CALIBRATION_SEC:
                break
            continue

        zs, composite = baseline.score(feats)
        elevated = ALONE_CONTEXT and (composite >= Z_THRESHOLD)
        streak = streak + 1 if elevated else 0
        fired = streak >= DEBOUNCE_WINDOWS
        mark = "  <<< EPISODE" if fired else ""
        print(f"[mon] z={_fmt(zs)}  composite={composite:+.2f}  "
              f"streak={streak}/{DEBOUNCE_WINDOWS}{mark}")

        if fired:
            if post:
                post_episode({
                    "event_id":    str(uuid.uuid4()),
                    "device_id":   DEVICE_ID,
                    "timestamp":   time.time(),
                    "composite_z": round(composite, 3),
                    "z_scores":    {k: round(v, 3) for k, v in zs.items()},
                    "features":    {k: round(v, 3) for k, v in feats.items()},
                    "window_sec":  WINDOW_SEC,
                })
            else:
                print("    -> (replay: webhook suppressed)")
            streak = 0

    if calibrate:
        if baseline.n < MIN_BASELINE_N:
            print(f"\n[gateway] ABORTED: only {baseline.n} independent windows "
                  f"(need >= {MIN_BASELINE_N}).")
            print("[gateway] Record a longer calm session, then recalibrate.")
            return
        warns = baseline.finalise()
        baseline.save(BASELINE_FILE)
        baseline.report()
        for w in warns:
            print(w)
        print(f"[gateway] baseline saved -> {BASELINE_FILE}")
    else:
        print(f"\n[gateway] windows scored: {scored}   skipped (sparse): {dropped}")
        if dropped > scored * 0.2:
            print("[gateway] WARNING: >20% of windows were too sparse. "
                  "Detection continuity is poor - fix before trusting these scores.")

def _fmt(d):
    return "{" + ", ".join(f"{k}:{v:.2f}" for k, v in d.items()) + "}"

# ============================== STREAM STATS ==================================
def stream_stats(path):
    ts, det, tot, bad = [], 0, 0, 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            s = parse_line(line)
            if not s:
                bad += 1
                continue
            tot += 1
            ts.append(s["t"])
            if s["detected"]:
                det += 1

    if len(ts) < 3:
        sys.exit(f"[stats] only {len(ts)} parseable sample(s) - nothing to measure.")

    deltas = sorted(ts[i] - ts[i - 1] for i in range(1, len(ts)) if ts[i] > ts[i - 1])
    mean_dt = sum(deltas) / len(deltas)
    median_dt = deltas[len(deltas) // 2]
    fps = 1.0 / mean_dt if mean_dt > 0 else 0.0
    duration = ts[-1] - ts[0]
    det_ratio = det / tot if tot else 0.0

    print(f"\n  Stream statistics: {path}")
    print("  " + "-" * 58)
    print(f"  parseable lines        {tot}   (ignored non-CSV: {bad})")
    print(f"  detections / total     {det}/{tot}  ({det_ratio*100:.1f}%)")
    print(f"  session duration       {duration:.1f} s  ({duration/60:.1f} min)")
    print(f"  mean frame interval    {mean_dt:.2f} s")
    print(f"  median frame interval  {median_dt:.2f} s")
    print(f"  TRUE pipeline rate     {fps:.3f} FPS")

    target_n = 30
    need_sec = target_n * mean_dt / max(det_ratio, 0.01)
    rec_window = int(math.ceil(need_sec / 30.0) * 30)
    print("\n  Recommended configuration")
    print("  " + "-" * 58)
    print(f"  WINDOW_SEC        >= {rec_window}   (for ~{target_n} detections/window)")
    print(f"  MIN_DETECTIONS       {max(10, int(target_n * 0.5))}")
    print(f"  CALIBRATION_SEC   >= {rec_window * MIN_BASELINE_N}   "
          f"({rec_window * MIN_BASELINE_N / 60:.0f} min for {MIN_BASELINE_N} "
          f"independent windows)")
    print(f"  current WINDOW_SEC = {WINDOW_SEC} -> "
          f"~{WINDOW_SEC / mean_dt * det_ratio:.1f} detections/window")

    if det_ratio < 0.7:
        print(f"\n  ! detection ratio {det_ratio*100:.0f}% is low. Either the "
              f"confidence gate is too strict,")
        print(f"    or the surrogate leaves frame / is occluded. Fix before calibrating.")
    if WINDOW_SEC / mean_dt * det_ratio < 15:
        print(f"\n  ! current WINDOW_SEC gives too few samples for stable statistics.")
        print(f"    Raise WINDOW_SEC to {rec_window} before recording a baseline.")
    print()

# ============================== CLI ===========================================
def main():
    ap = argparse.ArgumentParser(description="COM683 behavioural gateway")
    ap.add_argument("--record", metavar="FILE", help="tee raw serial stream to FILE")
    ap.add_argument("--replay", metavar="FILE", help="read from FILE instead of serial")
    ap.add_argument("--calibrate", action="store_true", help="build a new baseline")
    ap.add_argument("--show-baseline", action="store_true", help="print baseline and exit")
    ap.add_argument("--stats", metavar="FILE",
                    help="measure true frame rate / detection ratio of a recording")
    args = ap.parse_args()

    if args.show_baseline:
        if not os.path.exists(BASELINE_FILE):
            sys.exit(f"[gateway] no {BASELINE_FILE} yet.")
        Baseline.load(BASELINE_FILE).report()
        return

    if args.stats:
        if not os.path.exists(args.stats):
            sys.exit(f"[gateway] no such file: {args.stats}")
        stream_stats(args.stats)
        return

    print(f"[gateway] zones={NUM_ZONES}  window={WINDOW_SEC}s  "
          f"z_thresh={Z_THRESHOLD}  debounce={DEBOUNCE_WINDOWS}  mode={COMPOSITE_MODE}")

    if args.replay:
        if not os.path.exists(args.replay):
            sys.exit(f"[gateway] no such file: {args.replay}")
        print(f"[gateway] REPLAY <- {args.replay}")
        run(iter_file(args.replay), args.calibrate, replay=True, post=False)
    else:
        run(iter_serial(SERIAL_PORT, BAUD, args.record), args.calibrate, replay=False)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[gateway] stopped")