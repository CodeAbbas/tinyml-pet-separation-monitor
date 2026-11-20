# Architecture

The system has three tiers. Each tier has one job, and the tiers are joined by plain-text interfaces you can inspect.

```
┌──────────────────────────┐   USB serial (115200)   ┌──────────────────────────┐   HTTP POST (JSON)   ┌──────────────────────────┐
│  EDGE  — Nano 33 BLE     │  D,cx,cy,conf,millis    │  GATEWAY — gateway.py    │  /api/episodes       │  BACKEND — Laravel       │
│  Sense + OV7675 camera   │ ──────────────────────▶ │  zones → features →      │ ───────────────────▶ │  validate → upsert →     │
│  FOMO object detector    │  N,-1,-1,0,millis       │  z-scores → debounce     │                      │  SQLite → dashboard      │
└──────────────────────────┘                         └────────────┬─────────────┘                      └──────────────────────────┘
                                                                  │ POST fails
                                                                  ▼
                                                     episodes_pending.jsonl ──▶ drain_queue.py (idempotent replay)
```

## 1. Edge: on-device detection (`firmware/`)

- **Model:** Edge Impulse FOMO (*Faster Objects, More Objects*) object detector, 96×96 input, a single class `pet`. It runs on the TFLite Micro engine. The exported library is in `edge-impulse-lib/`.
- **Per frame:** capture 160×120 → resize/crop to 96×96 → `run_classifier()`. Of the boxes with confidence ≥ `CONF_THRESHOLD` (0.50), the one with the highest confidence is kept, and its centroid is computed.
- **Output:** exactly one CSV line per frame:

  | Line | Meaning |
  |---|---|
  | `D,<cx>,<cy>,<conf>,<millis>` | pet detected; centroid in 96×96 pixel coordinates |
  | `N,-1,-1,0,<millis>` | no detection, or capture/inference error |

  Every frame produces a line, including failures. The gateway therefore always sees a continuous timeline and can measure detection continuity.
- **Throughput:** the recorded sessions show **0.32 FPS** (about 3.1 s per frame), which is about 38 samples per 120 s window. The model itself takes about 29 ms for DSP and about 820 ms for classification. The camera is started at its 1 FPS setting (`Cam.begin(QQVGA, RGB565, 1)`). The rest of the about 3.1 s per frame hasn't been profiled. (A comment in `gateway.py` gives 1.18 FPS, an earlier estimate.) Set `DEBUG_TIMING 1` to print per-frame timing.
- **Privacy:** no images leave the device. Only centroids and confidences are sent.

## 2. Gateway: behavioural features and anomaly scoring (`gateway/gateway.py`)

1. **Zoning:** the 96×96 frame is split into a 2×2 grid (zones Z0–Z3).
2. **Sliding window:** 120 s of samples, re-evaluated every 10 s. A window with fewer than 5 detections is skipped and counted as "sparse".
3. **Features per window** (detected samples only):

   | Feature | Definition | Unit |
   |---|---|---|
   | `transition_rate` | zone changes ÷ window span | transitions/min |
   | `dwell_entropy` | Shannon entropy of the zone occupancy distribution | bits |
   | `position_var` | mean squared distance of centroids from their mean | px² |
   | `activity` | mean centroid speed between consecutive detections | px/s |

4. **Scoring:** each feature becomes a z-score against the calibrated baseline (`baseline.json`) and is clipped to ±6. The z-scores are combined into one composite: the weighted **mean** by default, or the **max**.
5. **Decision:** the composite is compared with `Z_THRESHOLD` (2.0). An episode fires once `DEBOUNCE_WINDOWS` (3) consecutive windows are elevated. The streak then resets.
6. **Context gate:** `ALONE_CONTEXT` is a constant (`True`) in this prototype. It marks where an "owner away" signal (geofence, door sensor, etc.) would plug in.
7. **Delivery:** the gateway POSTs JSON to the backend and retries 3× with linear backoff. If every attempt fails, the episode is appended to `episodes_pending.jsonl`.

### Episode payload

```json
{
  "event_id": "f780c490-7f11-4a4a-8f6d-aff2da5dc142",
  "device_id": "nano33-01",
  "timestamp": 1786189508.39,
  "composite_z": 3.05,
  "z_scores":  {"transition_rate": 1.217, "dwell_entropy": 3.707, "position_var": 5.062, "activity": 2.212},
  "features":  {"transition_rate": 8.444, "dwell_entropy": 1.46,  "position_var": 978.178, "activity": 8.075},
  "window_sec": 60
}
```

`data/episodes_sample.jsonl` has 13 real delivered episodes. They were recorded during development, some while `WINDOW_SEC` was still 60, before it was raised to the final 120.

### Offline queue (`gateway/drain_queue.py`)

The drainer replays `episodes_pending.jsonl`:

- Delivered episodes are moved to `episodes_sent.jsonl`.
- HTTP 422 responses (validation failures) are quarantined to `episodes_bad.jsonl`.
- Anything else stays queued.

Replays are **idempotent** because the backend upserts on `event_id`. If a POST timed out after the server had already committed it, the replay updates that row and creates no duplicate.

## 3. Backend: storage and dashboard (`backend/`)

The backend is Laravel 13 (PHP ≥ 8.3) with SQLite.

| Route | Purpose |
|---|---|
| `POST /api/episodes` | Validate and `updateOrCreate` by `event_id`. Returns 201 for a new row, 200 for a replay. |
| `GET  /api/episodes` | The 100 most recent episodes as JSON. |
| `GET  /` | Dashboard: total count, latest episode, 25 most recent logs. |
| `GET  /export` | All episodes as CSV, for offline analysis. |
| `GET  /up` | Health check. |

The `episodes` table stores each z-score and feature as its **own column** rather than in a JSON blob. Evaluation queries and CSV export can then read them directly. The full payload is also kept in `raw_payload` for audit and reprocessing. Severity bands (`low` < 3.0 ≤ `moderate` < 4.0 ≤ `high`) are for display only.
