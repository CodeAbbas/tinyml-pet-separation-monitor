#!/usr/bin/env python3
"""
COM683 CW2 - Offline Queue Drainer
================================================================================
Replays episodes that gateway.py buffered to disk while the Laravel API was
unreachable. Safe to run repeatedly.

WHY IT'S SAFE TO RE-RUN
    Each episode carries an "event_id" (UUID). The API upserts on that key, so a
    replayed episode UPDATES the existing row rather than creating a duplicate.
    This matters because a POST can fail *after* the server committed the row
    (lost response) - without idempotency that episode would be double-counted.

USAGE
    python drain_queue.py                # drain for real
    python drain_queue.py --dry-run      # show what would be sent, send nothing

BEHAVIOUR
    - successfully delivered episodes are appended to  episodes_sent.jsonl
    - episodes that still fail remain in                episodes_pending.jsonl
    - malformed lines are moved to                      episodes_bad.jsonl
================================================================================
"""

import os
import sys
import json
import time

import requests

# ============================== CONFIG ========================================
WEBHOOK_URL   = os.environ.get("PET_WEBHOOK_URL", "http://127.0.0.1:8000/api/episodes")
PENDING_FILE  = "episodes_pending.jsonl"
SENT_FILE     = "episodes_sent.jsonl"
BAD_FILE      = "episodes_bad.jsonl"
TIMEOUT       = 5
PAUSE_SEC     = 0.2          # be gentle on the dev server
# ==============================================================================


def load_pending(path):
    """Return (good_payloads, bad_raw_lines). Never raises on a malformed line."""
    good, bad = [], []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    good.append(json.loads(line))
                except json.JSONDecodeError:
                    bad.append(line)
    except FileNotFoundError:
        print(f"[drain] no queue file ({path}) - nothing to do.")
        sys.exit(0)
    return good, bad


def append_lines(path, rows):
    if not rows:
        return
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")


def rewrite(path, rows):
    """Rewrite the queue with only what still needs sending (empty file if none)."""
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main():
    dry = "--dry-run" in sys.argv

    pending, malformed = load_pending(PENDING_FILE)
    print(f"[drain] {len(pending)} queued episode(s); {len(malformed)} malformed")
    if not pending and not malformed:
        print("[drain] queue already empty.")
        return

    if malformed:
        append_lines(BAD_FILE, malformed)
        print(f"[drain] moved {len(malformed)} malformed line(s) -> {BAD_FILE}")

    if dry:
        for p in pending:
            print(f"  would POST  event_id={p.get('event_id','<none>')}  "
                  f"z={p.get('composite_z')}  t={p.get('timestamp')}")
        print("[drain] dry run - nothing sent, queue untouched.")
        return

    sent, still_failing = [], []

    for i, payload in enumerate(pending, 1):
        eid = payload.get("event_id", "<none>")
        try:
            r = requests.post(WEBHOOK_URL, json=payload, timeout=TIMEOUT)
            if r.status_code < 300:
                sent.append(payload)
                print(f"  [{i}/{len(pending)}] OK {r.status_code}  event_id={eid}")
            elif r.status_code == 422:
                # Validation failure: replaying won't help - quarantine it.
                append_lines(BAD_FILE, [payload])
                print(f"  [{i}/{len(pending)}] REJECTED 422 (quarantined)  event_id={eid}")
                print(f"        {r.text[:200]}")
            else:
                still_failing.append(payload)
                print(f"  [{i}/{len(pending)}] HTTP {r.status_code} - will retry later")
        except requests.RequestException as e:
            still_failing.append(payload)
            print(f"  [{i}/{len(pending)}] unreachable ({type(e).__name__}) - will retry later")
        time.sleep(PAUSE_SEC)

    append_lines(SENT_FILE, sent)
    rewrite(PENDING_FILE, still_failing)

    print(f"\n[drain] delivered {len(sent)}  |  still pending {len(still_failing)}")
    if still_failing:
        print("[drain] API still unreachable for some episodes - re-run once it's up.")
    else:
        print(f"[drain] queue fully drained. Archive: {SENT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[drain] interrupted - queue left intact.")