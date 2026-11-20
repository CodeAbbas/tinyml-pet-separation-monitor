# Calibration Protocol

Episodes are flagged as **deviations from this animal's own calm baseline**, not against a fixed population rule. A good baseline therefore decides whether the results can be trusted.

## 1. Check the stream before calibrating

Record a few minutes of normal behaviour and measure it:

```bash
cd gateway
python gateway.py --record ../data/sessions/probe.csv     # Ctrl+C to stop
python gateway.py --stats  ../data/sessions/probe.csv
```

`--stats` reports the true frame rate, the detection ratio and the session duration. It also recommends a `WINDOW_SEC`, `MIN_DETECTIONS` and `CALIBRATION_SEC` that give about 30 detections per window. Don't continue until both of these hold:

- the **detection ratio is ≥ 70%**. If it's lower, the confidence gate is too strict, or the subject is leaving the frame or being occluded.
- the current `WINDOW_SEC` gives **≥ 15 detections per window**.

The `probe*.csv` files in `data/sessions/` are the recordings used for this step during development.

## 2. Record the calm baseline

```bash
python gateway.py --calibrate --record ../data/sessions/calm_baseline.csv
```

- **Duration:** `CALIBRATION_SEC = 960` s (16 min).
- **Windows are non-overlapping** (`CALIB_STEP_SEC = WINDOW_SEC = 120`), so each one is an independent sample. An earlier 180 s calibration produced only about 3 windows, too few for a stable σ estimate.
- **Minimum of 8 windows** (`MIN_BASELINE_N`). If there are fewer, the gateway refuses to save a baseline and asks for a longer session.
- **Conditions:** the behaviour must be genuinely calm, with no hands or people in the frame. Lighting and camera position must be the same as during monitoring.

You can also calibrate offline from an existing recording:

```bash
python gateway.py --replay ../data/sessions/calm_baseline_v2.csv --calibrate
```

## 3. Sigma floors (the degenerate-sigma fix)

A calm animal can stay in one zone for the entire calibration. Its transition rate and dwell entropy then have a true σ of exactly 0, and any movement at all would produce an infinite z-score. To prevent this, each σ is floored:

```
sigma = max(raw_sigma, 0.15 × |mu|, ABS_FLOOR[feature])
```

| Feature | Absolute floor |
|---|---|
| `transition_rate` | 0.5 transitions/min |
| `dwell_entropy` | 0.10 bits |
| `position_var` | 25 px² |
| `activity` | 1.0 px/s |

Every z-score is also clipped to ±6 before the composite is computed, so one feature can't dominate it.

The `baseline.json` committed here shows the floors in action. It was built from 8 windows, and the subject never changed zone during them. `transition_rate` and `dwell_entropy` therefore have `raw_sigma = 0` and are floored to 0.5 and 0.1. Show the baseline with:

```bash
python gateway.py --show-baseline
```

## 4. Validate on held-out sessions

Record labelled sessions that weren't used for calibration (`calm_test_*.csv`, `restless_*.csv`). Then replay the parameter sweep:

```bash
python ablations.py                      # all experiments
python ablations.py --experiment threshold
```

What to look for:

- **0 episodes** in every calm session.
- **≥ 1 episode** in every restless session.
- A low **time-to-flag**, given as `first_ep_window`. Multiply it by `STEP_SEC` (10 s) to convert it to seconds.

## 5. When to recalibrate

Recalibrate when any of these change: camera position or angle, lighting (for example, day versus night), room layout, or the animal itself. Also recalibrate if the gateway warns that more than 20% of windows are sparse, because a baseline is only valid for the scene it was recorded in.
