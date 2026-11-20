# TinyML Pet Separation Monitor

**An on-device vision system that detects restless, separation-related behaviour in pets left alone. It compares how a pet moves against that pet's own calm baseline. No images ever leave the camera.**

An Arduino Nano 33 BLE Sense with an OV7675 camera runs an Edge Impulse **FOMO** object detector (96×96, about 181 KB arena) and streams only the pet's centroid over serial. A Python gateway turns those centroids into four behavioural features, scores each 120 s window against a calibrated baseline, and debounces the result. Confirmed episodes are posted to a Laravel backend with an idempotent API, an offline retry queue, and a dashboard.

*Built as the capstone project for COM683.*

---

## How it works

```
 Nano 33 BLE Sense            gateway.py                                  Laravel
 ┌───────────────┐  serial   ┌────────────────────────────────────────┐  HTTP  ┌──────────────┐
 │ OV7675 → FOMO │ ────────▶ │ 2×2 zones → features → z-score vs      │ ─────▶ │ /api/episodes│
 │ "pet" centroid│ D,cx,cy,… │ baseline → composite ≥ 2.0 × 3 windows │  JSON  │ SQLite + UI  │
 └───────────────┘           └───────────────┬────────────────────────┘        └──────────────┘
                                             └─▶ offline queue → drain_queue.py (idempotent replay)
```

| Feature (per 120 s window) | Captures |
|---|---|
| `transition_rate` | how often the pet moves between zones |
| `dwell_entropy` | how evenly its time is spread across zones |
| `position_var` | how widely it ranges in the frame |
| `activity` | how fast it moves |

The full design is in [docs/architecture.md](docs/architecture.md).

## Results

The evaluation replays 9 held-out recorded sessions (5 calm, 4 restless) under **23 configurations** across 5 ablation experiments. The raw output is in [`data/ablation_results.csv`](data/ablation_results.csv). It is reproducible with `python gateway/ablations.py`, and a re-run matches the committed file exactly.

| Experiment | Configs | Restless sessions flagged | False episodes (calm) | Mean time-to-flag |
|---|---|---|---|---|
| Threshold sweep `z ≥ 1.0 … 4.0` | 7 | 4/4 in every config | 0 | 3 windows |
| Debounce `1, 2, 3, 5` | 4 | 4/4 | 0 | 1 → 5 windows (= the debounce) |
| Composite `mean` vs `max` | 2 | 4/4 | 0 | 3 windows |
| Feature knockout | 6 | 4/4 | 0 | 3 windows; **11.25** with `activity_only` |
| Window length `60–180 s` | 4 | 4/4 | 0 | 3 windows |

At the default configuration (`z ≥ 2.0`, debounce 3, mean composite, 120 s window):

- **Calm sessions** average a composite of −0.2 to −0.4 and never exceed **0.31**.
- **Restless sessions** average **≈ 5.0**, with 7–9 episodes per session.

**Interpretation and caveats.** The two classes are separated by a wide margin, so every threshold between 1 and 4 classifies all sessions correctly. The sweep therefore can't pick an optimal threshold: it shows a ceiling effect, not fine-tuned sensitivity. Removing any single feature changes nothing. Using `activity` alone still detects every episode, but 3–4× more slowly, so the spatial features mostly buy **speed** of detection. The dataset is small: one device, one scene, one baseline and scripted sessions. These results show that the pipeline works end to end. They don't establish real-world accuracy.

## Repository layout

```
firmware/nano_ble33_sense_camera/   Arduino sketch: capture → FOMO → one CSV line per frame
edge-impulse-lib/                   Exported Edge Impulse Arduino library (model + SDK)
gateway/                            gateway.py, drain_queue.py, ablations.py, baseline.json
data/sessions/                      15 raw serial recordings (calm, restless, probe)
data/ablation_results.csv           Evaluation output (207 rows)
data/episodes_sample.jsonl          13 real episode payloads
backend/                            Laravel 13 API + dashboard (vendor/ and .env not included)
docs/                               Architecture, calibration, board setup, deployment
```

## Quick start

**Replay a recorded session (no hardware needed):**

```bash
cd gateway
pip install -r requirements.txt
python gateway.py --show-baseline
python gateway.py --replay ../data/sessions/restless_03.csv    # opens a radar window
python ablations.py                                            # full evaluation sweep
```

**Run the backend:**

```bash
cd backend
composer install && cp .env.example .env && php artisan key:generate
touch database/database.sqlite && php artisan migrate && php artisan serve
```

**Live with hardware:** flash the board ([docs/BOARD_SETUP.md](docs/BOARD_SETUP.md)), calibrate ([docs/calibration_protocol.md](docs/calibration_protocol.md)), then run `PET_SERIAL_PORT=COM10 python gateway.py`.

Before exposing the backend beyond localhost, read [docs/deployment_notes.md](docs/deployment_notes.md). The ingestion API is unauthenticated in this prototype.

## Data

Each line in `data/sessions/*.csv` is `D,cx,cy,conf,millis` for a detection, or `N,-1,-1,0,millis` for none. The frame rate is about 0.32 FPS.

| Files | Purpose |
|---|---|
| `calm_baseline_v2.csv` | 16-minute calm recording used to build `baseline.json` (8 windows) |
| `calm_test_01–05.csv`, `restless_02–05.csv` | Held-out evaluation sessions |
| `restless_01.csv` | Early 2-minute restless recording (not in the evaluation set) |
| `probe*.csv` | Short stream-quality checks used to choose the window length |
| `calm_01.csv` | Earliest recording. It still contains the stock Edge Impulse text output, which the gateway parser skips |

## Limitations and next steps

- The "owner is away" context gate is a stub (`ALONE_CONTEXT = True`).
- There is one device, a single baseline, and a small, scripted dataset. The next step is longer recordings of real pets in more than one home.
- The frame rate is about 0.32 FPS. Only about 0.85 s per frame is inference, so profiling the capture path should pay off.
- The ingestion API needs auth (Sanctum is installed but not wired up) and TLS before any real deployment.

## License

The original code is under the [MIT License](LICENSE). `edge-impulse-lib/` and the firmware sketch are derived from Edge Impulse SDK material and keep their original licences, mainly Apache-2.0; see [NOTICE](NOTICE) and the headers in those files.
