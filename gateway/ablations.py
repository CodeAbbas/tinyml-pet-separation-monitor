#!/usr/bin/env python3
"""
COM683 CW2 — Phase 7 Ablation Runner
================================================================================
Replays the 10 recorded sessions (5 calm, 5 restless) under each experimental
configuration and reports detection metrics. Output is a CSV you can chart.

PREREQUISITE
  - baseline.json exists (from calm_baseline_v2 calibration)
  - ../data/sessions/ contains the recorded .csv files
  - gateway.py is in the same directory

USAGE
    python ablations.py                      # run all experiments
    python ablations.py --experiment threshold   # run one experiment

OUTPUT
    ablation_results.csv   — one row per (experiment, config, session)
    Console summary with per-experiment sensitivity / FPR / time-to-flag
================================================================================
"""

import os
import sys
import csv
import time
import importlib
import argparse
from collections import defaultdict

# Import gateway module (must be in same directory)
import gateway as gw


# ============================== SESSION DATASET ===============================
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sessions")

# Map session files to ground-truth labels.
# Adjust filenames to match your actual recordings.
SESSIONS = {
    # calm (expect: 0 episodes)
    "calm_test_01.csv":  "calm",
    "calm_test_02.csv":  "calm",
    "calm_test_03.csv":  "calm",
    "calm_test_04.csv":  "calm",
    "calm_test_05.csv":  "calm",
    # restless (expect: >= 1 episode)
    "restless_02.csv":   "restless",
    "restless_03.csv":   "restless",
    "restless_04.csv":   "restless",
    "restless_05.csv":   "restless",
    "restless_06.csv":   "restless",
}


# ============================== SCORING =======================================
def score_session(session_path):
    """Replay a session and return (n_episodes, n_windows, first_episode_window,
       composite_values)."""
    episodes = 0
    windows = 0
    first_ep_window = None
    composites = []

    # Temporarily capture gateway output by monkey-patching
    original_post = gw.post_episode
    def fake_post(payload):
        nonlocal episodes, first_ep_window
        episodes += 1
        if first_ep_window is None:
            first_ep_window = windows
        return True
    gw.post_episode = fake_post

    # Suppress prints during bulk runs
    import io
    from contextlib import redirect_stdout
    captured = io.StringIO()

    window_buf = []
    baseline = gw.Baseline.load(gw.BASELINE_FILE)

    # We need to intercept the scoring to count windows and collect composites.
    # Simplest: re-implement the replay loop here for control.
    from collections import deque
    window = deque()
    streak = 0
    t0 = None
    next_eval = None

    for raw in gw.iter_file(session_path):
        s = gw.parse_line(raw)
        if not s:
            continue
        if t0 is None:
            t0 = s["t"]
            next_eval = t0 + gw.STEP_SEC
        if s["detected"]:
            s["zone"] = gw.zone_of(s["cx"], s["cy"])
        window.append(s)

        now = s["t"]
        while window and window[0]["t"] < now - gw.WINDOW_SEC:
            window.popleft()

        if now < next_eval:
            continue
        next_eval = now + gw.STEP_SEC

        feats = gw.extract_features(list(window))
        if not feats:
            continue

        windows += 1
        zs, composite = baseline.score(feats)
        composites.append(composite)

        elevated = gw.ALONE_CONTEXT and (composite >= gw.Z_THRESHOLD)
        streak = streak + 1 if elevated else 0
        if streak >= gw.DEBOUNCE_WINDOWS:
            episodes += 1
            if first_ep_window is None:
                first_ep_window = windows
            streak = 0

    gw.post_episode = original_post
    return {
        "episodes": episodes,
        "windows": windows,
        "first_ep_window": first_ep_window,
        "mean_composite": sum(composites) / len(composites) if composites else 0.0,
        "max_composite": max(composites) if composites else 0.0,
    }


# ============================== EXPERIMENTS ===================================
def run_experiment(name, configs, results_rows):
    """Run one experiment: for each config dict, set gateway globals, replay all
       sessions, collect metrics, restore defaults."""

    # Save original values
    originals = {}
    for cfg in configs:
        for k in cfg["params"]:
            if k not in originals:
                originals[k] = getattr(gw, k)

    for cfg in configs:
        label = cfg["label"]
        print(f"\n  [{name}] config: {label}")

        # Apply config
        for k, v in cfg["params"].items():
            setattr(gw, k, v)

        calm_episodes = 0
        calm_sessions_total = 0
        restless_detected = 0
        restless_sessions_total = 0
        ttf_values = []

        for fname, truth in SESSIONS.items():
            path = os.path.join(SESSIONS_DIR, fname)
            if not os.path.exists(path):
                print(f"    SKIP {fname} (not found)")
                continue

            result = score_session(path)

            row = {
                "experiment": name,
                "config": label,
                "session": fname,
                "truth": truth,
                "episodes": result["episodes"],
                "windows": result["windows"],
                "mean_z": round(result["mean_composite"], 2),
                "max_z": round(result["max_composite"], 2),
                "first_ep_window": result["first_ep_window"],
            }
            results_rows.append(row)

            if truth == "calm":
                calm_sessions_total += 1
                calm_episodes += result["episodes"]
            else:
                restless_sessions_total += 1
                if result["episodes"] > 0:
                    restless_detected += 1
                if result["first_ep_window"] is not None:
                    ttf_values.append(result["first_ep_window"])

            status = "OK" if (truth == "calm" and result["episodes"] == 0) or \
                             (truth == "restless" and result["episodes"] > 0) else "MISS"
            print(f"    {fname:<24} truth={truth:<9} episodes={result['episodes']}  "
                  f"mean_z={result['mean_composite']:+.2f}  [{status}]")

        # Summary
        sensitivity = restless_detected / restless_sessions_total if restless_sessions_total else 0
        fpr = calm_episodes  # total false episodes across all calm sessions
        mean_ttf = sum(ttf_values) / len(ttf_values) if ttf_values else float('nan')
        print(f"    --- sensitivity={sensitivity:.0%}  false_episodes={fpr}  "
              f"mean_time_to_flag={mean_ttf:.1f} windows")

    # Restore originals
    for k, v in originals.items():
        setattr(gw, k, v)


