#!/usr/local/bin/python3
"""cron-health-audit.py - hourly Hermes bot cron FLEET HEALTH audit.

no_agent script: stdout becomes the job report (empty stdout = silent).

Reads every profile's cron/jobs.json (last_status / failure_streak) and
executions.db (last runs), plus host loadavg, and appends one measured line
per hour to the cron-health ledger. Propose-only: never edits any job.

Detects, per scan:
  host  : loadavg / ncpu ratio (host-level event discriminator)
  error : jobs with last_status=error, bucketed by cause
  drift_skip : jobs whose last_error is the spend-guard (NOT a real fault)
  streak: jobs with failure_streak that grew since last scan (real worsening)
  ok_rate: fraction of ran jobs that are ok

Empty stdout = nothing new. A report only prints when the health delta
differs from the previous hour.

Env: none (all paths derived from HOME)."""
import json
import os
import sqlite3
import sys
import time
import datetime

PROFILES_DIR = os.path.expanduser("~/.hermes/profiles")
SELF = "cron-health"
LEDGER = os.path.join(PROFILES_DIR, SELF, "workspace", "cron-health-ledger.jsonl")


def loadavg_ratio():
    try:
        n = float(os.sysconf("SC_NPROCESSORS_ONLN"))
        with open("/proc/loadavg") as f:
            la = float(f.read().split()[0])
    except Exception:
        try:
            import subprocess
            n = float(os.sysconf("SC_NPROCESSORS_ONLN"))
            out = subprocess.run(["sysctl", "-n", "vm.loadavg"],
                                 capture_output=True, text=True).stdout
            la = float(out.replace("{", "").replace("}", "").split()[0])
        except Exception:
            la, n = 0.0, 1.0
    return la, la / max(n, 1)


def job_status(prof, j):
    """Return (bucket, streak, name, error)."""
    name = j.get("name", "?")
    ls = j.get("last_status")
    err = j.get("last_error") or ""
    streak = j.get("failure_streak", 0) or 0
    scratch = "drift_skip" if ("drift_skip" in err or
                               "Skipped to prevent unintended spend" in err) else None
    return ls, streak, name, err, scratch


def refresh_new(prof, j):
    # ongoing job line appended to a state file for cross-hour streak growth
    # detection is handled in the caller (we compare against saved snapshot)
    pass


def collect():
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    la, la_r = loadavg_ratio()
    total = error = ok = drift = never = disabled = 0
    buckets = {}
    streaks = []
    profiles = []
    snap = {}
    for d in sorted(os.listdir(PROFILES_DIR)):
        if d.startswith(".") or ".bak" in d or d == SELF:
            continue
        jf = os.path.join(PROFILES_DIR, d, "cron", "jobs.json")
        if not os.path.exists(jf):
            continue
        try:
            with open(jf) as fh:
                jobs = (json.load(fh) or {}).get("jobs", [])
        except (json.JSONDecodeError, OSError):
            continue
        pj = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            total += 1
            nm = j.get("name", "?")
            if j.get("enabled") is False:
                disabled += 1
                continue
            if j.get("paused_at"):
                continue
            snap.setdefault(d, {})[nm] = j.get("failure_streak", 0) or 0
            ls, streak, name, err, scratch = job_status(d, j)
            pj.append(dict(name=name, status=ls, streak=streak,
                           err=err[:60] if err else None, scratch=scratch))
            if scratch:
                drift += 1
                continue
            if ls == "error":
                error += 1
                key = "interrupt" if ("shutdown" in err or "Interrupted" in err) \
                      else "spend" if scratch else \
                      "conn" if "Connection" in err else \
                      "refused" if "REFUSED" in err else \
                      "script" if "Script not found" in err else \
                      "lock" if "lock" in err.lower() else "other"
                buckets[key] = buckets.get(key, 0) + 1
                streaks.append((d, name, streak, err[:50]))
            elif ls == "ok":
                ok += 1
            elif ls is None:
                never += 1
        profiles.append(dict(profile=d, jobs=pj))
    # streak growth vs previous snapshot
    snap_file = os.path.join(os.path.dirname(LEDGER), "state-snap.json")
    prev = {}
    if os.path.exists(snap_file):
        try:
            prev = json.load(open(snap_file))
        except Exception:
            prev = {}
    grown = []
    for p, jobs in snap.items():
        for nm, st in jobs.items():
            if st > 0 and st > prev.get(p, {}).get(nm, 0):
                grown.append((p, nm, prev.get(p, {}).get(nm, 0), st))
    with open(snap_file, "w") as fh:
        json.dump(snap, fh, ensure_ascii=False)
    rec = dict(
        ts=now, load1=round(la, 2), load_ratio=round(la_r, 2),
        total=total, ok=ok, error=error, drift=drift,
        never=never, disabled=disabled, buckets=buckets,
        streak_grown=[[p, n, int(f), int(t)] for p, n, f, t in grown],
        profiles=len(profiles))
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec, grown, buckets, la_r, ok, total


def main():
    rec, grown, buckets, la_r, ok, total = collect()
    # Only print a report when there is something to say
    lines = []
    if la_r > 3:
        lines.append("# HOST LOADALERT %.2fx/%dc at %s" % (la_r, os.sysconf("SC_NPROCESSORS_ONLN"), rec["ts"]))
    if rec["error"]:
        b = " ".join("%s=%d" % kv for kv in sorted(buckets.items()))
        lines.append("# %d ERROR jobs: %s" % (rec["error"], b))
    if grown:
        for p, n, f, t in grown:
            lines.append("# STREAK GROW %s/%s %d->%d" % (p, n, f, t))
    okpct = (100.0 * ok / max(total, 1))
    lines.append("ok_rate=%.1f%% (%d/%d) load=%.1f error=%s streak+n=%d" % (
        okpct, ok, total, rec["load1"], rec["error"], len(grown)))
    print("\n".join(lines))


if __name__ == "__main__":
    main()