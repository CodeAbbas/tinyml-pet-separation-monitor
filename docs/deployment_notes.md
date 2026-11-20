# Deployment Notes

This is a **research prototype**. Everything below assumes it runs on a local machine or a trusted LAN. Read the **Security** section before you expose it anywhere else.

## Backend (Laravel)

Requirements: PHP ≥ 8.3 with `pdo_sqlite` and Composer. Node is only needed if you rebuild the Vite assets; the dashboard loads Tailwind from a CDN.

```bash
cd backend
composer install
cp .env.example .env
php artisan key:generate          # generates a fresh APP_KEY. Never reuse or commit one.
touch database/database.sqlite    # PowerShell: New-Item database/database.sqlite
php artisan migrate
php artisan serve                 # http://127.0.0.1:8000
```

Smoke test:

```bash
curl -X POST http://127.0.0.1:8000/api/episodes \
     -H "Content-Type: application/json" -H "Accept: application/json" \
     -d @<(head -1 ../data/episodes_sample.jsonl)
# → 201 {"status":"created",...}. Run it again → 200 {"status":"updated",...}
```

## Gateway (Python)

```bash
cd gateway
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Settings are module-level constants at the top of `gateway.py`. You can override the most common ones with environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `PET_SERIAL_PORT` | `COM10` | Serial port of the board, e.g. `/dev/ttyACM0` |
| `PET_WEBHOOK_URL` | `http://127.0.0.1:8000/api/episodes` | Backend endpoint (also used by `drain_queue.py`) |
| `PET_DEVICE_ID` | `nano33-01` | Device ID stored with each episode |

```bash
python gateway.py                     # monitor live (needs baseline.json)
python gateway.py --replay ../data/sessions/restless_03.csv   # offline replay, no POSTs
python drain_queue.py --dry-run       # inspect the offline queue
python drain_queue.py                 # deliver queued episodes
```

Run the gateway from inside `gateway/`. `baseline.json` and the `episodes_*.jsonl` queue files are read and written relative to the working directory.

The radar visualiser (`render_radar`) opens an OpenCV window and **is called in replay mode too**. It needs a desktop session. On a headless machine, comment out the `render_radar(...)` call in `run()`.

## Security: before going past localhost

| Issue | Status in this prototype | Recommended fix |
|---|---|---|
| `POST /api/episodes` is **unauthenticated** | Anyone who can reach the port can insert episodes | Issue the gateway a Sanctum token (Sanctum is already installed) and add `auth:sanctum` to the route. Send it as `Authorization: Bearer …` |
| Dashboard and `/export` are public | They expose behavioural history | Put them behind auth or a reverse proxy with access control |
| Plain HTTP | Payloads travel in clear text | Terminate TLS at a reverse proxy (Caddy or nginx) |
| `APP_DEBUG=true` in `.env.example` | Stack traces are shown on errors | Set `APP_ENV=production` and `APP_DEBUG=false` |
| `APP_KEY` | Not in this repo | Generate one per deployment with `php artisan key:generate`. Rotate it if it is ever exposed |

## Data handling

- No camera images are transmitted or stored. The only data sent off the device is centroid coordinates, confidences and derived statistics.
- `database/database.sqlite`, `.env`, `vendor/` and the gateway's runtime queue files are git-ignored.

## Known limitations

- `ALONE_CONTEXT` is hard-coded to `True`. The system doesn't yet know whether the owner is home.
- There is one device and one baseline. Multi-device support would need a baseline per `device_id`.
- `ablations.py` lists `restless_06.csv`, which was never recorded, so it is skipped. The committed results cover 5 calm and 4 restless sessions.
- Each frame takes about 3 s (0.32 FPS measured). Inference accounts for only about 0.85 s of that. The camera's 1 FPS setting and the per-frame capture/resize path are the obvious places to profile next (`DEBUG_TIMING 1`).