EXPERIMENTS = {
    "threshold": {
        "desc": "Z_THRESHOLD sweep (1.0 to 4.0)",
        "configs": [
            {"label": "z>=1.0", "params": {"Z_THRESHOLD": 1.0}},
            {"label": "z>=1.5", "params": {"Z_THRESHOLD": 1.5}},
            {"label": "z>=2.0", "params": {"Z_THRESHOLD": 2.0}},
            {"label": "z>=2.5", "params": {"Z_THRESHOLD": 2.5}},
            {"label": "z>=3.0", "params": {"Z_THRESHOLD": 3.0}},
            {"label": "z>=3.5", "params": {"Z_THRESHOLD": 3.5}},
            {"label": "z>=4.0", "params": {"Z_THRESHOLD": 4.0}},
        ],
    },
    "debounce": {
        "desc": "DEBOUNCE_WINDOWS sweep (1, 2, 3, 5)",
        "configs": [
            {"label": "debounce=1", "params": {"DEBOUNCE_WINDOWS": 1}},
            {"label": "debounce=2", "params": {"DEBOUNCE_WINDOWS": 2}},
            {"label": "debounce=3", "params": {"DEBOUNCE_WINDOWS": 3}},
            {"label": "debounce=5", "params": {"DEBOUNCE_WINDOWS": 5}},
        ],
    },
    "composite": {
        "desc": "COMPOSITE_MODE: mean vs max",
        "configs": [
            {"label": "mean", "params": {"COMPOSITE_MODE": "mean"}},
            {"label": "max",  "params": {"COMPOSITE_MODE": "max"}},
        ],
    },
    "feature_knockout": {
        "desc": "Disable each feature in turn to measure its contribution",
        "configs": [
            {"label": "all_features",    "params": {"FEATURE_WEIGHTS": {"transition_rate":1,"dwell_entropy":1,"position_var":1,"activity":1}}},
            {"label": "no_transition",   "params": {"FEATURE_WEIGHTS": {"transition_rate":0,"dwell_entropy":1,"position_var":1,"activity":1}}},
            {"label": "no_entropy",      "params": {"FEATURE_WEIGHTS": {"transition_rate":1,"dwell_entropy":0,"position_var":1,"activity":1}}},
            {"label": "no_pos_var",      "params": {"FEATURE_WEIGHTS": {"transition_rate":1,"dwell_entropy":1,"position_var":0,"activity":1}}},
            {"label": "no_activity",     "params": {"FEATURE_WEIGHTS": {"transition_rate":1,"dwell_entropy":1,"position_var":1,"activity":0}}},
            {"label": "activity_only",   "params": {"FEATURE_WEIGHTS": {"transition_rate":0,"dwell_entropy":0,"position_var":0,"activity":1}}},
        ],
    },
    "window_length": {
        "desc": "WINDOW_SEC: 60, 90, 120, 180",
        "configs": [
            {"label": "win=60s",  "params": {"WINDOW_SEC": 60,  "CALIB_STEP_SEC": 60}},
            {"label": "win=90s",  "params": {"WINDOW_SEC": 90,  "CALIB_STEP_SEC": 90}},
            {"label": "win=120s", "params": {"WINDOW_SEC": 120, "CALIB_STEP_SEC": 120}},
            {"label": "win=180s", "params": {"WINDOW_SEC": 180, "CALIB_STEP_SEC": 180}},
        ],
    },
}


# ============================== MAIN ==========================================
def main():
    ap = argparse.ArgumentParser(description="Phase 7 ablation sweeps")
    ap.add_argument("--experiment", choices=list(EXPERIMENTS.keys()),
                    help="run only this experiment (default: all)")
    args = ap.parse_args()

    if not os.path.exists(gw.BASELINE_FILE):
        sys.exit(f"No {gw.BASELINE_FILE}. Run calibration first.")

    # Check which sessions exist
    found = {f: t for f, t in SESSIONS.items()
             if os.path.exists(os.path.join(SESSIONS_DIR, f))}
    print(f"Found {len(found)}/{len(SESSIONS)} sessions:")
    for f, t in found.items():
        print(f"  {f:<28} [{t}]")
    missing = set(SESSIONS) - set(found)
    if missing:
        print(f"\nMissing: {', '.join(sorted(missing))}")
        print("Record these before running ablations for complete results.\n")

    to_run = {args.experiment: EXPERIMENTS[args.experiment]} if args.experiment \
             else EXPERIMENTS

    results_rows = []

    for name, exp in to_run.items():
        print(f"\n{'='*70}")
        print(f"EXPERIMENT: {exp['desc']}")
        print(f"{'='*70}")
        run_experiment(name, exp["configs"], results_rows)

    # Write CSV
    out_path = "ablation_results.csv"
    fields = ["experiment", "config", "session", "truth", "episodes",
              "windows", "mean_z", "max_z", "first_ep_window"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results_rows)
    print(f"\nResults saved -> {out_path}")
    print("Import into Excel/Sheets for charts. Key columns:")
    print("  - sensitivity = restless sessions with episodes>0 / total restless")
    print("  - FPR = total episodes across calm sessions (should be 0)")
    print("  - time-to-flag = first_ep_window (lower = faster detection)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ablations] interrupted")