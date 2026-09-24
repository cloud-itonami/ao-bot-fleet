#!/usr/local/bin/python3
"""zombie-session-reaper.py - close cron sessions whose owner died.

A cron session stays open (ended_at NULL) forever when its gateway was
restarted mid-run or its stream hung past the inactivity watchdog. This
script marks those sessions ended so the fleet's measurement surface
(sessions table) stops counting ghosts. It touches NO running session.

Rules (all must hold to reap):
  - source='cron'
  - ended_at IS NULL
  - last_activity_at older than REAPER_STALE_S (default 3600)
  - started within the last 30 days

Env: REAPER_STALE_S (default 3600), REAPER_MAX_AGE_D (default 30).
stdout: one line per profile with reaped counts; empty = all healthy.
"""
import os
import sqlite3
import sys
import time

PROFILES = os.path.expanduser("~/.hermes/profiles")
STALE = int(os.environ.get("REAPER_STALE_S", "3600"))
MAX_AGE_D = int(os.environ.get("REAPER_MAX_AGE_D", "30"))


def main():
    now = time.time()
    total = 0
    lines = []
    for d in sorted(os.listdir(PROFILES)):
        if ".bak" in d:
            continue
        sd = os.path.join(PROFILES, d, "state.db")
        if not os.path.exists(sd):
            continue
        try:
            con = sqlite3.connect(sd, timeout=10)
            cur = con.execute(
                "UPDATE sessions SET ended_at = ?, end_reason = 'zombie-reaped' "
                "WHERE source='cron' AND ended_at IS NULL "
                "AND last_activity_at < ? AND started_at > ?",
                (now, now - STALE, now - MAX_AGE_D * 86400))
            n = cur.rowcount
            con.commit()
            con.close()
            if n:
                total += n
                lines.append("%s: %d" % (d, n))
        except sqlite3.OperationalError:
            continue
    if total:
        print("reaped %d zombie cron sessions across %d profiles" % (total, len(lines)))
        for l in lines:
            print(" ", l)
    # silent when healthy


if __name__ == "__main__":
    sys.exit(main())
